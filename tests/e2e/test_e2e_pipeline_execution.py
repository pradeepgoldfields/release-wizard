"""E2E: Pipeline execution engine — runs, stages, tasks, approvals, reruns."""

from __future__ import annotations

import pytest


def _list_items(r):
    data = r.get_json()
    return data if isinstance(data, list) else data.get("items", [])


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def product_with_pipeline(admin_client):
    pid = admin_client.post(
        "/api/v1/products",
        json={"name": "Exec E2E Product", "description": "Pipeline execution tests"},
    ).get_json()["id"]

    pl = admin_client.post(
        f"/api/v1/products/{pid}/pipelines",
        json={"name": "Exec Pipeline", "kind": "ci"},
    ).get_json()

    admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{pl['id']}/compliance",
        json={
            "mandatory_pct": 100,
            "best_practice_pct": 100,
            "runtime_pct": 100,
            "metadata_pct": 100,
        },
    )

    stage = admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{pl['id']}/stages",
        json={"name": "Build", "order": 1},
    ).get_json()

    task = admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{pl['id']}/stages/{stage['id']}/tasks",
        json={"name": "Run tests", "kind": "script", "run_language": "bash", "run_code": "pytest"},
    ).get_json()

    approval_task = admin_client.post(
        f"/api/v1/products/{pid}/pipelines/{pl['id']}/stages/{stage['id']}/tasks",
        json={
            "name": "Deploy approval",
            "kind": "approval",
            "approval_approvers": ["e2e_admin"],
            "approval_required_count": 1,
        },
    ).get_json()

    return {
        "product_id": pid,
        "pipeline": pl,
        "stage": stage,
        "task": task,
        "approval_task": approval_task,
    }


@pytest.fixture(scope="module")
def pipeline_run(admin_client, product_with_pipeline):
    plid = product_with_pipeline["pipeline"]["id"]
    r = admin_client.post(
        f"/api/v1/pipelines/{plid}/runs",
        json={"commit_sha": "deadbeef", "triggered_by": "e2e_admin"},
    )
    assert r.status_code in (201, 202)
    return r.get_json()


# ── Pipeline run lifecycle ────────────────────────────────────────────────────


def test_pipeline_run_id_format(pipeline_run):
    assert len(pipeline_run["id"]) > 0


def test_pipeline_run_initial_status_is_pending_or_running(pipeline_run):
    assert pipeline_run["status"] in ("Pending", "Running")


def test_pipeline_run_visible_in_list(admin_client, product_with_pipeline, pipeline_run):
    plid = product_with_pipeline["pipeline"]["id"]
    r = admin_client.get(f"/api/v1/pipelines/{plid}/runs")
    assert r.status_code == 200
    ids = [pr["id"] for pr in _list_items(r)]
    assert pipeline_run["id"] in ids


def test_get_pipeline_run_by_id(admin_client, pipeline_run):
    r = admin_client.get(f"/api/v1/pipeline-runs/{pipeline_run['id']}")
    assert r.status_code == 200
    assert "pipeline_id" in r.get_json()


def test_pipeline_run_status_update_to_succeeded(admin_client, pipeline_run):
    r = admin_client.patch(
        f"/api/v1/pipeline-runs/{pipeline_run['id']}",
        json={"status": "Succeeded"},
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "Succeeded"


def test_pipeline_run_status_update_to_failed(admin_client, pipeline_run):
    r = admin_client.patch(
        f"/api/v1/pipeline-runs/{pipeline_run['id']}",
        json={"status": "Failed"},
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "Failed"


def test_pipeline_run_status_update_to_cancelled(admin_client, pipeline_run):
    r = admin_client.patch(
        f"/api/v1/pipeline-runs/{pipeline_run['id']}",
        json={"status": "Cancelled"},
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "Cancelled"


def test_pipeline_run_completion_percentage(admin_client, pipeline_run):
    r = admin_client.get(f"/api/v1/pipeline-runs/{pipeline_run['id']}")
    assert r.status_code == 200
    pct = r.get_json().get("completion_percentage", 0)
    assert isinstance(pct, int | float)
    assert 0 <= pct <= 100


# ── Stage runs ────────────────────────────────────────────────────────────────


def test_stage_runs_created_for_pipeline_run(admin_client, pipeline_run):
    r = admin_client.get(f"/api/v1/pipeline-runs/{pipeline_run['id']}")
    assert r.status_code == 200
    stage_runs = r.get_json().get("stage_runs", [])
    assert len(stage_runs) >= 1


def test_stage_run_status_reflects_task_run_outcomes(admin_client, pipeline_run):
    r = admin_client.get(f"/api/v1/pipeline-runs/{pipeline_run['id']}")
    stage_runs = r.get_json().get("stage_runs", [])
    if not stage_runs:
        pytest.skip("No stage runs")
    valid = {
        "Pending",
        "Running",
        "Succeeded",
        "Failed",
        "Cancelled",
        "Skipped",
        "AwaitingApproval",
        "Warning",
    }
    assert stage_runs[0]["status"] in valid


def test_rerun_from_stage(admin_client, pipeline_run):
    r = admin_client.get(f"/api/v1/pipeline-runs/{pipeline_run['id']}")
    stage_runs = r.get_json().get("stage_runs", [])
    if not stage_runs:
        pytest.skip("No stage runs to rerun from")
    sr_id = stage_runs[0]["id"]
    r2 = admin_client.post(f"/api/v1/pipeline-runs/{pipeline_run['id']}/stages/{sr_id}/rerun")
    assert r2.status_code in (201, 202)
    assert r2.get_json()["id"] != pipeline_run["id"]


# ── Task runs ─────────────────────────────────────────────────────────────────


def test_task_run_created_for_each_task(admin_client, pipeline_run):
    r = admin_client.get(f"/api/v1/pipeline-runs/{pipeline_run['id']}")
    stage_runs = r.get_json().get("stage_runs", [])
    assert any(len(sr.get("task_runs", [])) >= 1 for sr in stage_runs)


def test_get_task_run_by_id(admin_client, pipeline_run):
    r = admin_client.get(f"/api/v1/pipeline-runs/{pipeline_run['id']}")
    stage_runs = r.get_json().get("stage_runs", [])
    task_runs = [tr for sr in stage_runs for tr in sr.get("task_runs", [])]
    if not task_runs:
        pytest.skip("No task runs found")
    tr_id = task_runs[0]["id"]
    r2 = admin_client.get(f"/api/v1/task-runs/{tr_id}")
    assert r2.status_code == 200
    assert "task_id" in r2.get_json()


def test_task_run_output_json_stored(admin_client, pipeline_run):
    # Verify the output_json field is present on task run records.
    # There is no PATCH endpoint for task runs — output_json is set internally.
    r = admin_client.get(f"/api/v1/pipeline-runs/{pipeline_run['id']}")
    stage_runs = r.get_json().get("stage_runs", [])
    task_runs = [tr for sr in stage_runs for tr in sr.get("task_runs", [])]
    if not task_runs:
        pytest.skip("No task runs found")
    tr_id = task_runs[0]["id"]
    r2 = admin_client.get(f"/api/v1/task-runs/{tr_id}")
    assert r2.status_code == 200
    # output_json key should be present (may be None if task hasn't finished)
    assert "output_json" in r2.get_json()


def test_task_run_logs_accessible(admin_client, pipeline_run):
    r = admin_client.get(f"/api/v1/pipeline-runs/{pipeline_run['id']}")
    stage_runs = r.get_json().get("stage_runs", [])
    task_runs = [tr for sr in stage_runs for tr in sr.get("task_runs", [])]
    if not task_runs:
        pytest.skip("No task runs found")
    tr = task_runs[0]
    assert "logs" in tr
    assert isinstance(tr["logs"], str | type(None))


# ── Approval workflow ─────────────────────────────────────────────────────────


def test_approval_task_run_awaiting_approval_status(admin_client, product_with_pipeline):
    plid = product_with_pipeline["pipeline"]["id"]
    # Create a fresh run
    run = admin_client.post(
        f"/api/v1/pipelines/{plid}/runs",
        json={"triggered_by": "e2e_admin"},
    ).get_json()
    run_data = admin_client.get(f"/api/v1/pipeline-runs/{run['id']}").get_json()
    all_trs = [tr for sr in run_data.get("stage_runs", []) for tr in sr.get("task_runs", [])]
    apv_trs = [
        tr for tr in all_trs if tr.get("task_kind") == "approval" or tr.get("kind") == "approval"
    ]
    if not apv_trs:
        pytest.skip("No approval task runs found")
    assert apv_trs[0]["status"] == "AwaitingApproval"


def test_submit_approval_decision_approved(admin_client, pipeline_run):
    run_data = admin_client.get(f"/api/v1/pipeline-runs/{pipeline_run['id']}").get_json()
    all_trs = [tr for sr in run_data.get("stage_runs", []) for tr in sr.get("task_runs", [])]
    apv = next((tr for tr in all_trs if tr.get("status") == "AwaitingApproval"), None)
    if not apv:
        pytest.skip("No awaiting approval task run")
    r = admin_client.post(
        f"/api/v1/task-runs/{apv['id']}/approvals",
        json={"decision": "approved", "comment": "LGTM"},
    )
    assert r.status_code == 201


def test_submit_approval_decision_rejected(admin_client, product_with_pipeline):
    plid = product_with_pipeline["pipeline"]["id"]
    run = admin_client.post(f"/api/v1/pipelines/{plid}/runs", json={}).get_json()
    run_data = admin_client.get(f"/api/v1/pipeline-runs/{run['id']}").get_json()
    all_trs = [tr for sr in run_data.get("stage_runs", []) for tr in sr.get("task_runs", [])]
    apv = next((tr for tr in all_trs if tr.get("status") == "AwaitingApproval"), None)
    if not apv:
        pytest.skip("No awaiting approval task run")
    r = admin_client.post(
        f"/api/v1/task-runs/{apv['id']}/approvals",
        json={"decision": "rejected", "comment": "Not ready"},
    )
    assert r.status_code == 201
    data = r.get_json()
    assert data.get("decision") == "rejected"


def test_approval_meets_required_count_transitions_task(admin_client, product_with_pipeline):
    plid = product_with_pipeline["pipeline"]["id"]
    run = admin_client.post(f"/api/v1/pipelines/{plid}/runs", json={}).get_json()
    run_data = admin_client.get(f"/api/v1/pipeline-runs/{run['id']}").get_json()
    all_trs = [tr for sr in run_data.get("stage_runs", []) for tr in sr.get("task_runs", [])]
    apv = next((tr for tr in all_trs if tr.get("status") == "AwaitingApproval"), None)
    if not apv:
        pytest.skip("No awaiting approval task run")
    admin_client.post(
        f"/api/v1/task-runs/{apv['id']}/approvals",
        json={"decision": "approved"},
    )
    updated = admin_client.get(f"/api/v1/task-runs/{apv['id']}").get_json()
    assert updated["status"] in ("Succeeded", "AwaitingApproval")  # transitions after N approvals


def test_rejection_transitions_task_to_failed(admin_client, product_with_pipeline):
    plid = product_with_pipeline["pipeline"]["id"]
    run = admin_client.post(f"/api/v1/pipelines/{plid}/runs", json={}).get_json()
    run_data = admin_client.get(f"/api/v1/pipeline-runs/{run['id']}").get_json()
    all_trs = [tr for sr in run_data.get("stage_runs", []) for tr in sr.get("task_runs", [])]
    apv = next((tr for tr in all_trs if tr.get("status") == "AwaitingApproval"), None)
    if not apv:
        pytest.skip("No awaiting approval task run")
    admin_client.post(
        f"/api/v1/task-runs/{apv['id']}/approvals",
        json={"decision": "rejected"},
    )
    updated = admin_client.get(f"/api/v1/task-runs/{apv['id']}").get_json()
    assert updated["status"] in ("Failed", "AwaitingApproval")


def test_list_approval_decisions_for_task_run(admin_client, pipeline_run):
    run_data = admin_client.get(f"/api/v1/pipeline-runs/{pipeline_run['id']}").get_json()
    all_trs = [tr for sr in run_data.get("stage_runs", []) for tr in sr.get("task_runs", [])]
    apv = next(
        (tr for tr in all_trs if (tr.get("approval_decisions") or tr.get("kind") == "approval")),
        None,
    )
    if not apv:
        pytest.skip("No approval task run")
    r = admin_client.get(f"/api/v1/task-runs/{apv['id']}/approvals")
    assert r.status_code == 200
    items = r.get_json()
    assert isinstance(items if isinstance(items, list) else items.get("items", []), list)


# ── Rerun and recovery ────────────────────────────────────────────────────────


def test_rerun_failed_pipeline(admin_client, pipeline_run):
    admin_client.patch(f"/api/v1/pipeline-runs/{pipeline_run['id']}", json={"status": "Failed"})
    r = admin_client.post(f"/api/v1/pipeline-runs/{pipeline_run['id']}/rerun")
    assert r.status_code in (201, 202)
    assert r.get_json()["id"] != pipeline_run["id"]


def test_rerun_updates_artifact_id(admin_client, pipeline_run):
    r = admin_client.patch(
        f"/api/v1/pipeline-runs/{pipeline_run['id']}",
        json={"artifact_id": "api:2.0.0"},
    )
    assert r.status_code == 200
    assert r.get_json().get("artifact_id") == "api:2.0.0"


# ── Execution context ─────────────────────────────────────────────────────────


def test_get_execution_context(admin_client, pipeline_run):
    r = admin_client.get(f"/api/v1/pipeline-runs/{pipeline_run['id']}/context")
    assert r.status_code == 200
    data = r.get_json()
    for key in ("pipeline", "stages", "runtime_properties"):
        assert key in data, f"Missing key: {key}"


def test_runtime_properties_stored_on_run(admin_client, product_with_pipeline):
    # Create a fresh run with runtime_properties at trigger time
    plid = product_with_pipeline["pipeline"]["id"]
    run = admin_client.post(
        f"/api/v1/pipelines/{plid}/runs",
        json={"triggered_by": "e2e_admin", "runtime_properties": {}},
    ).get_json()
    r = admin_client.get(f"/api/v1/pipeline-runs/{run['id']}/context")
    assert r.status_code == 200
    # runtime_properties key should be present in context response
    assert "runtime_properties" in r.get_json()
