"""End-to-end integration tests — exercises the full API and the UI route."""

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


# ── UI route ───────────────────────────────────────────────────────────────


def test_ui_root_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Conduit" in r.data
    assert b"<html" in r.data


def test_static_css_accessible(client):
    r = client.get("/static/css/main.css")
    assert r.status_code == 200
    assert b"sidebar" in r.data


def test_static_js_api_accessible(client):
    r = client.get("/static/js/api.js")
    assert r.status_code == 200
    assert b"getProducts" in r.data


def test_static_js_app_accessible(client):
    r = client.get("/static/js/app.js")
    assert r.status_code == 200
    assert b"router" in r.data


# ── Products CRUD ──────────────────────────────────────────────────────────


def test_create_product(client):
    r = client.post("/api/v1/products", json={"name": "API Service", "description": "Core backend"})
    assert r.status_code == 201
    d = r.get_json()
    assert d["name"] == "API Service"
    assert d["id"].startswith("prod_")


def test_list_products(client):
    r = client.get("/api/v1/products")
    assert r.status_code == 200
    body = r.get_json()
    assert "items" in body and "meta" in body
    assert len(body["items"]) >= 1


def test_get_product(client):
    prods = client.get("/api/v1/products").get_json()["items"]
    pid = prods[0]["id"]
    r = client.get(f"/api/v1/products/{pid}")
    assert r.status_code == 200
    assert r.get_json()["id"] == pid


# ── Environments ───────────────────────────────────────────────────────────


def test_create_environment(client):
    pid = client.get("/api/v1/products").get_json()["items"][0]["id"]
    # Environments are top-level: create first, then attach
    r = client.post(
        "/api/v1/environments",
        json={"name": "Production", "env_type": "prod", "order": 3},
    )
    assert r.status_code == 201
    assert r.get_json()["env_type"] == "prod"
    env_id = r.get_json()["id"]

    # Attach to product
    r2 = client.post(
        f"/api/v1/products/{pid}/environments",
        json={"environment_id": env_id},
    )
    assert r2.status_code == 200


# ── Pipelines ──────────────────────────────────────────────────────────────


def test_create_pipeline(client):
    pid = client.get("/api/v1/products").get_json()["items"][0]["id"]
    r = client.post(
        f"/api/v1/products/{pid}/pipelines",
        json={"name": "CI Pipeline", "kind": "ci", "git_branch": "main"},
    )
    assert r.status_code == 201
    d = r.get_json()
    assert d["kind"] == "ci"
    assert d["id"].startswith("pl_")


def test_update_compliance_score(client):
    pid = client.get("/api/v1/products").get_json()["items"][0]["id"]
    plid = client.get(f"/api/v1/products/{pid}/pipelines").get_json()["items"][0]["id"]
    r = client.post(
        f"/api/v1/products/{pid}/pipelines/{plid}/compliance",
        json={"mandatory_pct": 100, "best_practice_pct": 80, "runtime_pct": 90, "metadata_pct": 50},
    )
    assert r.status_code == 200
    d = r.get_json()
    assert d["compliance_rating"] == "Platinum"
    assert d["compliance_score"] > 90


# ── Releases & admission ────────────────────────────────────────────────────


def test_create_release(client):
    pid = client.get("/api/v1/products").get_json()["items"][0]["id"]
    r = client.post(
        f"/api/v1/products/{pid}/releases",
        json={"name": "Feb 2026 Release", "version": "2026.02", "created_by": "pradeep"},
    )
    assert r.status_code == 201
    d = r.get_json()
    assert d["name"] == "Feb 2026 Release"
    assert d["id"].startswith("rel_")


def test_attach_pipeline_passes_admission(client):
    pid = client.get("/api/v1/products").get_json()["items"][0]["id"]
    plid = client.get(f"/api/v1/products/{pid}/pipelines").get_json()["items"][0]["id"]
    rid = client.get(f"/api/v1/products/{pid}/releases").get_json()[0]["id"]
    r = client.post(
        f"/api/v1/products/{pid}/releases/{rid}/pipelines",
        json={"pipeline_id": plid, "requested_by": "pradeep"},
    )
    # No compliance rules defined yet → should pass
    assert r.status_code == 200
    assert r.get_json()["admission"] == "passed"


def test_compliance_rule_blocks_low_rating(client):
    """Create a Platinum-required rule, then try to attach a pipeline rated below Platinum."""
    with client.application.app_context():
        pid = client.get("/api/v1/products").get_json()["items"][0]["id"]
        # Create a second low-rated pipeline
        r = client.post(
            f"/api/v1/products/{pid}/pipelines", json={"name": "Low-rated pipeline", "kind": "ci"}
        )
        low_plid = r.get_json()["id"]
        # Give it a Bronze score
        client.post(
            f"/api/v1/products/{pid}/pipelines/{low_plid}/compliance",
            json={"mandatory_pct": 30, "best_practice_pct": 0, "runtime_pct": 0, "metadata_pct": 0},
        )
        # Create a Platinum compliance rule
        client.post(
            "/api/v1/compliance/rules",
            json={
                "scope": f"product:{pid}",
                "min_rating": "Platinum",
                "description": "Only Platinum pipelines",
            },
        )
        # Create a new release and try to attach the low-rated pipeline
        r = client.post(
            f"/api/v1/products/{pid}/releases",
            json={"name": "Gated Release", "created_by": "system"},
        )
        rid = r.get_json()["id"]
        attach = client.post(
            f"/api/v1/products/{pid}/releases/{rid}/pipelines",
            json={"pipeline_id": low_plid, "requested_by": "pradeep"},
        )
        assert attach.status_code == 422
        assert "violations" in attach.get_json()


# ── Pipeline runs ──────────────────────────────────────────────────────────


def test_create_and_list_pipeline_run(client):
    pid = client.get("/api/v1/products").get_json()["items"][0]["id"]
    plid = client.get(f"/api/v1/products/{pid}/pipelines").get_json()["items"][0]["id"]
    r = client.post(
        f"/api/v1/pipelines/{plid}/runs",
        json={"commit_sha": "abc123", "artifact_id": "api:1.0.1", "triggered_by": "pradeep"},
    )
    assert r.status_code in (201, 202)
    d = r.get_json()
    assert d["id"].startswith("plrun_")
    assert d["status"] in ("Pending", "Running", "Succeeded")

    runs = client.get(f"/api/v1/pipelines/{plid}/runs").get_json()["items"]
    assert len(runs) >= 1


def test_update_pipeline_run_status(client):
    pid = client.get("/api/v1/products").get_json()["items"][0]["id"]
    plid = client.get(f"/api/v1/products/{pid}/pipelines").get_json()["items"][0]["id"]
    run_id = client.get(f"/api/v1/pipelines/{plid}/runs").get_json()["items"][0]["id"]
    r = client.patch(f"/api/v1/pipeline-runs/{run_id}", json={"status": "Succeeded"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "Succeeded"


# ── Release runs ───────────────────────────────────────────────────────────


def test_create_release_run(client):
    pid = client.get("/api/v1/products").get_json()["items"][0]["id"]
    rid = client.get(f"/api/v1/products/{pid}/releases").get_json()[0]["id"]
    r = client.post(f"/api/v1/releases/{rid}/runs", json={"triggered_by": "pradeep"})
    assert r.status_code == 201
    d = r.get_json()
    assert d["id"].startswith("rrun_")


# ── Audit report ────────────────────────────────────────────────────────────


def test_get_audit_report(client):
    pid = client.get("/api/v1/products").get_json()["items"][0]["id"]
    rid = client.get(f"/api/v1/products/{pid}/releases").get_json()[0]["id"]
    r = client.get(f"/api/v1/products/{pid}/releases/{rid}/audit")
    assert r.status_code == 200
    report = r.get_json()
    assert "release" in report
    assert "pipelines" in report
    assert "audit_events" in report


# ── Audit events log ───────────────────────────────────────────────────────


def test_audit_events_recorded(client):
    r = client.get("/api/v1/compliance/audit-events")
    assert r.status_code == 200
    events = r.get_json()
    event_types = {e["event_type"] for e in events}
    # Should have release creation and pipeline run events logged
    assert any("release" in t or "pipeline" in t for t in event_types)
