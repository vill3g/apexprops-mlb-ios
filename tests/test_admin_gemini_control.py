import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.models import get_all_users, get_user_by_id, admin_update_user
from backend.auth.security import create_jwt_token

client = TestClient(app)

def test_admin_gemini_every_interval_control():
    # Fetch test users created by test environment
    users = get_all_users()
    admin_user = next((u for u in users if u.get("role") == "admin"), users[0] if users else None)
    assert admin_user is not None, "No test user found in test DB"

    # Ensure admin role for test
    admin_update_user(admin_user["id"], {"role": "admin"})

    admin_token = create_jwt_token(admin_user["id"], admin_user["username"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Test updating gemini_every_interval_enabled via /api/admin/users/{user_id}/config
    res = client.post(
        f"/api/admin/users/{admin_user['id']}/config",
        headers=headers,
        json={"gemini_every_interval_enabled": True}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True

    user_fresh = get_user_by_id(admin_user["id"])
    assert user_fresh["gemini_every_interval_enabled"] == 1

    # 2. Test fetching /api/admin/users reflects the field
    res_list = client.get("/api/admin/users", headers=headers)
    assert res_list.status_code == 200
    users_data = res_list.json()["users"]
    u_found = next((u for u in users_data if u["id"] == admin_user["id"]), None)
    assert u_found is not None
    assert u_found["gemini_every_interval_enabled"] is True

    # 3. Test quick toggle endpoint /api/admin/users/{user_id}/toggle_gemini
    res_toggle = client.post(
        f"/api/admin/users/{admin_user['id']}/toggle_gemini",
        headers=headers,
        json={"enabled": False}
    )
    assert res_toggle.status_code == 200
    assert res_toggle.json()["gemini_every_interval_enabled"] is False
    user_fresh2 = get_user_by_id(admin_user["id"])
    assert user_fresh2["gemini_every_interval_enabled"] == 0

    # 4. Test batch toggle endpoint /api/admin/users/batch/gemini_every_interval
    res_batch = client.post(
        "/api/admin/users/batch/gemini_every_interval",
        headers=headers,
        json={"enabled": True, "user_ids": [admin_user["id"]]}
    )
    assert res_batch.status_code == 200
    batch_json = res_batch.json()
    assert batch_json["success"] is True
    assert batch_json["updated_count"] >= 1
    user_fresh3 = get_user_by_id(admin_user["id"])
    assert user_fresh3["gemini_every_interval_enabled"] == 1
