import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.database.models import (
    get_db_connection,
    update_user_trading_universe,
    update_user_config
)
from backend.auth.security import create_jwt_token


@pytest.fixture
def client():
    return TestClient(app)


def test_sports_toggle_preserves_both_universe(client):
    """Verify toggling sports auto-trading (ON and OFF) preserves 'BOTH' in DB and does not overwrite it."""
    conn = get_db_connection()
    user = conn.execute("SELECT id, username, trading_universe, ai_enabled FROM users WHERE id = 1").fetchone()
    conn.close()
    orig_universe = user["trading_universe"]
    orig_ai = user["ai_enabled"]

    token = create_jwt_token(user["id"], user["username"])
    headers = {"Authorization": f"Bearer {token}"}

    try:
        # 1. Set to BOTH
        update_user_trading_universe(user["id"], "BOTH")

        conn = get_db_connection()
        row = conn.execute("SELECT trading_universe FROM users WHERE id = ?", (user["id"],)).fetchone()
        conn.close()
        assert row["trading_universe"] == "BOTH"

        # 2. Toggle sports ON
        res_on = client.post("/api/engine/sports/trade/toggle?enabled=true", headers=headers)
        assert res_on.status_code == 200
        assert res_on.json().get("enabled") is True

        conn = get_db_connection()
        row_on = conn.execute("SELECT trading_universe, ai_enabled FROM users WHERE id = ?", (user["id"],)).fetchone()
        conn.close()
        assert row_on["trading_universe"] == "BOTH", "Toggling sports ON must not overwrite 'BOTH'"
        assert row_on["ai_enabled"] == 1

        # 3. Toggle sports OFF
        res_off = client.post("/api/engine/sports/trade/toggle?enabled=false", headers=headers)
        assert res_off.status_code == 200
        assert res_off.json().get("enabled") is False

        conn = get_db_connection()
        row_off = conn.execute("SELECT trading_universe, ai_enabled FROM users WHERE id = ?", (user["id"],)).fetchone()
        conn.close()
        assert row_off["trading_universe"] == "BOTH", "Toggling sports OFF must not overwrite 'BOTH'"
        assert row_off["ai_enabled"] == 0

        # Also verify dashboard stats confirms "BOTH"
        stats = client.get("/api/auth/dashboard_stats", headers=headers).json()
        assert stats.get("trading_universe") == "BOTH"

    finally:
        conn = get_db_connection()
        conn.execute("UPDATE users SET trading_universe = ?, ai_enabled = ? WHERE id = ?", 
                     (orig_universe, orig_ai, user["id"]))
        conn.commit()
        conn.close()


def test_financial_trade_config_preserves_both_universe(client):
    """Verify updating financial config via /api/engine/{asset}/trade/config preserves 'BOTH'."""
    conn = get_db_connection()
    user = conn.execute("SELECT id, username, trading_universe, trade_size_dollars FROM users WHERE id = 1").fetchone()
    conn.close()
    orig_universe = user["trading_universe"]
    orig_trade_size = user["trade_size_dollars"]

    token = create_jwt_token(user["id"], user["username"])
    headers = {"Authorization": f"Bearer {token}"}

    try:
        # 1. Set to BOTH
        update_user_trading_universe(user["id"], "BOTH")

        # 2. Post financial config without trading_universe field
        payload = {
            "trade_size_dollars": 42.5,
            "stop_loss_pct": 33.0,
            "trading_style": "SNIPER"
        }
        res = client.post("/api/engine/btc/trade/config", json=payload, headers=headers)
        assert res.status_code == 200
        assert res.json().get("status") == "ok"

        # 3. Check DB state
        conn = get_db_connection()
        row = conn.execute("SELECT trading_universe, trade_size_dollars, stop_loss_pct, trading_style FROM users WHERE id = ?", (user["id"],)).fetchone()
        conn.close()
        assert row["trading_universe"] == "BOTH", "Saving BTC config must preserve 'BOTH' universe in DB"
        assert row["trade_size_dollars"] == 42.5
        assert row["stop_loss_pct"] == 33.0
        assert row["trading_style"] == "SNIPER"

        # Check dashboard stats
        stats = client.get("/api/auth/dashboard_stats", headers=headers).json()
        assert stats.get("trading_universe") == "BOTH"

    finally:
        conn = get_db_connection()
        conn.execute("UPDATE users SET trading_universe = ?, trade_size_dollars = ? WHERE id = ?", 
                     (orig_universe, orig_trade_size, user["id"]))
        conn.commit()
        conn.close()


def test_update_user_config_function_direct_preserves_both():
    """Verify update_user_config() function call with omitted trading_universe preserves existing 'BOTH'."""
    conn = get_db_connection()
    user = conn.execute("SELECT id, trading_universe, trade_size_dollars FROM users WHERE id = 1").fetchone()
    conn.close()
    orig_universe = user["trading_universe"]
    orig_size = user["trade_size_dollars"]

    try:
        # Set to BOTH
        update_user_trading_universe(user["id"], "BOTH")

        # Call update_user_config without trading_universe parameter
        update_user_config(
            user_id=user["id"],
            trade_size_dollars=77.0,
            paper_trade_size_dollars=150.0,
            stop_loss_pct=25.0
        )

        conn = get_db_connection()
        row = conn.execute("SELECT trading_universe, trade_size_dollars FROM users WHERE id = ?", (user["id"],)).fetchone()
        conn.close()
        assert row["trading_universe"] == "BOTH", "update_user_config() must preserve existing 'BOTH' when trading_universe is omitted"
        assert row["trade_size_dollars"] == 77.0

        # Call update_user_config with explicit None
        update_user_config(
            user_id=user["id"],
            trade_size_dollars=88.0,
            paper_trade_size_dollars=150.0,
            stop_loss_pct=25.0,
            trading_universe=None
        )

        conn = get_db_connection()
        row2 = conn.execute("SELECT trading_universe, trade_size_dollars FROM users WHERE id = ?", (user["id"],)).fetchone()
        conn.close()
        assert row2["trading_universe"] == "BOTH", "update_user_config() must preserve existing 'BOTH' when trading_universe=None"
        assert row2["trade_size_dollars"] == 88.0

        # Call update_user_config with explicit 'SPORTS'
        update_user_config(
            user_id=user["id"],
            trade_size_dollars=99.0,
            paper_trade_size_dollars=150.0,
            stop_loss_pct=25.0,
            trading_universe="SPORTS"
        )

        conn = get_db_connection()
        row3 = conn.execute("SELECT trading_universe FROM users WHERE id = ?", (user["id"],)).fetchone()
        conn.close()
        assert row3["trading_universe"] == "SPORTS"

        # Call with invalid universe raises ValueError
        with pytest.raises(ValueError):
            update_user_config(
                user_id=user["id"],
                trade_size_dollars=99.0,
                paper_trade_size_dollars=150.0,
                stop_loss_pct=25.0,
                trading_universe="INVALID_UNIVERSE"
            )

    finally:
        conn = get_db_connection()
        conn.execute("UPDATE users SET trading_universe = ?, trade_size_dollars = ? WHERE id = ?", 
                     (orig_universe, orig_size, user["id"]))
        conn.commit()
        conn.close()
