import pytest
import os
import json
import datetime
from fastapi.testclient import TestClient
from backend.main import app
from backend.auth.security import create_jwt_token, decode_jwt_token
from backend.database.models import get_all_active_users

client = TestClient(app, follow_redirects=False)

def test_jwt_token_duration_is_90_days():
    """Verify create_jwt_token sets an expiration of 90 days for persistent sessions."""
    active_users = get_all_active_users()
    assert len(active_users) > 0
    user = active_users[0]
    token = create_jwt_token(user["id"], user["username"])
    payload = decode_jwt_token(token)
    assert payload is not None
    assert "exp" in payload
    assert "iat" in payload
    duration_days = (payload["exp"] - payload["iat"]) / (60 * 60 * 24)
    assert round(duration_days) == 90


def test_login_sets_persistent_session_cookie():
    """Verify that logging in sets the saas_token cookie with 90 days max-age."""
    # We test with one of the known users, or create a temporary mock/login test
    active_users = get_all_active_users()
    user = active_users[0]
    token = create_jwt_token(user["id"], user["username"])

    # Test login endpoint response headers
    from backend.auth.routes import login, LoginRequest
    from starlette.responses import Response

    res = Response()
    # Mock verify password or test via TestClient if password is known
    # Or directly invoke the route function with a mock
    from unittest.mock import patch
    with patch("backend.auth.routes.verify_password", return_value=True):
        req = LoginRequest(username=user["username"], password="any_password")
        login_res = login(req, response=res)
        assert login_res["success"] is True
        assert "saas_token" in res.headers.get("set-cookie", "")
        assert "Max-Age=7776000" in res.headers.get("set-cookie", "") or "max-age=7776000" in res.headers.get("set-cookie", "").lower()


def test_auth_me_supports_cookie_authentication():
    """Verify /api/auth/me authenticates via saas_token cookie without Bearer header."""
    active_users = get_all_active_users()
    user = active_users[0]
    token = create_jwt_token(user["id"], user["username"])

    # Call with cookie only
    resp = client.get("/api/auth/me", cookies={"saas_token": token})
    assert resp.status_code == 200, f"Expected 200 OK via cookie, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["success"] is True
    assert data["user_id"] == user["id"]
    assert data["username"] == user["username"]


@pytest.mark.skip()
def test_root_redirects_to_dashboard_when_cookie_present():
    """Verify navigating to '/' auto-redirects to /saas_dashboard.html if session cookie exists."""
    active_users = get_all_active_users()
    user = active_users[0]
    token = create_jwt_token(user["id"], user["username"])

    # With cookie: should 302 to /saas_dashboard.html
    resp = client.get("/", cookies={"saas_token": token})
    assert resp.status_code == 302
    assert resp.headers["location"] == "/saas_dashboard.html"


@pytest.mark.skip()
def test_root_redirects_to_login_when_no_cookie():
    """Verify navigating to '/' redirects to /login.html when not logged in."""
    resp = client.get("/")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login.html"


@pytest.mark.skip()
def test_login_page_redirects_to_dashboard_when_cookie_present():
    """Verify visiting /login.html directly auto-forwards to /saas_dashboard.html if already logged in."""
    active_users = get_all_active_users()
    user = active_users[0]
    token = create_jwt_token(user["id"], user["username"])

    resp = client.get("/login.html", cookies={"saas_token": token})
    assert resp.status_code == 302
    assert resp.headers["location"] == "/saas_dashboard.html"


def test_login_page_serves_html_when_no_cookie():
    """Verify visiting /login.html serves the login page when no session exists."""
    resp = client.get("/login.html")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Login" in resp.text
    # Verify client-side auto-resume logic is present
    assert "checkExistingSession" in resp.text
    assert "setTokenCookie" in resp.text


def test_logout_endpoint_clears_cookie():
    """Verify /api/auth/logout deletes the saas_token cookie."""
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert "saas_token" in set_cookie
    # Deleting cookie sets max-age=0 or expires in the past
    assert 'max-age=0' in set_cookie.lower() or 'expires=' in set_cookie.lower()


def test_saas_dashboard_contains_session_persistence_handlers():
    """Verify static/saas_dashboard.html includes synchronized cookie and localStorage handlers."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "..", "static", "saas_dashboard.html")
    with open(dashboard_path, "r", encoding="utf-8") as f:
        html = f.read()
    # UI logic lives in static/js/dashboard.js (loaded by the page)
    with open(os.path.join(os.path.dirname(__file__), "..", "static", "js", "dashboard.js"), "r", encoding="utf-8") as f:
        html += f.read()

    assert "getCookie('saas_token')" in html
    assert "setTokenCookie(token)" in html
    assert "saas_token=; path=/; expires=Thu, 01 Jan 1970" in html


def test_login_page_has_admin_switch_button():
    """Verify login page includes switch to admin login button and controls."""
    resp = client.get("/login.html")
    assert resp.status_code == 200
    assert "switch-admin-btn" in resp.text
    assert "Switch to Admin Login" in resp.text
    assert "toggleAdminMode" in resp.text
    assert "admin-token" in resp.text


def test_login_alias_serves_page():
    """Verify /login serves the same page as /login.html."""
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "Switch to Admin Login" in resp.text


def test_login_admin_mode_bypasses_dashboard_redirect():
    """Verify ?mode=admin serves login page without 302 redirecting to dashboard even with cookie."""
    active_users = get_all_active_users()
    user = active_users[0]
    token = create_jwt_token(user["id"], user["username"])

    resp = client.get("/login.html?mode=admin", cookies={"saas_token": token})
    assert resp.status_code == 200
    assert "Switch to Admin Login" in resp.text


def test_admin_verify_endpoint():
    """Verify /api/admin/verify returns 200 for localhost / LAN."""
    resp = client.post("/api/admin/verify")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


