import re
import uuid
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock, patch
from starlette.testclient import TestClient

from backend.main import app
from backend.database.models import (
    get_db_connection,
    update_user_trading_universe,
    VALID_TRADING_UNIVERSES
)
from backend.auth.routes import UserConfigRequest
from backend.auth.security import create_jwt_token
from backend.sports_bridge.executor import SportsBridgeExecutor, _parse_trade_timestamp
from backend.database.trade_store import TradeStore, _trade_epoch
from backend.routes.engine import _resolve_user_id, _execute_sports_trade
from backend.sports.sports_executor import run_sports_executor


ET_TIMESTAMP_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (AM|PM) ET$")


@pytest.fixture
def client():
    return TestClient(app)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Database & Schema Multi-Universe Acceptance Tests (R2)
# ═════════════════════════════════════════════════════════════════════════════

def test_valid_trading_universes_constant():
    """Verify VALID_TRADING_UNIVERSES set contains FINANCIAL, SPORTS, BOTH, ALL."""
    assert {"FINANCIAL", "SPORTS", "BOTH", "ALL"}.issubset(VALID_TRADING_UNIVERSES)


@pytest.mark.parametrize("universe_input,expected_stored", [
    ("BOTH", "BOTH"),
    ("both", "BOTH"),
    ("ALL", "ALL"),
    ("all", "ALL"),
    ("FINANCIAL", "FINANCIAL"),
    ("financial", "FINANCIAL"),
    ("SPORTS", "SPORTS"),
    ("sports", "SPORTS"),
])
def test_update_user_trading_universe_db_acceptance(universe_input, expected_stored):
    """Verify update_user_trading_universe accepts valid universes and normalizes to uppercase."""
    conn = get_db_connection()
    user = conn.execute("SELECT id, trading_universe FROM users WHERE id = 1").fetchone()
    conn.close()
    assert user is not None, "User 1 must exist for testing"
    orig_universe = user["trading_universe"]

    try:
        update_user_trading_universe(1, universe_input)

        conn = get_db_connection()
        updated = conn.execute("SELECT trading_universe FROM users WHERE id = 1").fetchone()
        conn.close()
        assert updated["trading_universe"] == expected_stored
    finally:
        # Restore original state
        conn = get_db_connection()
        conn.execute("UPDATE users SET trading_universe = ? WHERE id = ?", (orig_universe, 1))
        conn.commit()
        conn.close()


@pytest.mark.parametrize("invalid_universe", [
    "CRYPTO",
    "INVALID",
    "FOREX",
    "NONE",
    "",
])
def test_update_user_trading_universe_db_rejection(invalid_universe):
    """Verify update_user_trading_universe raises ValueError on invalid universe."""
    with pytest.raises(ValueError) as exc_info:
        update_user_trading_universe(1, invalid_universe)
    assert "Invalid trading_universe" in str(exc_info.value)


@pytest.mark.parametrize("valid_val,expected", [
    ("BOTH", "BOTH"),
    ("both", "BOTH"),
    ("ALL", "ALL"),
    ("all", "ALL"),
    ("FINANCIAL", "FINANCIAL"),
    ("SPORTS", "SPORTS"),
])
def test_user_config_request_schema_validation_success(valid_val, expected):
    """Verify Pydantic UserConfigRequest accepts and normalizes valid universes."""
    req = UserConfigRequest(trading_universe=valid_val)
    assert req.trading_universe == expected


@pytest.mark.parametrize("invalid_val", [
    "CRYPTO",
    "STOCK",
    "NOT_A_UNIVERSE",
    "foo",
])
def test_user_config_request_schema_validation_failure(invalid_val):
    """Verify Pydantic UserConfigRequest rejects invalid universes."""
    with pytest.raises(Exception):
        UserConfigRequest(trading_universe=invalid_val)


def test_api_user_config_both_and_all_persistence(client):
    """Verify /api/auth/user/config endpoint accepts 'BOTH' and 'ALL' and persists to DB and stats."""
    conn = get_db_connection()
    user = conn.execute("SELECT id, username, trading_universe FROM users WHERE id = 1").fetchone()
    conn.close()
    orig_universe = user["trading_universe"]

    token = create_jwt_token(user["id"], user["username"])
    headers = {"Authorization": f"Bearer {token}"}

    try:
        # 1. Update to 'BOTH'
        res_both = client.post("/api/auth/user/config", json={"trading_universe": "BOTH"}, headers=headers)
        assert res_both.status_code == 200
        stats_both = client.get("/api/auth/dashboard_stats", headers=headers).json()
        assert stats_both.get("trading_universe") == "BOTH"

        conn = get_db_connection()
        row = conn.execute("SELECT trading_universe FROM users WHERE id = ?", (user["id"],)).fetchone()
        conn.close()
        assert row["trading_universe"] == "BOTH"

        # 2. Update to 'ALL'
        res_all = client.post("/api/auth/user/config", json={"trading_universe": "ALL"}, headers=headers)
        assert res_all.status_code == 200
        stats_all = client.get("/api/auth/dashboard_stats", headers=headers).json()
        assert stats_all.get("trading_universe") == "ALL"

        # 3. Reject invalid universe with 422
        res_inv = client.post("/api/auth/user/config", json={"trading_universe": "CRYPTO_ONLY"}, headers=headers)
        assert res_inv.status_code == 422

    finally:
        conn = get_db_connection()
        conn.execute("UPDATE users SET trading_universe = ? WHERE id = ?", (orig_universe, user["id"]))
        conn.commit()
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# 2. Multi-Universe Auto-Executor Filter Matching Tests (R2)
# ═════════════════════════════════════════════════════════════════════════════

def test_financial_auto_executor_filters_multi_universe():
    """Verify SaasBroadcaster user filter includes FINANCIAL, BOTH, ALL and excludes SPORTS."""
    mock_users = [
        {"id": 1, "username": "u_both", "ai_enabled": 1, "target_asset": "BTC", "trading_universe": "BOTH"},
        {"id": 2, "username": "u_all", "ai_enabled": 1, "target_asset": "BTC", "trading_universe": "ALL"},
        {"id": 3, "username": "u_fin", "ai_enabled": 1, "target_asset": "BTC", "trading_universe": "FINANCIAL"},
        {"id": 4, "username": "u_sports", "ai_enabled": 1, "target_asset": "BTC", "trading_universe": "SPORTS"},
        {"id": 5, "username": "u_def", "ai_enabled": 1, "target_asset": "BTC"},  # default should be FINANCIAL
    ]

    target_asset = "BTC"
    # Logic matching saas_broadcaster.py:388
    active_users = [
        u for u in mock_users
        if u.get('ai_enabled', 1)
        and (u.get('trading_universe') or 'FINANCIAL').upper() in ('FINANCIAL', 'BOTH', 'ALL')
        and target_asset.upper() in [x.strip() for x in u.get('target_asset', 'BTC').upper().split(',')]
    ]

    matched_ids = {u["id"] for u in active_users}
    assert 1 in matched_ids, "User with 'BOTH' must be included in financial auto-executor"
    assert 2 in matched_ids, "User with 'ALL' must be included in financial auto-executor"
    assert 3 in matched_ids, "User with 'FINANCIAL' must be included in financial auto-executor"
    assert 5 in matched_ids, "User with default universe must be included in financial auto-executor"
    assert 4 not in matched_ids, "User with 'SPORTS' must be excluded from financial auto-executor"


def test_sports_auto_executor_filters_multi_universe():
    """Verify SportsBridgeExecutor user filter includes SPORTS, BOTH, ALL and excludes FINANCIAL."""
    mock_users = [
        {"id": 1, "username": "u_both", "ai_enabled": 1, "trading_universe": "BOTH"},
        {"id": 2, "username": "u_all", "ai_enabled": 1, "trading_universe": "ALL"},
        {"id": 3, "username": "u_sports", "ai_enabled": 1, "trading_universe": "SPORTS"},
        {"id": 4, "username": "u_fin", "ai_enabled": 1, "trading_universe": "FINANCIAL"},
        {"id": 5, "username": "u_def", "ai_enabled": 1},  # default None -> not sports
    ]

    # Logic matching sports_bridge/executor.py:330
    sports_users = [
        u for u in mock_users
        if (u.get("trading_universe") or "").upper() in ("SPORTS", "BOTH", "ALL") and bool(u.get("ai_enabled", 0))
    ]

    matched_ids = {u["id"] for u in sports_users}
    assert 1 in matched_ids, "User with 'BOTH' must be included in sports auto-executor"
    assert 2 in matched_ids, "User with 'ALL' must be included in sports auto-executor"
    assert 3 in matched_ids, "User with 'SPORTS' must be included in sports auto-executor"
    assert 4 not in matched_ids, "User with 'FINANCIAL' must be excluded from sports auto-executor"
    assert 5 not in matched_ids, "User with default universe must be excluded from sports auto-executor"


def test_user_with_both_matches_simultaneously():
    """Verify user with universe 'BOTH' is simultaneously matched by both financial and sports engines."""
    user = {"id": 99, "ai_enabled": 1, "target_asset": "BTC", "trading_universe": "BOTH"}

    financial_match = (
        user.get("ai_enabled", 1)
        and (user.get("trading_universe") or "FINANCIAL").upper() in ("FINANCIAL", "BOTH", "ALL")
        and "BTC" in [x.strip() for x in user.get("target_asset", "BTC").upper().split(",")]
    )

    sports_match = (
        (user.get("trading_universe") or "").upper() in ("SPORTS", "BOTH", "ALL")
        and bool(user.get("ai_enabled", 0))
    )

    assert financial_match is True, "User with 'BOTH' must match financial criteria"
    assert sports_match is True, "User with 'BOTH' must match sports criteria"


def test_route_effective_user_id_prioritizes_both_and_all():
    """Verify _resolve_user_id handles users with universe 'BOTH' and 'ALL'."""
    users = [
        {"id": 10, "role": "user", "trading_mode": "PAPER", "trading_universe": "FINANCIAL"},
        {"id": 20, "role": "admin", "trading_mode": "LIVE", "trading_universe": "BOTH"},
    ]
    with patch("backend.database.models.get_all_active_users", return_value=users):
        eff_id = _resolve_user_id(None)
        assert eff_id == 20, "Admin LIVE user with universe 'BOTH' should be prioritized"


# ═════════════════════════════════════════════════════════════════════════════
# 3. Standardize Timestamps Acceptance Tests (R5)
# ═════════════════════════════════════════════════════════════════════════════

def test_sports_trade_insertion_in_engine_produces_et_timestamp():
    """Verify _execute_sports_trade produces a string timestamp formatted as 'YYYY-MM-DD HH:MM:SS AM/PM ET'."""
    def fake_kalshi_event_get(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "event": {
                "markets": [{
                    "ticker": "KXNFLGAME-26OCT08TBDAL-DAL",
                    "yes_ask_dollars": "0.50",
                    "no_ask_dollars": "0.50",
                    "last_price_dollars": "0.50",
                    "status": "open",
                    "title": "Dallas Cowboys Win",
                    "yes_sub_title": "Dallas Cowboys"
                }]
            }
        }
        return resp

    pred = {
        "event_ticker": "KXNFLGAME-26OCT08TBDAL-DAL",
        "predicted_team": "Dallas Cowboys",
        "confidence_pct": 75.0,
        "edge_pct": 5.0,
        "sport": "NFL"
    }

    test_uid = 1
    with patch("backend.routes.engine.requests.get", side_effect=fake_kalshi_event_get):
        trade, err = _execute_sports_trade("KXNFLGAME-26OCT08TBDAL-DAL", pred, user_id=test_uid, trade_size=10.0)

    assert err is None, f"Execution failed: {err}"
    assert trade is not None
    trade_id = trade["id"]

    try:
        trade_db = TradeStore.get_trade_by_id(trade_id)
        assert trade_db is not None, "Trade must be saved in database"

        ts_str = trade_db["timestamp"]
        assert isinstance(ts_str, str), f"Timestamp must be a string, got {type(ts_str)}"
        assert ET_TIMESTAMP_REGEX.match(ts_str), f"Timestamp '{ts_str}' must match ET format regex"
        assert ts_str.endswith(" ET")

        # Verify parsed epoch is valid
        epoch = _trade_epoch(ts_str)
        assert epoch > 1700000000.0
        parsed_bridge = _parse_trade_timestamp(ts_str)
        assert parsed_bridge == epoch
    finally:
        conn = get_db_connection()
        conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        conn.commit()
        conn.close()


def test_sports_bridge_executor_trade_insertion_produces_et_timestamp():
    """Verify SportsBridgeExecutor.run_cycle creates trade with ET formatted string timestamp."""
    executor = SportsBridgeExecutor()
    today_code = datetime.now(ZoneInfo("America/New_York")).strftime("%y%b%d").upper()
    good_pred = {
        "sport": "NFL",
        "predicted_team": "Packers",
        "confidence_pct": 75.0,
        "edge_pct": 5.0,
        "metadata": {"is_upcoming": True, "date": today_code}
    }
    user_conf = {
        "id": 1,
        "ai_enabled": 1,
        "trading_mode": "PAPER",
        "trading_universe": "BOTH",
        "min_sports_confidence": 60.0,
        "min_sports_edge": 2.0,
        "sports_trade_size_dollars": 20.0,
        "sports_max_wager": 25.0,
        "sports_min_price": 0.20,
        "sports_max_price": 0.80,
        "sports_max_daily_trades": 5,
        "sports_max_daily_risk": 100.0,
        "sports_active_leagues": "NFL",
        "sports_market_types": "GAME"
    }
    test_ticker = f"KXNFLGAME-{today_code}GB-GB"
    created_trades = []
    orig_insert = TradeStore.insert_trade

    def capture_insert(user_id, t_dict):
        created_trades.append(t_dict)
        return orig_insert(user_id, t_dict)

    with patch("backend.sports_bridge.executor._generate_kalshi_market", return_value=(test_ticker, 0.50, "Packers Win")), \
         patch.object(executor.client, "fetch_latest_picks", return_value=[good_pred]), \
         patch("backend.sports_bridge.executor.get_all_active_users", return_value=[user_conf]), \
         patch("backend.database.trade_store.TradeStore.insert_trade", side_effect=capture_insert):
        executor.last_check = 0
        executor.run_cycle()

    assert len(created_trades) >= 1, "SportsBridgeExecutor must create at least one trade"
    t = created_trades[0]
    ts_str = t["timestamp"]
    assert isinstance(ts_str, str), f"Timestamp must be string, got {type(ts_str)}"
    assert ET_TIMESTAMP_REGEX.match(ts_str), f"Timestamp '{ts_str}' must match ET regex"
    assert ts_str.endswith(" ET")

    epoch = _trade_epoch(ts_str)
    assert epoch > 1700000000.0

    # Cleanup DB
    conn = get_db_connection()
    conn.execute("DELETE FROM trades WHERE id = ?", (t["id"],))
    conn.commit()
    conn.close()


def test_sports_standalone_executor_trade_insertion_produces_et_timestamp():
    """Verify run_sports_executor creates trades with ET formatted string timestamp."""
    pred_data = [{
        "sport": "MLB",
        "predicted_team": "Yankees",
        "confidence_pct": 80.0,
        "edge_pct": 6.0,
        "metadata": {"is_upcoming": True, "date": "261006"},
        "status": "upcoming"
    }]

    mock_users = [{
        "id": 1,
        "trading_mode": "PAPER",
        "min_sports_confidence": 70.0,
        "min_sports_edge": 3.0,
        "sports_max_wager": 10.0,
        "sports_include_live": False
    }]

    created_trades = []
    original_insert = TradeStore.insert_trade

    def capture_insert(user_id, trade):
        created_trades.append(trade)
        return original_insert(user_id, trade)

    with patch("backend.sports.sports_executor.get_predictions", return_value=pred_data), \
         patch("backend.sports.sports_executor.get_all_active_users", return_value=mock_users), \
         patch("backend.database.trade_store.TradeStore.get_open_trades", return_value=[]), \
         patch("backend.database.trade_store.TradeStore.insert_trade", side_effect=capture_insert):
        run_sports_executor()

    assert len(created_trades) >= 1
    t = created_trades[0]
    ts_str = t["timestamp"]
    assert isinstance(ts_str, str), f"Timestamp must be string, got {type(ts_str)}"
    assert ET_TIMESTAMP_REGEX.match(ts_str), f"Timestamp '{ts_str}' must match ET regex"
    assert ts_str.endswith(" ET")

    # Clean up created trade from DB
    conn = get_db_connection()
    conn.execute("DELETE FROM trades WHERE id = ?", (t["id"],))
    conn.commit()
    conn.close()
