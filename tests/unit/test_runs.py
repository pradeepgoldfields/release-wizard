"""Unit tests for PipelineRun endpoints.

Covers: list runs, trigger run, get run, patch run status, re-run.
The execution engine is NOT invoked in these tests — runs are created via the
API and their status manipulated through the PATCH endpoint.
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
            name="Runs Product",
            description="",
        )
        db.session.add(p)
        db.session.commit()
        return p.id


def _make_pipeline(admin_client, prod_id: str) -> dict:
    r = admin_client.post(
        f"/api/v1/products/{prod_id}/pipelines",
        json={"name": "Test Pipeline", "kind": "ci"},
    )
    assert r.status_code == 201
    return r.get_json()


def _trigger_run(admin_client, pipeline_id: str) -> dict:
    r = admin_client.post(
        f"/api/v1/pipelines/{pipeline_id}/runs",
        json={"triggered_by": "test", "commit_sha": "abc123"},
    )
    assert r.status_code == 202, r.get_json()
    return r.get_json()


# ── list runs ─────────────────────────────────────────────────────────────────


def test_list_runs_empty(admin_client, app):
    prod_id = _make_product(app)
    pl = _make_pipeline(admin_client, prod_id)
    r = admin_client.get(f"/api/v1/pipelines/{pl['id']}/runs")
    assert r.status_code == 200
    assert r.get_json()["items"] == []


def test_list_runs_after_trigger(admin_client, app):
    prod_id = _make_product(app)
    pl = _make_pipeline(admin_client, prod_id)
    _trigger_run(admin_client, pl["id"])

    r = admin_client.get(f"/api/v1/pipelines/{pl['id']}/runs")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert len(items) == 1


# ── trigger run ───────────────────────────────────────────────────────────────


def test_trigger_run_success(admin_client, app):
    prod_id = _make_product(app)
    pl = _make_pipeline(admin_client, prod_id)

    r = admin_client.post(
        f"/api/v1/pipelines/{pl['id']}/runs",
        json={"triggered_by": "ci-bot", "commit_sha": "deadbeef"},
    )
    assert r.status_code == 202
    data = r.get_json()
    assert "id" in data
    assert data["pipeline_id"] == pl["id"]


def test_trigger_run_pipeline_not_found(admin_client, app):
    r = admin_client.post(
        "/api/v1/pipelines/nonexistent/runs",
        json={"triggered_by": "ci-bot"},
    )
    assert r.status_code == 404


# ── get run ───────────────────────────────────────────────────────────────────


def test_get_run_found(admin_client, app):
    prod_id = _make_product(app)
    pl = _make_pipeline(admin_client, prod_id)
    run = _trigger_run(admin_client, pl["id"])

    r = admin_client.get(f"/api/v1/pipeline-runs/{run['id']}")
    assert r.status_code == 200
    assert r.get_json()["id"] == run["id"]


def test_get_run_not_found(admin_client, app):
    r = admin_client.get("/api/v1/pipeline-runs/nonexistent")
    assert r.status_code == 404


# ── patch run status ──────────────────────────────────────────────────────────


def test_patch_run_status_success(admin_client, app):
    prod_id = _make_product(app)
    pl = _make_pipeline(admin_client, prod_id)
    run = _trigger_run(admin_client, pl["id"])

    r = admin_client.patch(
        f"/api/v1/pipeline-runs/{run['id']}",
        json={"status": "Succeeded"},
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "Succeeded"


def test_patch_run_status_invalid(admin_client, app):
    prod_id = _make_product(app)
    pl = _make_pipeline(admin_client, prod_id)
    run = _trigger_run(admin_client, pl["id"])

    r = admin_client.patch(
        f"/api/v1/pipeline-runs/{run['id']}",
        json={"status": "not-a-real-status"},
    )
    assert r.status_code == 400


# ── re-run ────────────────────────────────────────────────────────────────────


def test_rerun_pipeline(admin_client, app):
    prod_id = _make_product(app)
    pl = _make_pipeline(admin_client, prod_id)
    run = _trigger_run(admin_client, pl["id"])

    # Mark original as failed first
    admin_client.patch(
        f"/api/v1/pipeline-runs/{run['id']}",
        json={"status": "Failed"},
    )

    r = admin_client.post(f"/api/v1/pipeline-runs/{run['id']}/rerun")
    assert r.status_code == 202
    new_run = r.get_json()
    assert new_run["id"] != run["id"]
    assert new_run["pipeline_id"] == pl["id"]
