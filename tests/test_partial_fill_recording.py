"""Regression tests for audit finding H1: LIVE trade records must store the contracts Kalshi
actually filled (IOC orders can fill partially), not the count that was requested - otherwise
P&L and the daily-risk exposure are computed on contracts the user never bought."""
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

import backend.database.models as models
from backend.auth.security import create_jwt_token, encrypt_kalshi_key
from backend.btc.kalshi_trader import filled_count
from backend.database.trade_store import TradeStore
from backend.main import app

client = TestClient(app)


# ── helper ───────────────────────────────────────────────────────────────────

def test_filled_count_uses_the_real_fill():
    assert filled_count({"count": 6.0}, 20) == 6
    assert isinstance(filled_count({"count": 6.0}, 20), int)
    assert filled_count({"count": "3"}, 20) == 3
    assert filled_count({"count": 2.5}, 20) == 2.5


def test_filled_count_falls_back_when_missing_or_invalid():
    assert filled_count({}, 20) == 20
    assert filled_count({"count": None}, 20) == 20
    assert filled_count({"count": "abc"}, 20) == 20
    assert filled_count({"count": 0}, 20) == 20
    assert filled_count(None, 7) == 7


# ── manual LIVE trade endpoint records the partial fill ──────────────────────

@pytest.fixture
def live_user(monkeypatch):
    temp_dir = tempfile.mkdtemp()
    monkeypatch.setattr(models, "DB_PATH", os.path.join(temp_dir, "users.db"))
    monkeypatch.setattr(models, "DATA_DIR", os.path.join(temp_dir, "data"))
    os.makedirs(models.DATA_DIR, exist_ok=True)
    models.init_db()
    user_id = models.create_user(f"partial_fill_{os.urandom(4).hex()}", "Password123!")
    conn = models.get_db_connection()
    conn.execute(
        "UPDATE users SET kalshi_key_id = ?, kalshi_priv_key_encrypted = ?, trading_mode = 'LIVE' WHERE id = ?",
        ("test_key_id", encrypt_kalshi_key("dummy_pem"), user_id),
    )
    conn.commit()
    yield user_id
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_manual_live_trade_records_filled_count_not_requested(live_user):
    close = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    market = {"ticker": "KXBTC15M-PARTIAL", "status": "active", "close_time": close,
              "yes_ask": 0.50, "no_ask": 0.52, "target_price": 80000}
    mock_kt = MagicMock()
    mock_kt.is_authenticated.return_value = True
    mock_kt.get_balance.return_value = {"success": True, "balance_dollars": 1000.0}
    # Asked for ~19 contracts, Kalshi only filled 6.
    mock_kt.place_order.return_value = {"success": True, "count": 6.0, "filled_price": 0.51,
                                        "client_order_id": "cid-partial-1"}

    headers = {"Authorization": f"Bearer {create_jwt_token(live_user, 'partial')}"}
    with patch("backend.btc.kalshi_client.get_kalshi_15m_market", return_value=market), \
         patch("backend.auth.security.decrypt_kalshi_key", return_value="dummy_pem"), \
         patch("backend.btc.kalshi_trader.KalshiTrader", return_value=mock_kt):
        resp = client.post("/api/auth/trade/manual", json={"direction": "YES", "amount_dollars": 10.0},
                           headers=headers)

    assert resp.status_code == 200, resp.text
    requested = mock_kt.place_order.call_args.kwargs["count"]
    assert requested > 6
    stored = TradeStore.get_trade_by_id("cid-partial-1")
    assert stored is not None
    assert float(stored["count"]) == 6
    assert float(stored["entry_price"]) == pytest.approx(0.51)
