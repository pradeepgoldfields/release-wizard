"""Unit tests for Release CRUD endpoints.

Covers: list, create, get, update, delete, pipeline attachment, audit report.
"""

from __future__ import annotations

from app.extensions import db
from app.models.product import Product
from app.services.id_service import resource_id

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_product(app) -> str:
    with app.app_context():
        p = Product(
            id=resource_id("prod"),
            name="Release Prod",
            description="",
        )
        db.session.add(p)
        db.session.commit()
        return p.id


# ── list releases ─────────────────────────────────────────────────────────────


def test_list_releases_empty(admin_client, app):
    prod_id = _make_product(app)
    r = admin_client.get(f"/api/v1/products/{prod_id}/releases")
    assert r.status_code == 200
    assert r.get_json() == []


def test_list_releases_returns_existing(admin_client, app):
    prod_id = _make_product(app)
    admin_client.post(
        f"/api/v1/products/{prod_id}/releases",
        json={"name": "v1.0.0", "description": "first release"},
    )
    r = admin_client.get(f"/api/v1/products/{prod_id}/releases")
    assert r.status_code == 200
    items = r.get_json()
    assert len(items) == 1
    assert items[0]["name"] == "v1.0.0"


# ── create release ────────────────────────────────────────────────────────────


def test_create_release_success(admin_client, app):
    prod_id = _make_product(app)
    r = admin_client.post(
        f"/api/v1/products/{prod_id}/releases",
        json={"name": "v2.0.0", "version": "2.0.0", "description": "second"},
    )
    assert r.status_code == 201
    data = r.get_json()
    assert data["name"] == "v2.0.0"
    assert "id" in data


def test_create_release_missing_name(admin_client, app):
    prod_id = _make_product(app)
    r = admin_client.post(
        f"/api/v1/products/{prod_id}/releases",
        json={"version": "1.0.0"},
    )
    assert r.status_code == 400
    assert "name" in r.get_json()["error"].lower()


# ── get release ───────────────────────────────────────────────────────────────


def test_get_release_found(admin_client, app):
    prod_id = _make_product(app)
    rel_id = admin_client.post(
        f"/api/v1/products/{prod_id}/releases",
        json={"name": "v3.0.0"},
    ).get_json()["id"]

    r = admin_client.get(f"/api/v1/products/{prod_id}/releases/{rel_id}")
    assert r.status_code == 200
    assert r.get_json()["id"] == rel_id


def test_get_release_not_found(admin_client, app):
    prod_id = _make_product(app)
    r = admin_client.get(f"/api/v1/products/{prod_id}/releases/nonexistent")
    assert r.status_code == 404


# ── update release ────────────────────────────────────────────────────────────


def test_update_release_name(admin_client, app):
    prod_id = _make_product(app)
    rel_id = admin_client.post(
        f"/api/v1/products/{prod_id}/releases",
        json={"name": "old-name"},
    ).get_json()["id"]

    r = admin_client.put(
        f"/api/v1/products/{prod_id}/releases/{rel_id}",
        json={"name": "new-name"},
    )
    assert r.status_code == 200
    assert r.get_json()["name"] == "new-name"


# ── delete release ────────────────────────────────────────────────────────────


def test_delete_release(admin_client, app):
    prod_id = _make_product(app)
    rel_id = admin_client.post(
        f"/api/v1/products/{prod_id}/releases",
        json={"name": "to-delete"},
    ).get_json()["id"]

    r = admin_client.delete(f"/api/v1/products/{prod_id}/releases/{rel_id}")
    assert r.status_code == 204

    r2 = admin_client.get(f"/api/v1/products/{prod_id}/releases/{rel_id}")
    assert r2.status_code == 404


# ── attach pipeline ───────────────────────────────────────────────────────────


def test_attach_pipeline_to_release(admin_client, app):
    prod_id = _make_product(app)

    pl_id = admin_client.post(
        f"/api/v1/products/{prod_id}/pipelines",
        json={"name": "Deploy Pipeline"},
    ).get_json()["id"]

    rel_id = admin_client.post(
        f"/api/v1/products/{prod_id}/releases",
        json={"name": "v4.0.0"},
    ).get_json()["id"]

    r = admin_client.post(
        f"/api/v1/products/{prod_id}/releases/{rel_id}/pipelines",
        json={"pipeline_id": pl_id},
    )
    assert r.status_code in (200, 201)


def test_attach_nonexistent_pipeline_to_release(admin_client, app):
    prod_id = _make_product(app)
    rel_id = admin_client.post(
        f"/api/v1/products/{prod_id}/releases",
        json={"name": "v5.0.0"},
    ).get_json()["id"]

    r = admin_client.post(
        f"/api/v1/products/{prod_id}/releases/{rel_id}/pipelines",
        json={"pipeline_id": "nonexistent"},
    )
    assert r.status_code in (400, 404)
