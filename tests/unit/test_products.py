"""Unit tests for Product and Environment endpoints.

All endpoints now require authentication; tests use the ``admin_client`` fixture
which authenticates as a system-administrator before each test.
"""

from __future__ import annotations


def test_create_and_list_product(admin_client):
    r = admin_client.post("/api/v1/products", json={"name": "API Service", "description": "Core API"})
    assert r.status_code == 201
    data = r.get_json()
    assert data["name"] == "API Service"

    r2 = admin_client.get("/api/v1/products")
    assert r2.status_code == 200
    assert len(r2.get_json()["items"]) >= 1


def test_get_product(admin_client):
    r = admin_client.post("/api/v1/products", json={"name": "Test Product"})
    assert r.status_code == 201
    product_id = r.get_json()["id"]

    r2 = admin_client.get(f"/api/v1/products/{product_id}")
    assert r2.status_code == 200
    assert r2.get_json()["id"] == product_id


def test_delete_product(admin_client):
    r = admin_client.post("/api/v1/products", json={"name": "Delete Me"})
    assert r.status_code == 201
    product_id = r.get_json()["id"]

    r2 = admin_client.delete(f"/api/v1/products/{product_id}")
    assert r2.status_code == 204

    r3 = admin_client.get(f"/api/v1/products/{product_id}")
    assert r3.status_code == 404


def test_unauthenticated_request_rejected():
    """A raw (no-token) request should get 401, not 403 or 200."""
    from app import create_app
    from app.config import TestConfig
    from app.extensions import db as _db

    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        c = application.test_client()
        r = c.post("/api/v1/products", json={"name": "Should Fail"})
        assert r.status_code == 401
        _db.drop_all()


def test_create_top_level_environment(admin_client):
    """Environments are top-level — create via /api/v1/environments."""
    r = admin_client.post(
        "/api/v1/environments",
        json={"name": "Production", "env_type": "prod", "order": 3},
    )
    assert r.status_code == 201
    assert r.get_json()["env_type"] == "prod"
    assert "product_id" not in r.get_json()


def test_attach_environment_to_product(admin_client):
    """Attach a top-level environment to a product."""
    prod = admin_client.post("/api/v1/products", json={"name": "My Product"}).get_json()
    env = admin_client.post(
        "/api/v1/environments", json={"name": "Staging", "env_type": "staging"}
    ).get_json()

    r = admin_client.post(
        f"/api/v1/products/{prod['id']}/environments",
        json={"environment_id": env["id"]},
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "attached"

    envs = admin_client.get(f"/api/v1/products/{prod['id']}/environments").get_json()
    assert any(e["id"] == env["id"] for e in envs)


def test_detach_environment_from_product(admin_client):
    prod = admin_client.post("/api/v1/products", json={"name": "Prod"}).get_json()
    env = admin_client.post("/api/v1/environments", json={"name": "Dev", "env_type": "dev"}).get_json()
    admin_client.post(f"/api/v1/products/{prod['id']}/environments", json={"environment_id": env["id"]})

    r = admin_client.delete(f"/api/v1/products/{prod['id']}/environments/{env['id']}")
    assert r.status_code == 204

    envs = admin_client.get(f"/api/v1/products/{prod['id']}/environments").get_json()
    assert not any(e["id"] == env["id"] for e in envs)

    # Environment still exists globally
    r2 = admin_client.get(f"/api/v1/environments/{env['id']}")
    assert r2.status_code == 200
