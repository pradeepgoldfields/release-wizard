import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db


@pytest.fixture(scope="module")
def app():
    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


def test_create_user_with_persona(client):
    r = client.post(
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


def test_list_users(client):
    r = client.get("/api/v1/users")
    assert r.status_code == 200
    assert len(r.get_json()) >= 1


def test_duplicate_username_rejected(client):
    r = client.post("/api/v1/users", json={"username": "pradeep", "persona": "ReadOnly"})
    assert r.status_code == 409


def test_create_user_missing_username(client):
    r = client.post("/api/v1/users", json={"email": "no@name.com"})
    assert r.status_code == 400


def test_update_user_persona(client):
    users = client.get("/api/v1/users").get_json()
    user_id = users[0]["id"]
    r = client.patch(f"/api/v1/users/{user_id}", json={"persona": "PlatformAdmin"})
    assert r.status_code == 200
    assert r.get_json()["persona"] == "PlatformAdmin"


def test_get_user_permissions(client):
    users = client.get("/api/v1/users").get_json()
    user_id = users[0]["id"]
    r = client.get(f"/api/v1/users/{user_id}/permissions?scope=organization")
    assert r.status_code == 200
    d = r.get_json()
    assert "permissions" in d
    assert len(d["permissions"]) > 0


def test_list_user_bindings(client):
    users = client.get("/api/v1/users").get_json()
    user_id = users[0]["id"]
    r = client.get(f"/api/v1/users/{user_id}/bindings")
    assert r.status_code == 200
    assert len(r.get_json()) >= 1  # persona binding


def test_create_and_list_roles(client):
    r = client.post(
        "/api/v1/roles",
        json={
            "name": "CustomDeployer",
            "permissions": ["environment.deploy", "environment.view"],
            "description": "Can deploy to environments",
        },
    )
    assert r.status_code == 201
    assert r.get_json()["name"] == "CustomDeployer"

    roles = client.get("/api/v1/roles").get_json()
    role_names = [r["name"] for r in roles]
    assert "CustomDeployer" in role_names


def test_create_group(client):
    r = client.post(
        "/api/v1/groups", json={"name": "DevOps Team", "description": "Platform engineers"}
    )
    assert r.status_code == 201
    assert r.get_json()["name"] == "DevOps Team"


def test_add_remove_group_member(client):
    groups = client.get("/api/v1/groups").get_json()
    group_id = groups[0]["id"]
    users = client.get("/api/v1/users").get_json()
    user_id = users[0]["id"]

    r = client.post(f"/api/v1/groups/{group_id}/members/{user_id}")
    assert r.status_code == 200

    r2 = client.delete(f"/api/v1/groups/{group_id}/members/{user_id}")
    assert r2.status_code == 204
