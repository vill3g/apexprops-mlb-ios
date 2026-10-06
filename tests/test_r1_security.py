import pytest
from unittest.mock import MagicMock
from starlette.datastructures import Headers
from fastapi.testclient import TestClient

from backend.main import app
from backend.auth.dependencies import _is_local_client
from backend.auth.security import create_jwt_token
from backend.database.models import get_db_connection


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_user():
    """Retrieve or use active user ID 2 from the SQLite database."""
    conn = get_db_connection()
    user = conn.execute("SELECT id, username, is_active FROM users WHERE id = 2").fetchone()
    conn.close()
    assert user is not None, "Test user ID 2 must exist in database"
    return dict(user)


def test_is_local_client_unit():
    """Verify _is_local_client correctly identifies local clients and rejects X-Forwarded-For."""
    # 1. Local loopback without headers -> True
    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.headers = {}
    assert _is_local_client(req) is True

    req.client.host = "localhost"
    assert _is_local_client(req) is True

    req.client.host = "::1"
    assert _is_local_client(req) is True

    req.client.host = "testclient"
    assert _is_local_client(req) is True

    # 2. LAN addresses without headers -> True
    req.client.host = "192.168.1.50"
    assert _is_local_client(req) is True

    req.client.host = "10.0.0.1"
    assert _is_local_client(req) is True

    # 3. Foreign IP without headers -> False
    req.client.host = "203.0.113.195"
    assert _is_local_client(req) is False

    # 4. Localhost with X-Forwarded-For (reverse proxy / ngrok) -> False (case-insensitive)
    req.client.host = "127.0.0.1"
    req.headers = {"X-Forwarded-For": "203.0.113.195"}
    assert _is_local_client(req) is False

    req.headers = {"x-forwarded-for": "203.0.113.195"}
    assert _is_local_client(req) is False

    req.headers = {"X-FORWARDED-FOR": "203.0.113.195"}
    assert _is_local_client(req) is False

    req.headers = {"X-Forwarded-For": ""}
    assert _is_local_client(req) is False

    # 5. LAN with X-Forwarded-For -> False
    req.client.host = "192.168.1.10"
    req.headers = {"X-Forwarded-For": "203.0.113.195"}
    assert _is_local_client(req) is False

    # 6. Starlette Headers object
    req.client.host = "127.0.0.1"
    req.headers = Headers(raw=[(b"x-forwarded-for", b"203.0.113.195")])
    assert _is_local_client(req) is False

    req.headers = Headers(raw=[(b"user-agent", b"pytest")])
    assert _is_local_client(req) is True

    # 7. No client attribute -> False
    req_no_client = MagicMock()
    req_no_client.client = None
    req_no_client.headers = {}
    assert _is_local_client(req_no_client) is False


def test_sports_endpoints_unauthenticated_proxy_returns_401(client):
    """Verify all sports endpoints reject unauthenticated reverse-proxied requests with 401."""
    proxy_headers = {"X-Forwarded-For": "203.0.113.195"}

    endpoints_to_test = [
        ("GET", "/api/engine/sports/events"),
        ("GET", "/api/engine/sports/predict?event_ticker=KXNFL-TEST"),
        ("POST", "/api/engine/sports/predict?event_ticker=KXNFL-TEST"),
        ("GET", "/api/engine/sports/execute?event_ticker=KXNFL-TEST"),
        ("POST", "/api/engine/sports/execute?event_ticker=KXNFL-TEST"),
        ("GET", "/api/engine/sports/combo?event_tickers=KXNFL-TEST"),
        ("POST", "/api/engine/sports/combo?event_tickers=KXNFL-TEST"),
        ("GET", "/api/engine/sports/combo/execute?event_tickers=KXNFL-TEST"),
        ("POST", "/api/engine/sports/combo/execute?event_tickers=KXNFL-TEST"),
        ("GET", "/api/engine/sports/trade/manual"),
        ("POST", "/api/engine/sports/trade/manual"),
        ("POST", "/api/engine/sports/slip/submit"),
    ]

    for method, path in endpoints_to_test:
        if method == "GET":
            res = client.get(path, headers=proxy_headers)
        else:
            res = client.post(path, json={}, headers=proxy_headers)

        assert res.status_code in (401, 403), (
            f"Endpoint {method} {path} should return 401/403 when called with X-Forwarded-For and no auth, "
            f"got {res.status_code}: {res.text}"
        )
        assert res.status_code == 401
        assert res.json().get("detail") == "Login required."


def test_sports_endpoints_authenticated_proxy_succeeds(client, test_user):
    """Verify sports endpoints allow reverse-proxied requests when presenting a valid JWT."""
    token = create_jwt_token(test_user["id"], test_user["username"])
    auth_proxy_headers = {
        "X-Forwarded-For": "203.0.113.195",
        "Authorization": f"Bearer {token}"
    }

    # 1. GET /api/engine/sports/events succeeds (200)
    res = client.get("/api/engine/sports/events?sport=NFL", headers=auth_proxy_headers)
    assert res.status_code == 200, f"Expected 200 OK for authenticated proxy request, got {res.status_code}"
    assert res.json().get("status") == "ok"

    # 2. GET /api/engine/sports/predict with execute=false succeeds
    res = client.get("/api/engine/sports/predict?event_ticker=KXNFL-TEST&execute=false", headers=auth_proxy_headers)
    assert res.status_code in (200, 400), f"Expected non-auth response, got {res.status_code}"
    assert res.status_code != 401
    assert res.status_code != 403

    # 3. POST /api/engine/sports/slip/submit passes auth and reaches validation (e.g. 400 for empty slip)
    res = client.post("/api/engine/sports/slip/submit", json={"items": []}, headers=auth_proxy_headers)
    assert res.status_code == 400, f"Expected 400 for empty slip after passing auth, got {res.status_code}"
    assert "No items provided in trade slip" in res.text


def test_sports_endpoints_disabled_user_returns_403(client):
    """Verify that disabled accounts receive 403 Forbidden even with a valid signed JWT."""
    conn = get_db_connection()
    # Check if a disabled user exists or create a temporary mock/record
    disabled_user = conn.execute("SELECT id, username FROM users WHERE is_active = 0 LIMIT 1").fetchone()
    if not disabled_user:
        # Temporarily create or disable a dummy user
        conn.execute("INSERT OR IGNORE INTO users (id, username, password_hash, is_active) VALUES (9999, 'disabled_test_user', 'hash', 0)")
        conn.commit()
        uid = 9999
        uname = "disabled_test_user"
    else:
        uid = disabled_user["id"]
        uname = disabled_user["username"]
    conn.close()

    try:
        disabled_token = create_jwt_token(uid, uname)
        headers = {
            "X-Forwarded-For": "203.0.113.195",
            "Authorization": f"Bearer {disabled_token}"
        }
        res = client.get("/api/engine/sports/events", headers=headers)
        assert res.status_code == 403, f"Expected 403 Forbidden for disabled user, got {res.status_code}"
        assert "disabled" in res.json().get("detail", "").lower()
    finally:
        conn = get_db_connection()
        conn.execute("DELETE FROM users WHERE id = 9999")
        conn.commit()
        conn.close()


def test_direct_local_client_preserves_access(client):
    """Verify that genuine direct local requests without X-Forwarded-For continue to work."""
    res = client.get("/api/engine/sports/events?sport=NFL")
    assert res.status_code == 200
    assert res.json().get("status") == "ok"
