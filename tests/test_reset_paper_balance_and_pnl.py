import os
import json
import tempfile
import shutil
import pytest
from starlette.testclient import TestClient

from backend.main import app
import backend.database.models as models
from backend.auth.security import create_jwt_token

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
def temp_test_user():
    username = f"reset_test_user_{os.urandom(4).hex()}"
    user_id = models.create_user(username, "Password123!")

    # Seed user with paper and live trades
    user_dir = os.path.join(models.DATA_DIR, "users", str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    hist_path = os.path.join(user_dir, "trades_history.json")

    seed_trades = [
        {"id": "paper_t1", "mode": "PAPER", "status": "CLOSED", "pnl": 45.0, "ticker": "KXBTC15M-T1"},
        {"id": "paper_t2", "mode": "PAPER", "status": "CLOSED", "pnl": -20.0, "ticker": "KXBTC15M-T2"},
        {"id": "paper_t3", "mode": "PAPER", "status": "OPEN", "pnl": 0.0, "ticker": "KXBTC15M-T3"},
        {"id": "live_t1", "mode": "LIVE", "status": "CLOSED", "pnl": 150.0, "ticker": "KXBTC15M-LIVE1"}
    ]
    with models.get_user_lock(user_id):
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(seed_trades, f)
    from backend.database.trade_store import TradeStore
    for t in seed_trades:  # SQLite is the source of truth for stats
        TradeStore.insert_trade(user_id, t)

    token = create_jwt_token(user_id, username)

    yield {"id": user_id, "username": username, "token": token, "hist_path": hist_path, "user_dir": user_dir}

    models.delete_user_by_id(user_id)


def test_reset_user_paper_balance_and_pnl_unit(temp_test_user):
    user_id = temp_test_user["id"]
    hist_path = temp_test_user["hist_path"]
    archive_path = os.path.join(temp_test_user["user_dir"], "trades_history_archive.json")

    # Call reset function
    success = models.reset_user_paper_balance_and_pnl(user_id, balance=500.0)
    assert success is True

    # 1. DB paper balance should be 500.0
    u = models.get_user_by_id(user_id)
    assert float(u["paper_balance"]) == 500.0

    # 2. Active trades should contain ONLY the LIVE trade
    with open(hist_path, "r", encoding="utf-8") as f:
        active_trades = json.load(f)
    assert len(active_trades) == 1
    assert active_trades[0]["id"] == "live_t1"
    assert active_trades[0]["mode"] == "LIVE"

    # 3. Archive should contain the 3 paper trades
    assert os.path.exists(archive_path)
    with open(archive_path, "r", encoding="utf-8") as f:
        archived_trades = json.load(f)
    assert len(archived_trades) == 3
    assert any(t["id"] == "paper_t1" for t in archived_trades)
    assert any(t["id"] == "paper_t2" for t in archived_trades)
    assert any(t["id"] == "paper_t3" for t in archived_trades)
    assert "archived_at_reset" in archived_trades[0]


def test_dashboard_stats_pnl_resets_to_zero(temp_test_user):
    token = temp_test_user["token"]

    # Before reset: stats should reflect the +25 net paper PnL (+45 - 20)
    res_before = client.get("/api/auth/dashboard_stats", headers={"Authorization": f"Bearer {token}"})
    assert res_before.status_code == 200
    data_before = res_before.json()
    assert data_before["total_pnl"] == 25.0

    # Reset balance and PnL via user endpoint
    res_reset = client.post("/api/auth/user/reset_paper_balance", headers={"Authorization": f"Bearer {token}"})
    assert res_reset.status_code == 200
    assert res_reset.json()["success"] is True
    assert res_reset.json()["paper_balance"] == 500.0

    # After reset: dashboard stats should show $0.00 total_pnl
    res_after = client.get("/api/auth/dashboard_stats", headers={"Authorization": f"Bearer {token}"})
    assert res_after.status_code == 200
    data_after = res_after.json()
    assert data_after["total_pnl"] == 0.0
    assert data_after["balance_dollars"] == 500.0
    assert data_after["win_rate"] == 0.0 or data_after["win_rate"] == 0


def test_admin_reset_balance_resets_user_pnl(temp_test_user):
    user_id = temp_test_user["id"]
    token = temp_test_user["token"]

    # Verify PnL is non-zero initially (+25)
    res_before = client.get("/api/auth/dashboard_stats", headers={"Authorization": f"Bearer {token}"})
    assert res_before.json()["total_pnl"] == 25.0

    # Reset via Admin endpoint
    resp = client.post(f"/api/admin/users/{user_id}/reset_balance", json={"balance": 500.0})
    assert resp.status_code == 200
    assert resp.json()["paper_balance"] == 500.0

    # User's dashboard PnL should now be reset to $0.00
    res_after = client.get("/api/auth/dashboard_stats", headers={"Authorization": f"Bearer {token}"})
    assert res_after.json()["total_pnl"] == 0.0
    assert res_after.json()["balance_dollars"] == 500.0
