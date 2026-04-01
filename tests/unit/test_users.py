"""Unit tests for User, Group, and Role endpoints.

All endpoints require authentication; tests use ``admin_client`` from conftest.
"""

from __future__ import annotations


def test_create_user_with_persona(admin_client):
    r = admin_client.post(
        "/api/v1/users",
        json={
            "username": "pradeep",
            "email": "pradeep@example.com",
            "display_name": "Pradeep",
            "persona": "ProductOwner",
        },
    )
    assert r.status_code == 201
    d = r.get_json()
    assert d["username"] == "pradeep"
    assert d["persona"] == "ProductOwner"
    assert d["id"].startswith("usr_")


def test_list_users(admin_client):
    r = admin_client.get("/api/v1/users")
    assert r.status_code == 200
    assert len(r.get_json()) >= 1


def test_duplicate_username_rejected(admin_client):
    admin_client.post("/api/v1/users", json={"username": "dupuser", "persona": "ReadOnly"})
    r = admin_client.post("/api/v1/users", json={"username": "dupuser", "persona": "ReadOnly"})
    assert r.status_code == 409


def test_create_user_missing_username(admin_client):
    r = admin_client.post("/api/v1/users", json={"email": "no@name.com"})
    assert r.status_code == 400


def test_update_user_persona(admin_client):
    r = admin_client.post("/api/v1/users", json={"username": "persona_test", "persona": "ReadOnly"})
    user_id = r.get_json()["id"]
    r2 = admin_client.patch(f"/api/v1/users/{user_id}", json={"persona": "PlatformAdmin"})
    assert r2.status_code == 200
    assert r2.get_json()["persona"] == "PlatformAdmin"


def test_get_user_permissions(admin_client):
    users = admin_client.get("/api/v1/users").get_json()
    # Use the test_admin user which has system-administrator binding
    admin_user = next((u for u in users if u["username"] == "test_admin"), None)
    assert admin_user is not None
    r = admin_client.get(f"/api/v1/users/{admin_user['id']}/permissions?scope=organization")
    assert r.status_code == 200
    d = r.get_json()
    assert "permissions" in d
    assert len(d["permissions"]) > 0


def test_list_user_bindings(admin_client):
    users = admin_client.get("/api/v1/users").get_json()
    admin_user = next((u for u in users if u["username"] == "test_admin"), None)
    assert admin_user is not None
    r = admin_client.get(f"/api/v1/users/{admin_user['id']}/bindings")
    assert r.status_code == 200
    assert len(r.get_json()) >= 1


def test_create_and_list_roles(admin_client):
    r = admin_client.post(
        "/api/v1/roles",
        json={
            "name": "CustomDeployer",
            "permissions": ["environments:view", "pipelines:execute"],
            "description": "Can deploy to environments",
        },
    )
    assert r.status_code == 201
    assert r.get_json()["name"] == "CustomDeployer"

    roles = admin_client.get("/api/v1/roles").get_json()
    role_names = [ro["name"] for ro in roles]
    assert "CustomDeployer" in role_names


def test_create_group(admin_client):
    r = admin_client.post(
        "/api/v1/groups", json={"name": "DevOps Team", "description": "Platform engineers"}
    )
    assert r.status_code == 201
    assert r.get_json()["name"] == "DevOps Team"


def test_add_remove_group_member(admin_client):
    group_r = admin_client.post("/api/v1/groups", json={"name": "TestGroup"})
    group_id = group_r.get_json()["id"]

    user_r = admin_client.post("/api/v1/users", json={"username": "groupmember"})
    user_id = user_r.get_json()["id"]

    r = admin_client.post(f"/api/v1/groups/{group_id}/members/{user_id}")
    assert r.status_code == 200

    r2 = admin_client.delete(f"/api/v1/groups/{group_id}/members/{user_id}")
    assert r2.status_code == 204


def test_unauthenticated_rejected():
    """Raw (no-token) requests to protected endpoints return 401."""
    from app import _ensure_builtin_roles, create_app
    from app.config import TestConfig
    from app.extensions import db as _db

    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        _ensure_builtin_roles()
        c = application.test_client()
        r = c.get("/api/v1/users")
        assert r.status_code == 401
        _db.drop_all()
