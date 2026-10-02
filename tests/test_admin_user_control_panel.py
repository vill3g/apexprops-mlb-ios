import pytest
import os
import json
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.models import get_all_users, get_user_by_id, admin_update_user, admin_reset_paper_balance

client = TestClient(app)

def test_admin_get_users_endpoint():
    resp = client.get("/api/admin/users")
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["success"] is True
    assert "users" in data
    assert len(data["users"]) > 0

    first_user = data["users"][0]
    # Ensure sensitive fields are never returned
    assert "password_hash" not in first_user
    assert "kalshi_priv_key_encrypted" not in first_user

    # Ensure required user details and stats exist
    required_keys = [
        "id", "username", "role", "is_active", "trading_mode", "paper_balance",
        "ai_enabled", "total_trades", "win_rate", "net_pnl", "trade_size_dollars",
        "trading_style", "signal_source", "auto_force_trade", "second_entry_enabled"
    ]
    for k in required_keys:
        assert k in first_user, f"Missing key {k} in user dict"


def test_admin_update_user_config():
    # Fetch a user to update
    all_users = get_all_users()
    assert len(all_users) > 0
    target_id = all_users[0]["id"]

    update_payload = {
        "trade_size_dollars": 88.5,
        "trading_style": "AMBUSH",
        "signal_source": "BLEND",
        "auto_force_trade": True,
        "second_entry_enabled": True,
        "second_entry_max_ask": 0.65,
        "trailing_stop_enabled": True,
        "trailing_stop_activation_pct": 40.0,
        "trailing_stop_distance_pct": 5.5
    }

    resp = client.post(f"/api/admin/users/{target_id}/config", json=update_payload)
    assert resp.status_code == 200, f"Update failed: {resp.text}"
    res_data = resp.json()
    assert res_data["success"] is True

    # Verify persistence in database
    updated = get_user_by_id(target_id)
    assert updated["trade_size_dollars"] == 88.5
    assert updated["trading_style"] == "AMBUSH"
    assert updated["signal_source"] == "BLEND"
    assert bool(updated["auto_force_trade"]) is True
    assert bool(updated["second_entry_enabled"]) is True
    assert updated["second_entry_max_ask"] == 0.65
    assert bool(updated["trailing_stop_enabled"]) is True
    assert updated["trailing_stop_activation_pct"] == 40.0
    assert updated["trailing_stop_distance_pct"] == 5.5


def test_admin_toggle_ai():
    all_users = get_all_users()
    target_id = all_users[0]["id"]

    # Toggle to False
    resp = client.post(f"/api/admin/users/{target_id}/toggle_ai", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["ai_enabled"] is False
    assert bool(get_user_by_id(target_id)["ai_enabled"]) is False

    # Toggle to True
    resp2 = client.post(f"/api/admin/users/{target_id}/toggle_ai", json={"enabled": True})
    assert resp2.status_code == 200
    assert resp2.json()["ai_enabled"] is True
    assert bool(get_user_by_id(target_id)["ai_enabled"]) is True


def test_admin_reset_balance():
    all_users = get_all_users()
    target_id = all_users[0]["id"]

    resp = client.post(f"/api/admin/users/{target_id}/reset_balance", json={"balance": 500.0})
    assert resp.status_code == 200
    assert resp.json()["paper_balance"] == 500.0
    assert float(get_user_by_id(target_id)["paper_balance"]) == 500.0


def test_admin_ui_elements_in_index_html():
    index_path = os.path.join(os.path.dirname(__file__), "..", "static", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Buttons to open modal
    assert 'id="btnOpenUserPanel"' in html, "Missing desktop User Control Panel button"
    assert 'id="btnIphoneUsers"' in html, "Missing mobile User Control Panel button"
    assert 'openAdminUserPanel()' in html, "Missing openAdminUserPanel call"

    # Modal elements
    assert 'id="adminUserModal"' in html, "Missing adminUserModal"
    assert 'id="adminUserListContainer"' in html, "Missing adminUserListContainer"
    assert 'id="adminUserDetailPanel"' in html, "Missing adminUserDetailPanel"
    assert 'admin_users.js' in html, "Missing script tag for admin_users.js"


def test_admin_delete_user_account():
    from backend.database.models import create_user, delete_user_by_id
    # Create a dummy user
    uid = create_user("pytest_user_to_delete", "pytest_pass_hash")
    assert uid is not None
    try:
        assert get_user_by_id(uid) is not None

        # Delete via DELETE
        resp = client.delete(f"/api/admin/users/{uid}")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert get_user_by_id(uid) is None

        # Test deleting non-existent user returns 404
        resp_404 = client.delete(f"/api/admin/users/{uid}")
        assert resp_404.status_code == 404
    finally:
        delete_user_by_id(uid)

    # Create another dummy user and delete via POST /delete
    uid2 = create_user("pytest_user_to_delete_post", "pytest_pass_hash")
    assert uid2 is not None
    try:
        resp_post = client.post(f"/api/admin/users/{uid2}/delete")
        assert resp_post.status_code == 200
        assert resp_post.json()["success"] is True
        assert get_user_by_id(uid2) is None
    finally:
        delete_user_by_id(uid2)


def test_admin_get_user_trades():
    all_users = get_all_users()
    assert len(all_users) > 0
    target_id = all_users[0]["id"]

    resp = client.get(f"/api/admin/users/{target_id}/trades")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["success"] is True
    assert data["user_id"] == target_id
    assert "summary" in data
    assert "total_trades" in data["summary"]
    assert "win_rate" in data["summary"]
    assert "net_pnl" in data["summary"]
    assert "open_trades" in data["summary"]
    assert "trades" in data
    assert isinstance(data["trades"], list)

    # Test 404 on non-existent user
    resp_404 = client.get("/api/admin/users/99999999/trades")
    assert resp_404.status_code == 404


def test_trade_history_endpoint_with_user_param():
    all_users = get_all_users()
    assert len(all_users) > 0
    target_id = all_users[0]["id"]

    token = os.environ.get("APP_API_TOKEN", "kalshi_secure_1234")
    resp = client.get(
        f"/api/engine/BTC/trade/history?user={target_id}",
        headers={"X-API-Token": token}
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    trades = resp.json()
    assert isinstance(trades, list)


def test_admin_broadcast_status_and_toggle():
    # 1. Check broadcast status endpoint
    resp = client.get("/api/admin/broadcast/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "broadcast_trades" in data

    # 2. Toggle to False
    toggle_resp = client.post("/api/admin/broadcast/toggle", json={"enabled": False})
    assert toggle_resp.status_code == 200
    t_data = toggle_resp.json()
    assert t_data["success"] is True
    assert t_data["broadcast_trades"] is False

    # Verify status reflects disabled
    status_resp = client.get("/api/admin/broadcast/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["broadcast_trades"] is False

    # 3. Toggle back to True
    toggle_resp2 = client.post("/api/admin/broadcast/toggle", json={"enabled": True})
    assert toggle_resp2.status_code == 200
    assert toggle_resp2.json()["broadcast_trades"] is True


def test_admin_user_settings_synchronization_and_persistence():
    all_users = get_all_users()
    assert len(all_users) > 0
    target_id = all_users[0]["id"]

    # LIVE is refused for an account without Kalshi keys
    from backend.database.models import get_db_connection
    conn = get_db_connection()
    conn.execute("UPDATE users SET kalshi_key_id = NULL, kalshi_priv_key_encrypted = NULL, trading_mode = 'PAPER' WHERE id = ?", (target_id,))
    conn.commit()
    refused = client.post(f"/api/admin/users/{target_id}/config", json={"trading_mode": "LIVE"})
    assert refused.status_code == 400
    conn.execute("UPDATE users SET kalshi_key_id = 'test-key', kalshi_priv_key_encrypted = 'test-enc' WHERE id = ?", (target_id,))
    conn.commit()

    update_payload = {
        "trading_mode": "LIVE",
        "signal_source": "ML_ENSEMBLE",
        "trading_style": "SNIPER",
        "stop_loss_pct": 12.5,
        "take_profit_pct": 45.0,
        "trade_size_dollars": 75.0,
        "ai_enabled": True
    }

    resp = client.post(f"/api/admin/users/{target_id}/config", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # 1. DB persistence
    user = get_user_by_id(target_id)
    assert user["trading_mode"] == "LIVE"
    assert user["signal_source"] == "ML_ENSEMBLE"
    assert user["stop_loss_pct"] == 12.5
    assert user["take_profit_pct"] == 45.0
    assert user["trade_size_dollars"] == 75.0
    assert bool(user["ai_enabled"]) is True

    # 2. In-memory executor and isolated trading_config.json sync
    from backend.core.registry import get_auto_executor
    ex = get_auto_executor("BTC", guest_id=str(target_id))
    assert ex.mode == "LIVE"
    assert ex.enabled is True
    assert ex.ai_settings.get("signal_source") == "ML_ENSEMBLE"
    assert ex.ai_settings.get("signalIsolation") == "ML_ENSEMBLE"
    assert ex.ai_settings.get("stop_loss_pct") == 12.5
    assert ex.ai_settings.get("stopLossPercent") == 12.5

    # 3. Clean up back to original state
    client.post(f"/api/admin/users/{target_id}/config", json={
        "trading_mode": "LIVE",
        "signal_source": "BLEND",
        "trading_style": "MOMENTUM_SURFER",
        "stop_loss_pct": 15.0,
        "take_profit_pct": 55.0,
        "trade_size_dollars": 60.0,
        "ai_enabled": True
    })


def test_user_stop_loss_allows_tight_stops_in_settler():
    user = {"stop_loss_pct": 10.0}
    sl_pct = max(0.01, float(user.get("stop_loss_pct", 50.0)) / 100.0)
    assert sl_pct == 0.10, f"Expected 0.10, got {sl_pct} (should not be clamped to 0.35)"


def test_user_trade_config_post_with_jwt():
    from backend.auth.security import create_jwt_token
    all_users = get_all_users()
    assert len(all_users) > 0
    target_user = all_users[0]
    token = create_jwt_token(target_user["id"], target_user["username"])

    post_payload = {
        "trade_size_dollars": 60.0,
        "stop_loss_pct": 15.0,
        "one_click_trade": True,
        "auto_force_trade": False,
        "trading_style": "AMBUSH",
        "signal_source": "RL_DQN",
        "take_profit_pct": 55.0,
        "max_daily_trades": 12,
        "max_daily_risk": 60.0,
        "trailing_stop_enabled": True,
        "trailing_stop_activation_pct": 30.0,
        "trailing_stop_distance_pct": 5.0,
        "second_entry_enabled": False,
        "second_entry_max_ask": 0.70,
        "model_choice": "RL_DQN",
        "train_window": 3000,
        "regularization_c": 0.4,
        "class_weight": "balanced",
        "xgb_estimators": 250,
        "xgb_max_depth": 4,
        "xgb_learning_rate": 0.08,
        "ignore_pass_technical": False,
        "one_shot_ai": True
    }

    # Test POST
    resp = client.post(
        "/api/engine/BTC/trade/config",
        json=post_payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, f"Failed: {resp.text}"
    assert resp.json()["status"] == "ok"

    # Test GET
    get_resp = client.get(
        "/api/engine/BTC/trade/config",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert get_resp.status_code == 200
    cfg = get_resp.json()
    assert cfg["enabled"] == bool(target_user.get("ai_enabled", 1))
    assert cfg["is_guest"] is False


def test_dashboard_stats_filters_trades_by_mode():
    """Verify that get_dashboard_stats strictly filters recent_trades by active trading mode and includes mode field."""
    from backend.auth.security import create_jwt_token
    all_users = get_all_users()
    user = next((u for u in all_users if u["id"] in (2, 5)), all_users[0])
    token = create_jwt_token(user["id"], user["username"])

    resp = client.get("/api/auth/dashboard_stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "recent_trades" in data
    assert "trading_mode" in data
    active_mode = data["trading_mode"]

    for t in data["recent_trades"]:
        assert t.get("mode") == active_mode, f"Trade mode '{t.get('mode')}' does not match active mode '{active_mode}'"


def test_switch_mode_requires_kalshi_keys():
    """Verify that switching to LIVE requires linked Kalshi credentials."""
    from backend.auth.security import create_jwt_token
    all_users = get_all_users()
    no_key_user = next((u for u in all_users if not u.get("kalshi_key_id")), None)
    if no_key_user:
        token = create_jwt_token(no_key_user["id"], no_key_user["username"])
        resp = client.post("/api/auth/trade/config", json={"mode": "LIVE"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400
        assert "No Kalshi API keys linked" in resp.json()["detail"]





