import os
import json
import tempfile
import shutil
import pytest
from starlette.testclient import TestClient
from unittest.mock import MagicMock, patch

from backend.main import app
import backend.database.models as models
from backend.auth.security import create_jwt_token, encrypt_kalshi_key
from backend.database.trade_store import TradeStore
from backend.btc.fees import net_pnl


def _stored(trade_id):
    """Trades live in SQLite (TradeStore); the JSON history is a legacy mirror."""
    return TradeStore.get_trade_by_id(trade_id)

client = TestClient(app)

@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch):
    temp_dir = tempfile.mkdtemp()
    test_db = os.path.join(temp_dir, "test_users.db")
    test_data = os.path.join(temp_dir, "data")
    os.makedirs(test_data, exist_ok=True)

    monkeypatch.setattr(models, "DB_PATH", test_db)
    monkeypatch.setattr(models, "DATA_DIR", test_data)
    models.init_db()

    yield

    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def test_user():
    username = f"manual_close_user_{os.urandom(4).hex()}"
    user_id = models.create_user(username, "Password123!")

    # Set Kalshi keys and LIVE mode
    enc_priv = encrypt_kalshi_key("dummy_pem")
    conn = models.get_db_connection()
    try:
        conn.execute(
            "UPDATE users SET kalshi_key_id = ?, kalshi_priv_key_encrypted = ?, trading_mode = 'LIVE' WHERE id = ?",
            ("test_key_id", enc_priv, user_id)
        )
        conn.commit()
    finally:
        conn.close()

    user_dir = os.path.join(models.DATA_DIR, "users", str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    hist_path = os.path.join(user_dir, "trades_history.json")

    seed_trades = [
        {
            "id": "live_trade_1",
            "ticker": "KXBTC15M-TEST-1",
            "side": "YES",
            "direction": "YES",
            "count": 5,
            "entry_price": 0.40,
            "status": "OPEN",
            "mode": "LIVE",
            "pnl": 0.0,
            "trading_style": "AUTO",
            "signal_source": "BLEND"
        },
        {
            "id": "paper_trade_1",
            "ticker": "KXBTC15M-TEST-2",
            "side": "NO",
            "direction": "NO",
            "count": 10,
            "entry_price": 0.50,
            "status": "OPEN",
            "mode": "PAPER",
            "pnl": 0.0,
            "trading_style": "SNIPER",
            "signal_source": "RL_DQN"
        }
    ]
    with models.get_user_lock(user_id):
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(seed_trades, f)
    for t in seed_trades:
        TradeStore.insert_trade(user_id, t)

    token = create_jwt_token(user_id, username)
    return {"id": user_id, "username": username, "token": token, "hist_path": hist_path}


def test_live_manual_close_calculates_pnl(test_user):
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    # Mock KalshiTrader close_position returning exit_price 0.70
    mock_kt = MagicMock()
    mock_kt.is_authenticated.return_value = True
    mock_kt.close_position.return_value = {
        "success": True,
        "mode": "LIVE",
        "filled_count": 5.0,
        "exit_price": 0.70
    }

    with patch("backend.auth.security.decrypt_kalshi_key", return_value="dummy_pem"):
        with patch("backend.btc.kalshi_trader.KalshiTrader", return_value=mock_kt):
            resp = client.post("/api/auth/trade/close/live_trade_1", headers=headers)
            assert resp.status_code == 200, resp.text
            res_data = resp.json()
            assert res_data["success"] is True
            # Entry 0.40, Exit 0.70, Count 5 => PnL = (0.70 - 0.40) * 5 = +1.50
            assert res_data["pnl"] == net_pnl(0.40, 0.70, 5)
            assert res_data["exit_price"] == 0.70

    # Verify trades_history.json on disk
    t = _stored("live_trade_1")
    assert t["status"] == "CLOSED"
    assert t.get("exit_reason", t.get("reason")) == "MANUAL_CLOSE"
    assert t["pnl"] == net_pnl(0.40, 0.70, 5)
    assert t["exit_price"] == 0.70


def test_paper_manual_close_calculates_pnl(test_user):
    # Switch user to PAPER mode
    models.update_user_trading_mode(test_user["id"], "PAPER")
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    # Mock get_kalshi_15m_market
    mock_market = {
        "status": "active",
        "ticker": "KXBTC15M-TEST-2",
        "no_bid": 0.65
    }

    with patch("backend.btc.kalshi_client.get_kalshi_15m_market", return_value=mock_market):
        resp = client.post("/api/auth/trade/close/paper_trade_1", headers=headers)
        assert resp.status_code == 200, resp.text
        res_data = resp.json()
        assert res_data["success"] is True
        # Entry 0.50, Exit 0.65, Count 10 => PnL = (0.65 - 0.50) * 10 = +1.50
        assert res_data["pnl"] == net_pnl(0.50, 0.65, 10)
        assert res_data["exit_price"] == 0.65

    t = _stored("paper_trade_1")
    assert t["status"] == "CLOSED"
    assert t.get("exit_reason", t.get("reason")) == "MANUAL_CLOSE"
    assert t["pnl"] == net_pnl(0.50, 0.65, 10)
    assert t["exit_price"] == 0.65


def test_live_close_all_trades_calculates_pnl(test_user):
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    mock_kt = MagicMock()
    mock_kt.is_authenticated.return_value = True
    mock_kt.get_positions.return_value = {
        "success": True,
        "positions": [
            {"ticker": "KXBTC15M-TEST-1", "position_yes": 5, "position_no": 0}
        ]
    }
    mock_kt.close_position.return_value = {
        "success": True,
        "mode": "LIVE",
        "filled_count": 5.0,
        "exit_price": 0.80
    }

    with patch("backend.auth.security.decrypt_kalshi_key", return_value="dummy_pem"):
        with patch("backend.btc.kalshi_trader.KalshiTrader", return_value=mock_kt):
            resp = client.post("/api/auth/trade/close_all", headers=headers)
            assert resp.status_code == 200, resp.text
            res_data = resp.json()
            assert res_data["success"] is True

    t = _stored("live_trade_1")
    assert t["status"] == "CLOSED"
    assert t.get("exit_reason", t.get("reason")) == "MANUAL_CLOSE"
    # Entry 0.40, Exit 0.80, Count 5 => PnL = (0.80 - 0.40) * 5 = +2.00
    assert t["pnl"] == net_pnl(0.40, 0.80, 5)
    assert t["exit_price"] == 0.80

