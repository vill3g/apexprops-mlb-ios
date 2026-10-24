import pytest
import time
import json
import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from starlette.testclient import TestClient

from backend.main import app
from backend.database.models import get_db_connection, get_user_by_id, update_user_config, get_all_active_users
from backend.database.trade_store import TradeStore
from backend.btc.kalshi_trader import KalshiTrader
from backend.routes.engine_sports import _execute_sports_trade
from backend.routes.engine import _resolve_user_id
from backend.sports_bridge.executor import SportsBridgeExecutor, _parse_trade_timestamp
from backend.auth.security import create_jwt_token

# The bot refuses events whose date has passed, so fixture games are dated 30 days ahead.
_MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
_GAME_DAY = date.today() + timedelta(days=30)
GAME_DATE = f"{_GAME_DAY.year % 100:02d}{_MONTHS[_GAME_DAY.month - 1]}{_GAME_DAY.day:02d}"
GAME_TICKER = f"KXNFLGAME-{GAME_DATE}TBDAL-DAL"
GAME_TICKER_GB = f"KXNFLGAME-{GAME_DATE}GB-GB"

@pytest.fixture
def client():
    return TestClient(app)

# Helper mock for Kalshi market responses
def fake_kalshi_get(url, *args, **kwargs):
    resp = MagicMock()
    if "/events/" in url:
        resp.status_code = 404
        resp.json.return_value = {"error": {"message": "Not found"}}
    elif "/markets/" in url:
        resp.status_code = 200
        resp.json.return_value = {
            "market": {
                "ticker": GAME_TICKER,
                "yes_ask_dollars": "0.55",
                "no_ask_dollars": "0.45",
                "last_price_dollars": "0.55",
                "status": "open"
            }
        }
    else:
        resp.status_code = 200
        resp.json.return_value = {}
    return resp


# ═════════════════════════════════════════════════════════════════════════════
# 1. KalshiTrader.place_sports_order Unit Tests
# ═════════════════════════════════════════════════════════════════════════════

def test_place_sports_order_validation():
    """Verify input validation: invalid side, invalid count, unauthenticated."""
    trader = KalshiTrader()

    # Invalid side
    res = trader.place_sports_order("KXNFLGAME-TEST", side="INVALID", count=1, dry_run=True)
    assert res["success"] is False
    assert "Invalid side" in res["error"]

    # Invalid count (0 or negative)
    res = trader.place_sports_order("KXNFLGAME-TEST", side="YES", count=0, dry_run=True)
    assert res["success"] is False
    assert "positive whole integer" in res["error"]

    # Fractional count
    res = trader.place_sports_order("KXNFLGAME-TEST", side="YES", count=1.5, dry_run=True)
    assert res["success"] is False
    assert "fractional" in res["error"]

    # Live order on explicitly unauthenticated trader
    trader_unauth = KalshiTrader()
    trader_unauth._authenticated = False
    trader_unauth._private_key_obj = None
    trader_unauth.key_id = None
    res = trader_unauth.place_sports_order("KXNFLGAME-TEST", side="YES", count=1, dry_run=False)
    assert res["success"] is False
    assert "not configured or private key invalid" in res["error"]


def test_place_sports_order_dry_run_simulation():
    """Verify dry_run simulation creates a structured paper fill."""
    trader = KalshiTrader()
    res = trader.place_sports_order(
        ticker="KXNFLGAME-TEST",
        side="yes",
        count=5,
        limit_price_dollars=0.55,
        dry_run=True,
        slippage_buffer_dollars=0.04
    )
    assert res["success"] is True
    assert res["mode"] == "PAPER"
    assert res["ticker"] == "KXNFLGAME-TEST"
    assert res["side"] == "YES"
    assert res["count"] == 5
    assert res["order_id"].startswith("sim_")
    assert res["status"] in ("FILLED (SIMULATED)", "PARTIALLY FILLED (SIMULATED)")
    assert 0.01 <= res["filled_price"] <= 0.99
    assert res["total_cost"] == round(res["filled_price"] * res["count"], 4)


def test_place_sports_order_live_rejection_of_dummy_tickers():
    """Verify live order strictly rejects dummy / synthetic tickers."""
    trader = KalshiTrader()
    trader._authenticated = True
    trader.key_id = "test-key-id"
    trader.private_key = MagicMock()

    # Reject non-KX ticker
    res = trader.place_sports_order("KALSHI-NFL-LIONS-MKT", side="yes", count=1, dry_run=False)
    assert res["success"] is False
    assert "Cannot execute live order on synthetic or non-Kalshi ticker" in res["error"]

    # Reject synthetic ticker
    res = trader.place_sports_order("KXNFLGAME-TEST_SYNTH", side="yes", count=1, dry_run=False)
    assert res["success"] is False
    assert "synthetic" in res["error"]


def test_place_sports_order_live_insufficient_balance():
    """Verify live order fails closed if Kalshi balance is less than required."""
    trader = KalshiTrader()
    trader._authenticated = True
    trader.key_id = "test-key-id"
    trader.private_key = MagicMock()

    with patch.object(trader, "get_balance", return_value={"success": True, "balance_dollars": 2.00, "raw": {}}):
        with patch.object(trader, "get_market_quote", return_value={"success": True, "market": {"yes_ask_dollars": "0.50"}}):
            res = trader.place_sports_order(GAME_TICKER, side="yes", count=10, limit_price_dollars=0.50, dry_run=False)
            assert res["success"] is False
            assert "Insufficient funds" in res["error"]


def test_place_sports_order_live_success():
    """Verify live order successfully signs and submits IOC order to Kalshi."""
    trader = KalshiTrader()
    trader._authenticated = True
    trader.key_id = "test-key-id"
    trader.private_key = MagicMock()

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "order_id": "kalshi-ord-12345",
        "client_order_id": "cid-12345",
        "fill_count": "5.00",
        "average_fill_price": "0.5200"
    }

    with patch.object(trader, "get_balance", return_value={"success": True, "balance_dollars": 100.00, "raw": {}}):
        with patch.object(trader, "get_market_quote", return_value={"success": True, "market": {"yes_ask_dollars": "0.50"}}):
            with patch.object(trader, "get_positions", return_value={"success": True, "positions": []}):
                with patch.object(trader, "_sign_headers", return_value={"KALSHI-ACCESS-KEY": "test"}):
                    with patch.object(trader.order_session, "post", return_value=mock_resp) as mock_post:
                        res = trader.place_sports_order(
                            ticker=GAME_TICKER,
                            side="yes",
                            count=5,
                            limit_price_dollars=0.50,
                            dry_run=False
                        )
                        assert res["success"] is True
                        assert res["mode"] == "LIVE"
                        assert res["order_id"] == "kalshi-ord-12345"
                        assert res["count"] == 5.0
                        assert res["filled_price"] == 0.52
                        assert mock_post.called
                        call_kwargs = mock_post.call_args[1]
                        payload = call_kwargs["json"]
                        assert payload["ticker"] == GAME_TICKER
                        assert payload["side"] == "bid"
                        assert payload["time_in_force"] == "immediate_or_cancel"


# ═════════════════════════════════════════════════════════════════════════════
# 2. _execute_sports_trade & Route Logic Tests
# ═════════════════════════════════════════════════════════════════════════════

def test_execute_sports_trade_paper_mode():
    """Verify User in PAPER mode deducts paper balance and inserts paper trade."""
    user = get_user_by_id(1)
    assert user is not None

    orig_mode = user.get("trading_mode", "PAPER")
    conn = get_db_connection()
    conn.execute("UPDATE users SET trading_mode = 'PAPER', paper_balance = 500.0 WHERE id = 1")
    conn.commit()
    conn.close()

    created_trade_id = None
    try:
        with patch("backend.routes.engine.requests.get", side_effect=fake_kalshi_get):
            pred = {"predicted_team": "Dallas Cowboys", "confidence_pct": 80.0, "edge_pct": 5.0, "sport": "NFL"}
            trade, err = _execute_sports_trade(GAME_TICKER, pred, user_id=1, trade_size=10.0)

            assert err is None
            assert trade is not None
            created_trade_id = trade["id"]
            assert trade["mode"] == "PAPER"
            assert trade["sport"] == "NFL"
            assert trade["team"] == "Dallas Cowboys"
            assert trade["status"] == "OPEN"
            assert trade["cost"] > 0

            # Verify balance deduction in db
            updated_user = get_user_by_id(1)
            assert updated_user["paper_balance"] < 500.0

            # Verify in DB
            conn = get_db_connection()
            row = conn.execute("SELECT * FROM trades WHERE id = ?", (created_trade_id,)).fetchone()
            conn.close()
            assert row is not None
    finally:
        conn = get_db_connection()
        if created_trade_id:
            conn.execute("DELETE FROM trades WHERE id = ?", (created_trade_id,))
        conn.execute("UPDATE users SET trading_mode = ?, paper_balance = ? WHERE id = 1", (orig_mode, user.get("paper_balance", 100.0)))
        conn.commit()
        conn.close()


def test_execute_sports_trade_live_guards_and_execution():
    """Verify User in LIVE mode: rejects missing keys, rejects dummy tickers."""
    conn = get_db_connection()
    conn.execute("UPDATE users SET trading_mode = 'LIVE', kalshi_key_id = NULL, kalshi_priv_key_encrypted = NULL WHERE id = 1")
    conn.commit()
    conn.close()

    try:
        with patch("backend.routes.engine.requests.get", side_effect=fake_kalshi_get):
            pred = {"predicted_team": "Dallas Cowboys", "confidence_pct": 80.0, "edge_pct": 5.0, "sport": "NFL"}
            trade, err = _execute_sports_trade(GAME_TICKER, pred, user_id=1, trade_size=10.0)
            assert trade is None
            assert "User is in LIVE mode but has no valid Kalshi API keys" in err

        # Reject dummy ticker in LIVE mode
        trade, err = _execute_sports_trade("KALSHI-NFL-TEST-MKT", pred, user_id=1, trade_size=10.0)
        assert trade is None
        assert "Cannot place live order on non-Kalshi ticker" in err
    finally:
        conn = get_db_connection()
        conn.execute("UPDATE users SET trading_mode = 'PAPER' WHERE id = 1")
        conn.commit()
        conn.close()


def test_execute_sports_trade_live_mocked_success():
    """Verify User in LIVE mode with authenticated trader successfully inserts live trade."""
    conn = get_db_connection()
    conn.execute("UPDATE users SET trading_mode = 'LIVE', kalshi_key_id = 'test-key', kalshi_priv_key_encrypted = 'dummy' WHERE id = 1")
    conn.commit()
    conn.close()

    mock_trader = MagicMock()
    mock_trader.is_authenticated.return_value = True
    mock_trader.get_balance.return_value = {"success": True, "balance_dollars": 50.00}
    mock_trader.place_sports_order.return_value = {
        "success": True,
        "mode": "LIVE",
        "order_id": "live-ord-abc-777",
        "client_order_id": "cid-777",
        "filled_price": 0.54,
        "count": 18,
        "total_cost": 9.72
    }

    created_trade_id = None
    try:
        with patch("backend.routes.engine.requests.get", side_effect=fake_kalshi_get):
            with patch("backend.btc.kalshi_trader.get_authenticated_trader_for_user", return_value=mock_trader):
                pred = {"predicted_team": "Dallas Cowboys", "confidence_pct": 82.0, "edge_pct": 6.0, "sport": "NFL"}
                trade, err = _execute_sports_trade(GAME_TICKER, pred, user_id=1, trade_size=10.0)

                assert err is None
                assert trade is not None
                created_trade_id = trade["id"]
                assert trade["id"] == "live-ord-abc-777"
                assert trade["mode"] == "LIVE"
                assert trade["entry_price"] == 0.54
                assert trade["count"] == 18
                assert trade["cost"] == 9.72

                # Verify in DB
                conn = get_db_connection()
                row = conn.execute("SELECT * FROM trades WHERE id = ?", (created_trade_id,)).fetchone()
                conn.close()
                assert row is not None
                assert row["mode"] == "LIVE"
    finally:
        conn = get_db_connection()
        if created_trade_id:
            conn.execute("DELETE FROM trades WHERE id = ?", (created_trade_id,))
        conn.execute("UPDATE users SET trading_mode = 'PAPER' WHERE id = 1")
        conn.commit()
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# 3. HTTP Endpoints (/manual, /slip/submit, /execute, /combo)
# ═════════════════════════════════════════════════════════════════════════════

def test_endpoint_sports_trade_manual(client):
    """Verify /api/engine/sports/trade/manual endpoint with JSON body and query parameters."""
    user = get_user_by_id(1)
    token = create_jwt_token(user["id"], user["username"])
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Test missing ticker returns 400
    res = client.post("/api/engine/sports/trade/manual", headers=headers, json={})
    assert res.status_code == 400
    assert "Missing event or market ticker" in res.json().get("error", "")

    # Test execution with mocked _execute_sports_trade
    mock_trade = {
        "id": "trade-manual-1",
        "ticker": "KXKBOGAME-TEST-DOO",
        "mode": "PAPER",
        "side": "YES",
        "team": "Doosan Bears",
        "cost": 10.0
    }
    with patch("backend.routes.engine._execute_sports_trade", return_value=(mock_trade, None)):
        # POST JSON
        res = client.post(
            "/api/engine/sports/trade/manual",
            headers=headers,
            json={"ticker": "KXKBOGAME-TEST-DOO", "direction": "YES", "amount_dollars": 10.0, "team": "Doosan Bears"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert data.get("executed") is True
        assert data.get("trade_id") == "trade-manual-1"

        # GET Query params
        res_get = client.get(
            "/api/engine/sports/trade/manual?ticker=KXKBOGAME-TEST-DOO&side=YES&trade_size=10.0",
            headers=headers
        )
        assert res_get.status_code == 200
        assert res_get.json().get("status") == "ok"


def test_endpoint_sports_slip_submit(client):
    """Verify /api/engine/sports/slip/submit endpoint for multi-leg trade slips."""
    user = get_user_by_id(1)
    token = create_jwt_token(user["id"], user["username"])
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Test empty slip returns 400
    res = client.post("/api/engine/sports/slip/submit", headers=headers, json={"items": []})
    assert res.status_code == 400
    assert "No items provided" in res.json().get("error", "")

    # Test multi-item slip
    mock_trade1 = {"id": "slip-leg-1", "ticker": "KXNFLGAME-1", "mode": "PAPER", "cost": 15.0}
    mock_trade2 = {"id": "slip-leg-2", "ticker": "KXNFLGAME-2", "mode": "PAPER", "cost": 15.0}

    with patch("backend.routes.engine._execute_sports_trade", side_effect=[(mock_trade1, None), (mock_trade2, None)]):
        payload = {
            "items": [
                {"ticker": "KXNFLGAME-1", "direction": "YES", "trade_size": 15.0, "team": "Chiefs"},
                {"ticker": "KXNFLGAME-2", "direction": "YES", "trade_size": 15.0, "team": "Lions"}
            ]
        }
        res = client.post("/api/engine/sports/slip/submit", headers=headers, json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert data.get("executed_count") == 2
        assert len(data.get("trades")) == 2


# ═════════════════════════════════════════════════════════════════════════════
# 4. SportsBridgeExecutor Safeguards & Execution
# ═════════════════════════════════════════════════════════════════════════════

def test_sports_bridge_executor_safeguards():
    """Verify SportsBridgeExecutor safeguards: edge, max wager cap, corridor, daily limits."""
    executor = SportsBridgeExecutor()

    # User configured with LIVE mode
    user_conf = {
        "id": 1,
        "ai_enabled": 1,
        "trading_mode": "LIVE",
        "trading_universe": "SPORTS",
        "min_sports_confidence": 60.0,
        "min_sports_edge": 3.0,
        "sports_max_wager": 25.0,
        "sports_min_price": 0.20,
        "sports_max_price": 0.80,
        "sports_max_daily_trades": 5,
        "sports_max_daily_risk": 100.0,
        "sports_active_leagues": "NFL",
        "sports_market_types": "GAME"
    }

    # Low edge prediction (0.5% < 1.0% minimum safeguard)
    low_edge_pred = {
        "sport": "NFL",
        "predicted_team": "Packers",
        "confidence_pct": 65.0,
        "edge_pct": 0.5,
        "metadata": {"is_upcoming": True, "date": GAME_DATE}
    }

    mock_trader = MagicMock()
    mock_trader.is_authenticated.return_value = True
    mock_trader.get_balance.return_value = {"success": True, "balance_dollars": 100.0}

    with patch("backend.sports_bridge.executor._generate_kalshi_market", return_value=(GAME_TICKER_GB, 0.50, "Packers Win")):
        with patch.object(executor.client, "fetch_latest_picks", return_value=[low_edge_pred]):
            with patch("backend.sports_bridge.executor.get_all_active_users", return_value=[user_conf]):
                with patch("backend.btc.kalshi_trader.get_authenticated_trader_for_user", return_value=mock_trader):
                    executor.last_check = 0
                    executor.run_cycle()
                    # Trader place_sports_order was never called due to min edge safeguard
                    assert not mock_trader.place_sports_order.called


def test_sports_bridge_executor_live_trade_safeguards():
    """Verify SportsBridgeExecutor executes LIVE trades with real tickers and respects balance."""
    executor = SportsBridgeExecutor()

    user_conf = {
        "id": 1,
        "ai_enabled": 1,
        "trading_mode": "LIVE",
        "trading_universe": "SPORTS",
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

    from datetime import datetime
    from zoneinfo import ZoneInfo
    today_code = datetime.now(ZoneInfo("America/New_York")).strftime("%y%b%d").upper()
    good_pred = {
        "sport": "NFL",
        "predicted_team": "Packers",
        "confidence_pct": 75.0,
        "edge_pct": 5.0,
        "metadata": {"is_upcoming": True, "date": today_code}
    }

    mock_trader = MagicMock()
    mock_trader.is_authenticated.return_value = True
    mock_trader.get_balance.return_value = {"success": True, "balance_dollars": 100.0}
    mock_trader.place_sports_order.return_value = {
        "success": True,
        "mode": "LIVE",
        "order_id": "auto-live-999",
        "filled_price": 0.50,
        "count": 40,
        "total_cost": 20.0
    }

    test_ticker = f"KXNFLGAME-{today_code}GB-GB"
    with patch("backend.sports_bridge.executor._generate_kalshi_market", return_value=(test_ticker, 0.50, "Packers Win")):
        with patch.object(executor.client, "fetch_latest_picks", return_value=[good_pred]):
            with patch("backend.sports_bridge.executor.get_all_active_users", return_value=[user_conf]):
                with patch("backend.btc.kalshi_trader.get_authenticated_trader_for_user", return_value=mock_trader):
                    executor.last_check = 0
                    executor.run_cycle()

                    assert mock_trader.place_sports_order.called
                    call_kwargs = mock_trader.place_sports_order.call_args[1]
                    assert call_kwargs["ticker"] == test_ticker
                    assert call_kwargs["dry_run"] is False

                    # Clean up trade from store
                    conn = get_db_connection()
                    conn.execute("DELETE FROM trades WHERE id = 'auto-live-999'")
                    conn.commit()
                    conn.close()


def test_execute_sports_trade_synthetic_paper_ticker():
    """Verify synthetic KALSHI-... ticker executes cleanly in PAPER mode without UnboundLocalError."""
    pred = {"predicted_team": "Chiefs", "confidence_pct": 75.0, "edge_pct": 5.0, "sport": "NFL", "limit_price": 0.50}
    trade, err = _execute_sports_trade("KALSHI-NFL-KC-261006", pred, user_id=1, trade_size=10.0)
    assert err is None
    assert trade is not None
    assert trade["mode"] == "PAPER"
    assert trade["ticker"] == "KALSHI-NFL-KC-261006"
    assert trade["entry_price"] == 0.50
    assert trade["count"] == 20
    assert trade["cost"] == 10.0

    # Clean up
    conn = get_db_connection()
    conn.execute("DELETE FROM trades WHERE id = ?", (trade["id"],))
    conn.commit()
    conn.close()


def test_sports_bridge_live_take_profit_close(monkeypatch):
    """Verify SportsBridgeExecutor._settle_open_trades calls close_position with purchased_side and estimated_exit_price."""
    executor = SportsBridgeExecutor()
    trade_id = f"test_tp_live_{uuid.uuid4().hex[:8]}"

    live_trade = {
        "id": trade_id,
        "user_id": 1,
        "ticker": GAME_TICKER,
        "side": "YES",
        "entry_price": 0.40,
        "count": 25,
        "cost": 10.0,
        "pnl": 0.0,
        "status": "OPEN",
        "mode": "LIVE",
        "trading_style": "SPORTS_AI"
    }

    TradeStore.insert_trade(1, live_trade)

    mock_trader = MagicMock()
    mock_trader.is_authenticated.return_value = True
    mock_trader.close_position.return_value = {
        "success": True,
        "mode": "LIVE",
        "exit_price": 0.65,
        "filled_count": 25,
        "order_id": "tp-close-ord-1"
    }

    user = {
        "id": 1,
        "trading_mode": "LIVE",
        "sports_tp_enabled": 1,
        "sports_tp_pct": 30.0,
        "kalshi_key_id": "test-key",
        "kalshi_priv_key_encrypted": "test-priv"
    }

    # Market is active at 0.65 (gain = (0.65 - 0.40) / 0.40 = 62.5% > 30% tp_pct)
    monkeypatch.setattr(
        "backend.sports_bridge.executor._check_kalshi_settlement",
        lambda ticker: {"status": "open", "result": None, "cur_price": 0.65}
    )
    monkeypatch.setattr(
        "backend.btc.kalshi_trader.get_authenticated_trader_for_user",
        lambda u: mock_trader
    )

    try:
        executor._settle_open_trades(user)

        assert mock_trader.close_position.called
        call_kwargs = mock_trader.close_position.call_args[1]
        assert call_kwargs["ticker"] == GAME_TICKER
        assert call_kwargs["purchased_side"] == "YES"
        assert call_kwargs["count"] == 25
        assert call_kwargs["dry_run"] is False
        assert call_kwargs["estimated_exit_price"] == 0.65

        settled = TradeStore.get_trade_by_id(trade_id)
        assert settled["status"] == "CLOSED"
        assert settled["exit_price"] == 0.65
        from backend.btc.fees import net_pnl
        assert settled["pnl"] == net_pnl(0.40, 0.65, 25)  # net of entry + exit fees
        assert "TAKE_PROFIT" in settled["exit_reason"]
    finally:
        conn = get_db_connection()
        conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        conn.commit()
        conn.close()


def test_execute_sports_trade_closed_market_rejection_live():
    """Verify LIVE mode rejects placing orders on closed or settled markets."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "market": {
            "ticker": "KXNFLGAME-CLOSED-MKT",
            "status": "closed",
            "yes_ask_dollars": "0.50"
        }
    }

    mock_event_resp = MagicMock()
    mock_event_resp.status_code = 404

    def mock_get(url, *args, **kwargs):
        if "/events/" in url:
            return mock_event_resp
        return mock_resp

    conn = get_db_connection()
    conn.execute("UPDATE users SET trading_mode = 'LIVE', kalshi_key_id = 'k', kalshi_priv_key_encrypted = 'p' WHERE id = 1")
    conn.commit()
    conn.close()

    try:
        with patch("backend.routes.engine.requests.get", side_effect=mock_get):
            pred = {"predicted_team": "YES", "confidence_pct": 80.0, "edge_pct": 5.0}
            trade, err = _execute_sports_trade("KXNFLGAME-CLOSED-MKT", pred, user_id=1, trade_size=10.0)
            assert trade is None
            assert "cannot place live order on closed market" in err
    finally:
        conn = get_db_connection()
        conn.execute("UPDATE users SET trading_mode = 'PAPER' WHERE id = 1")
        conn.commit()
        conn.close()


def test_resolve_user_id_prioritizes_admin_live():
    """Verify fallback resolution selects User 7 (admin, LIVE, SPORTS) over User 2 (user, PAPER, SPORTS)."""
    mock_users = [
        {"id": 2, "username": "IppoLang60", "role": "user", "trading_mode": "PAPER", "trading_universe": "SPORTS"},
        {"id": 4, "username": "Prep109", "role": "user", "trading_mode": "PAPER", "trading_universe": "FINANCIAL"},
        {"id": 7, "username": "Vill3.G", "role": "admin", "trading_mode": "LIVE", "trading_universe": "SPORTS"}
    ]
    with patch("backend.database.models.get_all_active_users", return_value=mock_users):
        uid = _resolve_user_id(None, None)
        assert uid == 7

    # When no users exist, default is 7
    with patch("backend.database.models.get_all_active_users", return_value=[]):
        assert _resolve_user_id(None, None) == 7


def test_resolve_user_id_from_request_sources():
    """Verify resolution extracts user_id from query params, X-User-Id header, and explicit user_id."""
    from starlette.requests import Request
    # 1. Explicit user_id
    assert _resolve_user_id(42, None) == 42
    
    # 2. Query param
    req_qp = Request(scope={"type": "http", "query_string": b"user_id=5", "headers": []})
    assert _resolve_user_id(None, req_qp) == 5

    # 3. Header
    req_hdr = Request(scope={"type": "http", "query_string": b"", "headers": [(b"x-user-id", b"205")]})
    assert _resolve_user_id(None, req_hdr) == 205


def test_parse_trade_timestamp_formats():
    """Verify _parse_trade_timestamp handles ISO strings, SQLite strings, datetime objects, and numeric timestamps."""
    from datetime import datetime, timezone
    now = time.time()
    
    # Numeric
    assert _parse_trade_timestamp(now) == now
    assert _parse_trade_timestamp(1234567890) == 1234567890.0

    # ISO string
    iso_str = "2026-10-06T03:00:00Z"
    parsed_iso = _parse_trade_timestamp(iso_str)
    assert parsed_iso > 1700000000

    # SQLite string
    sql_str = "2026-10-06 03:00:00"
    parsed_sql = _parse_trade_timestamp(sql_str)
    assert parsed_sql > 1700000000

    # Datetime object
    dt = datetime(2026, 10, 6, 3, 0, 0, tzinfo=timezone.utc)
    assert _parse_trade_timestamp(dt) == dt.timestamp()

    # None / empty / invalid
    assert _parse_trade_timestamp(None) == 0.0
    assert _parse_trade_timestamp("invalid") == 0.0


def test_place_sports_order_auto_transfer_shard():
    """Verify that when target_ex != 0 and shard balance is insufficient, funds are auto-transferred from Exchange 0."""
    trader = KalshiTrader()
    trader._authenticated = True
    trader.key_id = "test-key-id"
    trader.private_key = MagicMock()

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "order_id": "ord-shard-3",
        "client_order_id": "cid-shard-3",
        "fill_count": "2.00",
        "average_fill_price": "0.5500"
    }

    quote_data = {
        "success": True,
        "market": {
            "ticker": "KXNPBGAME-26OCT060500HIRHAN-HAN",
            "exchange_index": 3,
            "yes_ask_dollars": "0.55"
        }
    }

    bal_data = {
        "success": True,
        "balance_dollars": 10.00,
        "raw": {
            "balance": 100000,
            "balance_breakdown": [
                {"exchange_index": 0, "balance": 10.00},
                {"exchange_index": 3, "balance": 0.00}
            ]
        }
    }

    with patch.object(trader, "get_market_quote", return_value=quote_data):
        with patch.object(trader, "get_balance", return_value=bal_data):
            with patch.object(trader, "transfer_between_exchanges", return_value={"success": True, "transfer_id": "tx-123"}) as mock_transfer:
                with patch.object(trader, "get_positions", return_value={"success": True, "positions": []}):
                    with patch.object(trader, "_sign_headers", return_value={"KALSHI-ACCESS-KEY": "test"}):
                        with patch.object(trader.order_session, "post", return_value=mock_resp):
                            res = trader.place_sports_order(
                                ticker="KXNPBGAME-26OCT060500HIRHAN-HAN",
                                side="yes",
                                count=2,
                                limit_price_dollars=0.55,
                                dry_run=False
                            )
                            assert res["success"] is True
                            assert mock_transfer.called
                            transfer_args = mock_transfer.call_args[1]
                            assert transfer_args["source_exchange"] == 0
                            assert transfer_args["destination_exchange"] == 3
                            assert transfer_args["amount_dollars"] > 0


def test_place_sports_order_event_fallback_resolution():
    """Verify that passing an event ticker automatically resolves to the open market ticker."""
    trader = KalshiTrader()
    trader._authenticated = True
    trader.key_id = "test-key-id"
    trader.private_key = MagicMock()

    mock_ev_resp = MagicMock()
    mock_ev_resp.status_code = 200
    mock_ev_resp.json.return_value = {
        "event": {
            "ticker": "KXATPMATCH-26OCT05BELMUL",
            "markets": [
                {"ticker": "KXATPMATCH-26OCT05BELMUL-BEL", "status": "active", "yes_ask_dollars": "0.60", "exchange_index": 3}
            ]
        }
    }

    def mock_market_quote(tk):
        if tk == "KXATPMATCH-26OCT05BELMUL":
            return {"success": False, "error": "HTTP 404: Not found"}
        return {
            "success": True,
            "market": {
                "ticker": "KXATPMATCH-26OCT05BELMUL-BEL",
                "status": "active",
                "yes_ask_dollars": "0.60",
                "exchange_index": 3
            }
        }

    mock_order_resp = MagicMock()
    mock_order_resp.status_code = 201
    mock_order_resp.json.return_value = {
        "order_id": "ord-tennis-1",
        "client_order_id": "cid-tennis-1",
        "fill_count": "1.00",
        "average_fill_price": "0.6000"
    }

    bal_data = {
        "success": True,
        "balance_dollars": 5.00,
        "raw": {"balance_breakdown": [{"exchange_index": 3, "balance": 5.00}]}
    }

    with patch.object(trader, "get_market_quote", side_effect=mock_market_quote):
        with patch.object(trader.session, "get", return_value=mock_ev_resp):
            with patch.object(trader, "get_balance", return_value=bal_data):
                with patch.object(trader, "get_positions", return_value={"success": True, "positions": []}):
                    with patch.object(trader, "_sign_headers", return_value={"KALSHI-ACCESS-KEY": "test"}):
                        with patch.object(trader.order_session, "post", return_value=mock_order_resp):
                            res = trader.place_sports_order(
                                ticker="KXATPMATCH-26OCT05BELMUL",
                                side="yes",
                                count=1,
                                dry_run=False
                            )
                            assert res["success"] is True
                            assert res["ticker"] == "KXATPMATCH-26OCT05BELMUL-BEL"


def test_combo_execute_returns_errors_on_failures(client):
    """Verify api_sports_combo_execute tracks and returns errors array when legs fail."""
    resp = client.post("/api/engine/sports/combo?event_tickers=INVALID-TICKER-1,INVALID-TICKER-2&teams=TeamA,TeamB&trade_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    assert data["combo_executed"] is False
    assert len(data["errors"]) == 2
    assert data["errors"][0]["ticker"] == "INVALID-TICKER-1"


