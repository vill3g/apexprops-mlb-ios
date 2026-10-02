import pytest
import os
import json
from fastapi.testclient import TestClient
from backend.main import app
from backend.auth.security import create_jwt_token
from backend.database.models import get_all_active_users

client = TestClient(app)

def test_community_leaderboard_endpoint_anonymous():
    """Verify public access to /api/auth/community returns sanitized leaderboard."""
    resp = client.get("/api/auth/community")
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["success"] is True
    assert "summary" in data
    assert "users" in data
    assert len(data["users"]) > 0

    # Verify summary fields
    assert "total_traders" in data["summary"]
    assert "total_trades" in data["summary"]
    assert "community_win_rate" in data["summary"]

    users = data["users"]
    # Verify ranking order: default sorted by net_pnl descending
    for i in range(len(users) - 1):
        assert users[i]["net_pnl"] >= users[i+1]["net_pnl"], "Users must be sorted by net_pnl descending"
        assert users[i]["rank"] == i + 1, f"Rank mismatch at index {i}"

    # Verify data sanitization on every single profile
    for u in users:
        assert "password_hash" not in u
        assert "kalshi_priv_key_encrypted" not in u
        assert "kalshi_key_id" not in u
        assert "is_self" in u
        assert u["is_self"] is False  # Anonymous call has no self

        # Check required fields
        required_fields = [
            "id", "username", "initials", "trading_style", "trading_mode",
            "win_rate", "net_pnl", "total_trades", "wins", "losses", "rank"
        ]
        for field in required_fields:
            assert field in u, f"Missing required field {field} in user {u}"


def test_community_leaderboard_authenticated():
    """Verify that an authenticated user has their profile card flagged with is_self=True."""
    active_users = get_all_active_users()
    assert len(active_users) > 0
    target_user = active_users[0]
    token = create_jwt_token(target_user["id"], target_user["username"])

    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/auth/community", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    self_matches = [u for u in data["users"] if u["is_self"]]
    assert len(self_matches) == 1, "Exactly one user must have is_self=True"
    assert self_matches[0]["id"] == target_user["id"]
    assert self_matches[0]["username"] == target_user["username"]


def test_social_leaderboard_alias_route():
    """Verify /api/social/leaderboard endpoint alias."""
    resp = client.get("/api/social/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "users" in data
    assert len(data["users"]) > 0


def test_saas_dashboard_contains_social_elements():
    """Verify static/saas_dashboard.html includes header icon, modal overlay, and JS handlers."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "..", "static", "saas_dashboard.html")
    with open(dashboard_path, "r", encoding="utf-8") as f:
        html = f.read()
    # UI logic lives in static/js/dashboard.js (loaded by the page)
    with open(os.path.join(os.path.dirname(__file__), "..", "static", "js", "dashboard.js"), "r", encoding="utf-8") as f:
        html += f.read()

    # Header and quick links
    assert 'id="btn-header-social"' in html or 'btn-header-social' in html
    assert 'openSocialModal()' in html
    assert 'id="social-page"' in html

    # Social Leaderboard UI Components
    assert 'id="socialTraderCountText"' in html
    assert 'id="socialYourCard"' in html
    assert 'id="socialSearchInput"' in html
    assert 'id="socialSortPnl"' in html
    assert 'id="socialSortWinRate"' in html
    assert 'id="socialSortTrades"' in html
    assert 'id="socialTradersList"' in html
    assert 'btn-copy-settings-' in html
    assert 'Copy Settings' in html

    # JavaScript logic
    assert 'function openSocialModal()' in html
    assert 'function closeSocialModal()' in html
    assert 'function loadSocialLeaderboard()' in html
    assert 'function renderSocialLeaderboard()' in html
    assert 'async function copyTraderSettings(' in html
    assert "location.hash === '#social'" in html


def test_index_html_contains_social_triggers():
    """Verify static/index.html includes desktop and mobile navigation to the social community."""
    index_path = os.path.join(os.path.dirname(__file__), "..", "static", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    assert 'id="btnTopBarSocial"' in html
    assert 'id="btnIphoneSocial"' in html
    assert 'saas_dashboard.html#social' in html


def test_copy_user_settings_model_logic():
    """Verify that copy_user_settings copies all AI and trading settings while strictly preserving trade size."""
    from backend.database.models import copy_user_settings, update_user_config, get_user_by_id

    active_users = get_all_active_users()
    assert len(active_users) >= 2, "Test requires at least two active users in database"

    user_a = active_users[0]
    user_b = active_users[1]

    # Configure User A with specific distinct strategy settings
    update_user_config(
        user_id=user_a["id"],
        trade_size_dollars=33.0,
        paper_trade_size_dollars=33.0,
        stop_loss_pct=14.0,
        one_click_trade=True,
        auto_force_trade=True,
        trading_style="SNIPER",
        signal_source="TECHNICAL_ONLY",
        take_profit_pct=42.0,
        max_daily_trades=7,
        max_daily_risk=35.0,
        trailing_stop_enabled=True,
        trailing_stop_activation_pct=28.0,
        trailing_stop_distance_pct=4.5,
        second_entry_enabled=True,
        second_entry_max_ask=0.65,
        model_choice="LSTM",
        train_window=2500,
        regularization_c=0.8,
        class_weight="balanced",
        xgb_estimators=150,
        xgb_max_depth=4,
        xgb_learning_rate=0.05,
        ignore_pass_technical=True,
        one_shot_ai=True
    )

    # Configure User B with their own capital trade size ($175.0) and different strategy
    update_user_config(
        user_id=user_b["id"],
        trade_size_dollars=175.0,
        paper_trade_size_dollars=175.0,
        stop_loss_pct=50.0,
        one_click_trade=False,
        auto_force_trade=False,
        trading_style="AUTO",
        signal_source="ML_ENSEMBLE",
        take_profit_pct=50.0,
        model_choice="Swarm"
    )

    # User B copies settings from User A
    res = copy_user_settings(source_user_id=user_a["id"], target_user_id=user_b["id"])
    assert res is not None
    assert res["source_user_id"] == user_a["id"]
    assert res["target_user_id"] == user_b["id"]
    assert res["copied_settings"]["trading_style"] == "SNIPER"
    assert res["copied_settings"]["model_choice"] == "LSTM"
    assert res["copied_settings"]["stop_loss_pct"] == 14.0
    assert res["copied_settings"]["take_profit_pct"] == 42.0

    # Retrieve User B from database and verify all settings were copied EXCEPT trade size
    refreshed_b = get_user_by_id(user_b["id"])
    assert refreshed_b["trade_size_dollars"] == 175.0, "CRITICAL: Trade size dollars must remain untouched!"
    assert refreshed_b["trading_style"] == "SNIPER"
    assert refreshed_b["signal_source"] == "TECHNICAL_ONLY"
    assert refreshed_b["model_choice"] == "LSTM"
    assert refreshed_b["stop_loss_pct"] == 14.0
    assert refreshed_b["take_profit_pct"] == 42.0
    assert refreshed_b["max_daily_trades"] == 7
    assert refreshed_b["trailing_stop_enabled"] == 1
    assert refreshed_b["second_entry_enabled"] == 1
    assert refreshed_b["second_entry_max_ask"] == 0.65

    # Self-copy must raise ValueError
    with pytest.raises(ValueError, match="Cannot copy settings from your own account"):
        copy_user_settings(source_user_id=user_a["id"], target_user_id=user_a["id"])


def test_copy_settings_api_endpoint():
    """Verify POST /api/auth/community/copy_settings/{target_user_id} endpoint."""
    from backend.database.models import get_user_by_id, update_user_config

    active_users = get_all_active_users()
    assert len(active_users) >= 2

    source = active_users[0]
    caller = active_users[1]

    # Set caller's trade size to $88.0
    update_user_config(
        user_id=caller["id"],
        trade_size_dollars=88.0,
        paper_trade_size_dollars=88.0,
        stop_loss_pct=50.0,
        one_click_trade=False,
        trading_style="CHOP",
        signal_source="BLEND"
    )

    caller_token = create_jwt_token(caller["id"], caller["username"])
    headers = {"Authorization": f"Bearer {caller_token}"}

    # Authenticated copy
    resp = client.post(f"/api/auth/community/copy_settings/{source['id']}", headers=headers)
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["success"] is True
    assert "Trade size preserved" in body["message"]

    # Verify caller's trade size is preserved in DB
    refreshed_caller = get_user_by_id(caller["id"])
    assert refreshed_caller["trade_size_dollars"] == 88.0, "Trade size must remain $88.0"


def test_copy_settings_self_copy_and_unauthorized():
    """Verify endpoint rejects self-copy (400) and unauthenticated calls (401)."""
    active_users = get_all_active_users()
    user = active_users[0]
    token = create_jwt_token(user["id"], user["username"])
    headers = {"Authorization": f"Bearer {token}"}

    # Attempting to copy self
    resp = client.post(f"/api/auth/community/copy_settings/{user['id']}", headers=headers)
    assert resp.status_code == 400
    assert "Cannot copy settings from your own account" in resp.json()["detail"]

    # Unauthenticated attempt
    anon_resp = client.post(f"/api/auth/community/copy_settings/{user['id']}")
    assert anon_resp.status_code == 401


