"""A logged-in user may only read their own trade history, never another account's."""
import pytest
from fastapi.testclient import TestClient

from backend.auth.security import create_jwt_token
from backend.database.models import create_user, delete_user_by_id
from backend.main import app

client = TestClient(app)

# TestClient connects as "testclient", which the app treats as the local owner.
# A forwarded-for header marks the request as remote so only the JWT counts.
REMOTE = {"X-Forwarded-For": "203.0.113.7"}


@pytest.fixture
def two_users():
    alice = create_user("pytest_history_alice", "pytest_pass_hash")
    bob = create_user("pytest_history_bob", "pytest_pass_hash")
    try:
        yield alice, bob
    finally:
        delete_user_by_id(alice)
        delete_user_by_id(bob)


def _get(uid, query=""):
    token = create_jwt_token(uid, f"user{uid}")
    return client.get(
        f"/api/engine/BTC/trade/history{query}",
        headers={**REMOTE, "Authorization": f"Bearer {token}"},
    )


@pytest.mark.parametrize("param", ["user", "user_id", "guest"])
def test_user_cannot_read_another_users_history(two_users, param):
    alice, bob = two_users
    resp = _get(alice, f"?{param}={bob}")
    assert resp.status_code == 403, resp.text


def test_user_can_read_own_history(two_users):
    alice, _ = two_users
    assert _get(alice).status_code == 200
    assert _get(alice, f"?user={alice}").status_code == 200


def test_non_owner_cannot_request_all_users(two_users):
    alice, bob = two_users
    resp = _get(alice, "?user=ALL")
    assert resp.status_code == 200
    assert all(t.get("user_id") in (None, alice) for t in resp.json())
