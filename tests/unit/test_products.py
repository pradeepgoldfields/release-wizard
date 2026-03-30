import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_create_and_list_product(client):
    r = client.post("/api/v1/products", json={"name": "API Service", "description": "Core API"})
    assert r.status_code == 201
    data = r.get_json()
    assert data["name"] == "API Service"

    r2 = client.get("/api/v1/products")
    assert r2.status_code == 200
    assert len(r2.get_json()) == 1


def test_get_product(client):
    r = client.post("/api/v1/products", json={"name": "Test Product"})
    product_id = r.get_json()["id"]

    r2 = client.get(f"/api/v1/products/{product_id}")
    assert r2.status_code == 200
    assert r2.get_json()["id"] == product_id


def test_delete_product(client):
    r = client.post("/api/v1/products", json={"name": "Delete Me"})
    product_id = r.get_json()["id"]

    r2 = client.delete(f"/api/v1/products/{product_id}")
    assert r2.status_code == 204

    r3 = client.get(f"/api/v1/products/{product_id}")
    assert r3.status_code == 404


def test_create_top_level_environment(client):
    """Environments are now top-level — create via /api/v1/environments."""
    r = client.post(
        "/api/v1/environments",
        json={"name": "Production", "env_type": "prod", "order": 3},
    )
    assert r.status_code == 201
    assert r.get_json()["env_type"] == "prod"
    assert "product_id" not in r.get_json()


def test_attach_environment_to_product(client):
    """Attach a top-level environment to a product."""
    prod = client.post("/api/v1/products", json={"name": "My Product"}).get_json()
    env = client.post(
        "/api/v1/environments", json={"name": "Staging", "env_type": "staging"}
    ).get_json()

    r = client.post(
        f"/api/v1/products/{prod['id']}/environments",
        json={"environment_id": env["id"]},
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "attached"

    envs = client.get(f"/api/v1/products/{prod['id']}/environments").get_json()
    assert any(e["id"] == env["id"] for e in envs)


def test_detach_environment_from_product(client):
    prod = client.post("/api/v1/products", json={"name": "Prod"}).get_json()
    env = client.post("/api/v1/environments", json={"name": "Dev", "env_type": "dev"}).get_json()
    client.post(f"/api/v1/products/{prod['id']}/environments", json={"environment_id": env["id"]})

    r = client.delete(f"/api/v1/products/{prod['id']}/environments/{env['id']}")
    assert r.status_code == 204

    envs = client.get(f"/api/v1/products/{prod['id']}/environments").get_json()
    assert not any(e["id"] == env["id"] for e in envs)

    # Environment still exists globally
    r2 = client.get(f"/api/v1/environments/{env['id']}")
    assert r2.status_code == 200
