"""E2E: Core release lifecycle — Product → Pipeline → Release → Run."""

from __future__ import annotations

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def product(admin_client):
    r = admin_client.post(
        "/api/v1/products",
        json={"name": "E2E Product", "description": "Created by E2E lifecycle tests"},
    )
    assert r.status_code == 201
    return r.get_json()


@pytest.fixture(scope="module")
def platinum_pipeline(admin_client, product):
    pid = product["id"]
    r = admin_client.post(
        f"/api/v1/products/{pid}/pipelines",
        json={"name": "E2E CI Pipeline", "kind": "ci", "git_branch": "main"},
    )
    assert r.status_code == 201
    pipeline = r.get_json()
    admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{pipeline['id']}/compliance",
        json={
            "mandatory_pct": 100,
            "best_practice_pct": 100,
            "runtime_pct": 100,
            "metadata_pct": 100,
        },
    )
    return pipeline


@pytest.fixture(scope="module")
def release(admin_client, product, platinum_pipeline):
    pid = product["id"]
    r = admin_client.post(
        f"/api/v1/products/{pid}/releases",
        json={"name": "E2E Release v1.0", "version": "1.0.0", "created_by": "e2e_admin"},
    )
    assert r.status_code == 201
    rel = r.get_json()
    attach = admin_client.post(
        f"/api/v1/products/{pid}/releases/{rel['id']}/pipelines",
        json={"pipeline_id": platinum_pipeline["id"], "requested_by": "e2e_admin"},
    )
    assert attach.status_code == 200
    return rel


# ── Product creation ──────────────────────────────────────────────────────────


def test_product_created_with_correct_fields(product):
    assert product["id"].startswith("prod_") or len(product["id"]) > 4
    assert product["name"] == "E2E Product"
    assert product["description"] == "Created by E2E lifecycle tests"
    assert "created_at" in product


def test_product_visible_in_list(admin_client, product):
    r = admin_client.get("/api/v1/products")
    assert r.status_code == 200
    items = r.get_json()
    ids = [p["id"] for p in (items if isinstance(items, list) else items.get("items", []))]
    assert product["id"] in ids


def test_product_get_by_id(admin_client, product):
    r = admin_client.get(f"/api/v1/products/{product['id']}")
    assert r.status_code == 200
    assert r.get_json()["name"] == "E2E Product"


def test_product_update_name(admin_client, product):
    r = admin_client.put(
        f"/api/v1/products/{product['id']}",
        json={"name": "E2E Product Updated"},
    )
    assert r.status_code == 200
    assert r.get_json()["name"] == "E2E Product Updated"
    # Restore name
    admin_client.put(f"/api/v1/products/{product['id']}", json={"name": "E2E Product"})


def test_product_delete_removes_from_list(admin_client):
    r = admin_client.post("/api/v1/products", json={"name": "Throwaway Product"})
    assert r.status_code == 201
    pid = r.get_json()["id"]
    d = admin_client.delete(f"/api/v1/products/{pid}")
    assert d.status_code == 204
    r2 = admin_client.get("/api/v1/products")
    items = r2.get_json()
    ids = [p["id"] for p in (items if isinstance(items, list) else items.get("items", []))]
    assert pid not in ids


# ── Pipeline definition ───────────────────────────────────────────────────────


def test_pipeline_created_under_product(platinum_pipeline):
    assert len(platinum_pipeline["id"]) > 0
    assert platinum_pipeline["kind"] == "ci"
    assert "product_id" in platinum_pipeline


def test_pipeline_list_under_product(admin_client, product, platinum_pipeline):
    r = admin_client.get(f"/api/v1/products/{product['id']}/pipelines")
    assert r.status_code == 200
    data = r.get_json()
    items = data if isinstance(data, list) else data.get("items", [])
    ids = [p["id"] for p in items]
    assert platinum_pipeline["id"] in ids


def test_pipeline_update_git_branch(admin_client, product, platinum_pipeline):
    r = admin_client.put(
        f"/api/v1/products/{product['id']}/pipelines/{platinum_pipeline['id']}",
        json={"git_branch": "release/1.0"},
    )
    assert r.status_code == 200
    assert r.get_json()["git_branch"] == "release/1.0"


def test_pipeline_compliance_score_reaches_platinum(admin_client, product, platinum_pipeline):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/pipelines/{platinum_pipeline['id']}/compliance",
        json={
            "mandatory_pct": 100,
            "best_practice_pct": 100,
            "runtime_pct": 100,
            "metadata_pct": 100,
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["compliance_rating"] == "Platinum"
    assert data["compliance_score"] >= 95


def test_pipeline_copy_creates_duplicate(admin_client, product, platinum_pipeline):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/pipelines/{platinum_pipeline['id']}/copy"
    )
    assert r.status_code == 201
    copy = r.get_json()
    assert copy["id"] != platinum_pipeline["id"]
    assert copy["name"].startswith("Copy of")
    # Cleanup
    admin_client.delete(f"/api/v1/products/{product['id']}/pipelines/{copy['id']}")


def test_pipeline_delete(admin_client, product):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/pipelines",
        json={"name": "Throwaway Pipeline", "kind": "ci"},
    )
    assert r.status_code == 201
    plid = r.get_json()["id"]
    d = admin_client.delete(f"/api/v1/products/{product['id']}/pipelines/{plid}")
    assert d.status_code == 204
    r2 = admin_client.get(f"/api/v1/products/{product['id']}/pipelines")
    items = r2.get_json()
    ids = [p["id"] for p in (items if isinstance(items, list) else items.get("items", []))]
    assert plid not in ids


# ── Stage and task definition ─────────────────────────────────────────────────


def test_add_stage_to_pipeline(admin_client, product, platinum_pipeline):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/pipelines/{platinum_pipeline['id']}/stages",
        json={"name": "Build Stage", "order": 1},
    )
    assert r.status_code == 201
    stage = r.get_json()
    assert len(stage["id"]) > 0
    assert stage["name"] == "Build Stage"


def test_stage_order_preserved(admin_client, product, platinum_pipeline):
    plid = platinum_pipeline["id"]
    pid = product["id"]
    s1 = admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{plid}/stages",
        json={"name": "Stage One", "order": 1},
    ).get_json()
    s2 = admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{plid}/stages",
        json={"name": "Stage Two", "order": 2},
    ).get_json()
    r = admin_client.get(f"/api/v1/products/{pid}/pipelines/{plid}")
    stages = r.get_json().get("stages", [])
    orders = [s["order"] for s in stages if s["id"] in (s1["id"], s2["id"])]
    assert sorted(orders) == orders


def test_add_task_to_stage(admin_client, product, platinum_pipeline):
    pid = product["id"]
    plid = platinum_pipeline["id"]
    stage = admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{plid}/stages",
        json={"name": "Task Stage", "order": 10},
    ).get_json()
    r = admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{plid}/stages/{stage['id']}/tasks",
        json={"name": "Run tests", "kind": "script", "run_language": "bash", "run_code": "pytest"},
    )
    assert r.status_code == 201
    task = r.get_json()
    assert len(task["id"]) > 0
    assert task["kind"] == "script"


def test_add_approval_task_to_stage(admin_client, product, platinum_pipeline):
    pid = product["id"]
    plid = platinum_pipeline["id"]
    stage = admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{plid}/stages",
        json={"name": "Approval Stage", "order": 11},
    ).get_json()
    r = admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{plid}/stages/{stage['id']}/tasks",
        json={
            "name": "Deploy approval",
            "kind": "approval",
            "approval_approvers": ["e2e_admin"],
            "approval_required_count": 2,
        },
    )
    assert r.status_code == 201
    task = r.get_json()
    assert task["kind"] == "approval"
    assert task.get("approval_required_count") == 2


def test_add_gate_task_to_stage(admin_client, product, platinum_pipeline):
    pid = product["id"]
    plid = platinum_pipeline["id"]
    stage = admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{plid}/stages",
        json={"name": "Gate Stage", "order": 12},
    ).get_json()
    r = admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{plid}/stages/{stage['id']}/tasks",
        json={"name": "Quality Gate", "kind": "gate", "run_code": "exit 0"},
    )
    assert r.status_code == 201
    task = r.get_json()
    assert task["kind"] == "gate"


def test_task_delete(admin_client, product, platinum_pipeline):
    pid = product["id"]
    plid = platinum_pipeline["id"]
    stage = admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{plid}/stages",
        json={"name": "Delete Task Stage", "order": 20},
    ).get_json()
    task = admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{plid}/stages/{stage['id']}/tasks",
        json={"name": "Throwaway Task", "kind": "script"},
    ).get_json()
    d = admin_client.delete(
        f"/api/v1/products/{pid}/pipelines/{plid}/stages/{stage['id']}/tasks/{task['id']}"
    )
    assert d.status_code == 204
    r = admin_client.get(f"/api/v1/products/{pid}/pipelines/{plid}")
    all_tasks = [
        t
        for s in r.get_json().get("stages", [])
        if s["id"] == stage["id"]
        for t in s.get("tasks", [])
    ]
    assert not any(t["id"] == task["id"] for t in all_tasks)


def test_stage_delete(admin_client, product, platinum_pipeline):
    pid = product["id"]
    plid = platinum_pipeline["id"]
    stage = admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{plid}/stages",
        json={"name": "Throwaway Stage", "order": 99},
    ).get_json()
    d = admin_client.delete(f"/api/v1/products/{pid}/pipelines/{plid}/stages/{stage['id']}")
    assert d.status_code == 204
    r = admin_client.get(f"/api/v1/products/{pid}/pipelines/{plid}")
    stage_ids = [s["id"] for s in r.get_json().get("stages", [])]
    assert stage["id"] not in stage_ids


# ── Release creation and admission ────────────────────────────────────────────


def test_release_created_with_correct_fields(release):
    assert len(release["id"]) > 0
    assert release["name"] == "E2E Release v1.0"
    assert release["version"] == "1.0.0"


def test_pipeline_attaches_to_release_with_passed_admission(
    admin_client, product, release, platinum_pipeline
):
    r = admin_client.get(f"/api/v1/products/{product['id']}/releases/{release['id']}")
    assert r.status_code == 200
    data = r.get_json()
    pipelines = data.get("pipelines", [])
    matched = [p for p in pipelines if p.get("pipeline_id") == platinum_pipeline["id"]]
    assert matched, "Pipeline not found in release"
    assert matched[0].get("admission") == "passed"


def test_compliance_rule_blocks_bronze_pipeline(admin_client, product):
    pid = product["id"]
    # Create a Gold rule for this product
    rule_r = admin_client.post(
        "/api/v1/compliance/rules",
        json={"name": "E2E Gold Rule", "scope": f"product:{pid}", "min_rating": "Gold"},
    )
    assert rule_r.status_code == 201
    rule_id = rule_r.get_json()["id"]

    # Create a bronze pipeline
    pl = admin_client.post(
        f"/api/v1/products/{pid}/pipelines",
        json={"name": "Bronze Pipeline", "kind": "ci"},
    ).get_json()
    admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{pl['id']}/compliance",
        json={"mandatory_pct": 50, "best_practice_pct": 0, "runtime_pct": 0, "metadata_pct": 0},
    )

    # Create release and attempt to attach bronze pipeline
    rel = admin_client.post(
        f"/api/v1/products/{pid}/releases",
        json={"name": "Blocked Release", "version": "0.1.0"},
    ).get_json()
    attach = admin_client.post(
        f"/api/v1/products/{pid}/releases/{rel['id']}/pipelines",
        json={"pipeline_id": pl["id"], "requested_by": "e2e_admin"},
    )
    assert attach.status_code == 422
    assert "violations" in attach.get_json()

    # Cleanup
    admin_client.delete(f"/api/v1/compliance/rules/{rule_id}")


def test_release_list_shows_release(admin_client, product, release):
    r = admin_client.get(f"/api/v1/products/{product['id']}/releases")
    assert r.status_code == 200
    data = r.get_json()
    items = data if isinstance(data, list) else data.get("items", [])
    ids = [rel["id"] for rel in items]
    assert release["id"] in ids


def test_release_update_description(admin_client, product, release):
    r = admin_client.put(
        f"/api/v1/products/{product['id']}/releases/{release['id']}",
        json={"description": "Updated by E2E test"},
    )
    assert r.status_code == 200
    assert r.get_json()["description"] == "Updated by E2E test"


def test_release_pipeline_detach(admin_client, product, platinum_pipeline):
    pid = product["id"]
    # Create a separate release for detach test
    rel = admin_client.post(
        f"/api/v1/products/{pid}/releases",
        json={"name": "Detach Release", "version": "99.0.0"},
    ).get_json()
    admin_client.post(
        f"/api/v1/products/{pid}/releases/{rel['id']}/pipelines",
        json={"pipeline_id": platinum_pipeline["id"], "requested_by": "e2e_admin"},
    )
    d = admin_client.delete(
        f"/api/v1/products/{pid}/releases/{rel['id']}/pipelines/{platinum_pipeline['id']}"
    )
    assert d.status_code in (200, 204)
    r = admin_client.get(f"/api/v1/products/{pid}/releases/{rel['id']}")
    pipelines = r.get_json().get("pipelines", [])
    assert not any(p.get("pipeline_id") == platinum_pipeline["id"] for p in pipelines)


# ── Release run ───────────────────────────────────────────────────────────────


def test_trigger_release_run_returns_202_or_201(admin_client, release):
    r = admin_client.post(f"/api/v1/releases/{release['id']}/runs", json={})
    assert r.status_code in (201, 202)
    data = r.get_json()
    assert len(data.get("id", "")) > 0


def test_release_run_visible_in_list(admin_client, release):
    admin_client.post(f"/api/v1/releases/{release['id']}/runs", json={})
    r = admin_client.get(f"/api/v1/releases/{release['id']}/runs")
    assert r.status_code == 200
    data = r.get_json()
    items = data if isinstance(data, list) else data.get("items", [])
    assert len(items) >= 1


def test_release_run_status_transitions(admin_client, release):
    r = admin_client.post(f"/api/v1/releases/{release['id']}/runs", json={})
    assert r.status_code in (201, 202)
    run_id = r.get_json()["id"]
    patch = admin_client.patch(f"/api/v1/release-runs/{run_id}", json={"status": "Succeeded"})
    assert patch.status_code == 200
    assert patch.get_json()["status"] == "Succeeded"


def test_pipeline_runs_created_for_release_run(admin_client, release, platinum_pipeline):
    run_r = admin_client.post(f"/api/v1/releases/{release['id']}/runs", json={})
    assert run_r.status_code in (201, 202)
    rrun_id = run_r.get_json()["id"]
    r = admin_client.get(f"/api/v1/pipelines/{platinum_pipeline['id']}/runs")
    assert r.status_code == 200
    data = r.get_json()
    items = data if isinstance(data, list) else data.get("items", [])
    matched = [pr for pr in items if pr.get("release_run_id") == rrun_id]
    assert len(matched) >= 1


# ── Audit report ──────────────────────────────────────────────────────────────


def test_audit_report_contains_release_and_pipeline_sections(admin_client, product, release):
    r = admin_client.get(f"/api/v1/products/{product['id']}/releases/{release['id']}/audit")
    assert r.status_code == 200
    data = r.get_json()
    for key in ("release", "pipelines", "audit_events"):
        assert key in data, f"Missing key: {key}"


def test_audit_events_log_product_creation(admin_client):
    r = admin_client.get("/api/v1/compliance/audit-events?resource_type=product")
    assert r.status_code == 200
    events = r.get_json()
    items = events if isinstance(events, list) else events.get("items", [])
    assert len(items) >= 1


def test_audit_events_log_pipeline_run(admin_client):
    r = admin_client.get("/api/v1/compliance/audit-events?resource_type=pipeline_run")
    assert r.status_code == 200
    events = r.get_json()
    items = events if isinstance(events, list) else events.get("items", [])
    assert len(items) >= 1


def test_audit_pdf_export_returns_pdf(admin_client, product, release):
    r = admin_client.get(f"/api/v1/products/{product['id']}/releases/{release['id']}/audit/export")
    assert r.status_code == 200
    assert "pdf" in r.content_type.lower() or r.data[:4] == b"%PDF"
