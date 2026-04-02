"""Unit tests for Pipeline CRUD endpoints.

Covers: list, create, get, update, delete, copy, compliance-score update.
All tests use an in-memory SQLite DB via the shared ``admin_client`` fixture.
"""

from __future__ import annotations

from app.extensions import db
from app.models.pipeline import Pipeline
from app.models.product import Product
from app.services.id_service import resource_id

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_product(app) -> str:
    with app.app_context():
        p = Product(
            id=resource_id("prod"),
            name="Test Product",
            description="",
        )
        db.session.add(p)
        db.session.commit()
        return p.id


# ── list pipelines ────────────────────────────────────────────────────────────


def test_list_pipelines_empty(admin_client, app):
    prod_id = _make_product(app)
    r = admin_client.get(f"/api/v1/products/{prod_id}/pipelines")
    assert r.status_code == 200
    data = r.get_json()
    assert data["items"] == []


def test_list_pipelines_returns_existing(admin_client, app):
    prod_id = _make_product(app)
    with app.app_context():
        pl = Pipeline(
            id=resource_id("pl"),
            product_id=prod_id,
            name="My Pipeline",
            kind="ci",
        )
        db.session.add(pl)
        db.session.commit()

    r = admin_client.get(f"/api/v1/products/{prod_id}/pipelines")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "My Pipeline"


# ── create pipeline ───────────────────────────────────────────────────────────


def test_create_pipeline_success(admin_client, app):
    prod_id = _make_product(app)
    r = admin_client.post(
        f"/api/v1/products/{prod_id}/pipelines",
        json={"name": "Build Pipeline", "kind": "ci"},
    )
    assert r.status_code == 201
    data = r.get_json()
    assert data["name"] == "Build Pipeline"
    assert data["kind"] == "ci"
    assert "id" in data


def test_create_pipeline_missing_name(admin_client, app):
    prod_id = _make_product(app)
    r = admin_client.post(
        f"/api/v1/products/{prod_id}/pipelines",
        json={"kind": "ci"},
    )
    assert r.status_code == 400
    assert "name" in r.get_json()["error"].lower()


def test_create_pipeline_with_stages(admin_client, app):
    prod_id = _make_product(app)
    r = admin_client.post(
        f"/api/v1/products/{prod_id}/pipelines",
        json={
            "name": "Full Pipeline",
            "kind": "ci",
            "stages": [
                {
                    "name": "Build",
                    "order": 1,
                    "tasks": [
                        {
                            "name": "compile",
                            "order": 1,
                            "run_language": "bash",
                            "run_code": "echo ok",
                        }
                    ],
                }
            ],
        },
    )
    assert r.status_code == 201
    data = r.get_json()
    assert len(data["stages"]) == 1
    assert data["stages"][0]["name"] == "Build"


# ── get pipeline ──────────────────────────────────────────────────────────────


def test_get_pipeline_found(admin_client, app):
    prod_id = _make_product(app)
    create_r = admin_client.post(
        f"/api/v1/products/{prod_id}/pipelines",
        json={"name": "Get Test"},
    )
    pl_id = create_r.get_json()["id"]

    r = admin_client.get(f"/api/v1/products/{prod_id}/pipelines/{pl_id}")
    assert r.status_code == 200
    assert r.get_json()["id"] == pl_id


def test_get_pipeline_not_found(admin_client, app):
    prod_id = _make_product(app)
    r = admin_client.get(f"/api/v1/products/{prod_id}/pipelines/nonexistent")
    assert r.status_code == 404


# ── update pipeline ───────────────────────────────────────────────────────────


def test_update_pipeline_name(admin_client, app):
    prod_id = _make_product(app)
    pl_id = admin_client.post(
        f"/api/v1/products/{prod_id}/pipelines", json={"name": "Old Name"}
    ).get_json()["id"]

    r = admin_client.put(
        f"/api/v1/products/{prod_id}/pipelines/{pl_id}",
        json={"name": "New Name"},
    )
    assert r.status_code == 200
    assert r.get_json()["name"] == "New Name"


# ── delete pipeline ───────────────────────────────────────────────────────────


def test_delete_pipeline(admin_client, app):
    prod_id = _make_product(app)
    pl_id = admin_client.post(
        f"/api/v1/products/{prod_id}/pipelines", json={"name": "To Delete"}
    ).get_json()["id"]

    r = admin_client.delete(f"/api/v1/products/{prod_id}/pipelines/{pl_id}")
    assert r.status_code == 204

    r2 = admin_client.get(f"/api/v1/products/{prod_id}/pipelines/{pl_id}")
    assert r2.status_code == 404


# ── copy pipeline ─────────────────────────────────────────────────────────────


def test_copy_pipeline(admin_client, app):
    prod_id = _make_product(app)
    src_id = admin_client.post(
        f"/api/v1/products/{prod_id}/pipelines",
        json={
            "name": "Source",
            "stages": [{"name": "Stage 1", "order": 1, "tasks": []}],
        },
    ).get_json()["id"]

    r = admin_client.post(
        f"/api/v1/products/{prod_id}/pipelines/{src_id}/copy",
        json={"name": "Source (Copy)"},
    )
    assert r.status_code == 201
    copy_data = r.get_json()
    assert copy_data["name"] == "Source (Copy)"
    assert copy_data["id"] != src_id


# ── compliance score ──────────────────────────────────────────────────────────


def test_update_compliance_score(admin_client, app):
    prod_id = _make_product(app)
    pl_id = admin_client.post(
        f"/api/v1/products/{prod_id}/pipelines", json={"name": "Comply"}
    ).get_json()["id"]

    r = admin_client.post(
        f"/api/v1/products/{prod_id}/pipelines/{pl_id}/compliance",
        json={"mandatory_pct": 80, "best_practice_pct": 60},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert "compliance_score" in data
    assert "compliance_rating" in data
