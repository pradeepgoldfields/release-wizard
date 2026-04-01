"""HTTP handlers for PipelineRun and ReleaseRun resources.

Each run is identified by a time-sortable ULID-based ID:
  PipelineRun  →  ``plrun_<ULID>``
  ReleaseRun   →  ``rrun_<ULID>``
"""

from __future__ import annotations

import json

from flask import Blueprint, current_app, jsonify, request

from app.domain.enums import RunStatus
from app.extensions import db
from app.models.pipeline import Pipeline
from app.models.release import Release
from app.models.run import PipelineRun, ReleaseRun
from app.services.run_service import (
    restart_from_stage,
    start_pipeline_run,
    start_release_run,
    update_run_status,
)
from app.utils import paginate

runs_bp = Blueprint("runs", __name__)

#: Valid status values accepted by the PATCH endpoint.
VALID_STATUSES: frozenset[str] = frozenset(RunStatus)


# ── Pipeline runs ─────────────────────────────────────────────────────────────


@runs_bp.get("/api/v1/pipelines/<pipeline_id>/runs")
def list_pipeline_runs(pipeline_id: str):
    """Return runs for a pipeline, newest first.

    Query params: ``limit`` (default 50, max 200), ``offset`` (default 0).
    """
    db.get_or_404(Pipeline, pipeline_id)
    query = PipelineRun.query.filter_by(pipeline_id=pipeline_id).order_by(
        PipelineRun.started_at.desc()
    )
    items, meta = paginate(query)
    return jsonify({"items": [r.to_dict() for r in items], "meta": meta})


@runs_bp.post("/api/v1/pipelines/<pipeline_id>/runs")
def create_pipeline_run(pipeline_id: str):
    """Trigger a new pipeline run.

    Optional body: ``commit_sha``, ``artifact_id``, ``triggered_by``
    """
    data = request.get_json(silent=True) or {}
    run = start_pipeline_run(
        pipeline_id=pipeline_id,
        commit_sha=data.get("commit_sha"),
        artifact_id=data.get("artifact_id"),
        triggered_by=data.get("triggered_by", "system"),
        runtime_properties=data.get("runtime_properties"),
        app=current_app._get_current_object(),
    )
    return jsonify(run.to_dict()), 202


@runs_bp.get("/api/v1/pipeline-runs/<run_id>")
def get_pipeline_run(run_id: str):
    """Return a single pipeline run with its stage runs."""
    run = db.get_or_404(PipelineRun, run_id)
    return jsonify(run.to_dict(include_stages=True))


@runs_bp.post("/api/v1/pipeline-runs/<run_id>/rerun")
def rerun_pipeline_run(run_id: str):
    """Start a fresh pipeline run cloning commit/artifact from an existing run."""
    original = db.get_or_404(PipelineRun, run_id)
    data = request.get_json(silent=True) or {}
    triggered_by = data.get("triggered_by") or (original.triggered_by or "system")
    run = start_pipeline_run(
        pipeline_id=original.pipeline_id,
        commit_sha=original.commit_sha,
        artifact_id=original.artifact_id,
        triggered_by=triggered_by,
        app=current_app._get_current_object(),
    )
    return jsonify(run.to_dict()), 202


@runs_bp.post("/api/v1/pipeline-runs/<run_id>/stages/<stage_run_id>/rerun")
def rerun_from_stage(run_id: str, stage_run_id: str):
    """Re-run a pipeline from a specific stage (resets that stage and all subsequent)."""
    run = db.get_or_404(PipelineRun, run_id)
    data = request.get_json(silent=True) or {}
    triggered_by = data.get("triggered_by") or (run.triggered_by or "system")
    new_run = restart_from_stage(
        pipeline_run_id=run_id,
        stage_run_id=stage_run_id,
        triggered_by=triggered_by,
        app=current_app._get_current_object(),
    )
    return jsonify(new_run.to_dict()), 202


@runs_bp.patch("/api/v1/pipeline-runs/<run_id>")
def update_pipeline_run(run_id: str):
    """Update a pipeline run's status or artifact ID.

    Optional body: ``status``, ``artifact_id``
    Valid statuses: Pending, Running, Succeeded, Failed, Cancelled
    """
    run = db.get_or_404(PipelineRun, run_id)
    data = request.get_json(silent=True) or {}

    if "artifact_id" in data:
        run.artifact_id = data["artifact_id"]
        db.session.commit()

    if "status" in data:
        new_status = data["status"]
        if new_status not in VALID_STATUSES:
            return jsonify(
                {"error": f"Invalid status '{new_status}'. Valid values: {sorted(VALID_STATUSES)}"}
            ), 400
        run = update_run_status(run, new_status)

    return jsonify(run.to_dict())


@runs_bp.get("/api/v1/pipeline-runs/<run_id>/context")
def get_pipeline_run_context(run_id: str):
    """Return the full execution context for a pipeline run.

    Response shape::

        {
          "run_id": "plrun_...",
          "pipeline": { "id", "name", "git_repo", "git_branch" },
          "triggered_by": "...",
          "commit_sha": "...",
          "runtime_properties": { ... },          # pipeline-level props / webhook payload
          "stages": [
            {
              "stage_run_id": "...",
              "stage_name": "...",
              "runtime_properties": { ... },
              "tasks": [
                {
                  "task_run_id": "...",
                  "task_name": "...",
                  "context_env": { "CDT_PIPELINE_NAME": "...", ... },
                  "output_json": { ... } | null,
                  "user_input": { ... } | null
                }
              ]
            }
          ]
        }
    """
    run = db.get_or_404(PipelineRun, run_id)
    pipeline = run.pipeline

    stages_out = []
    for sr in sorted(run.stage_runs, key=lambda s: s.stage.order if s.stage else 0):
        tasks_out = []
        for tr in sorted(sr.task_runs, key=lambda t: t.task.order if t.task else 0):
            out_json = None
            if tr.output_json:
                try:
                    out_json = json.loads(tr.output_json)
                except (ValueError, TypeError):
                    out_json = tr.output_json

            user_inp = None
            if tr.user_input:
                try:
                    user_inp = json.loads(tr.user_input)
                except (ValueError, TypeError):
                    user_inp = tr.user_input

            ctx_env = {}
            if tr.context_env:
                try:
                    ctx_env = json.loads(tr.context_env)
                except (ValueError, TypeError):
                    ctx_env = {}

            tasks_out.append(
                {
                    "task_run_id": tr.id,
                    "task_name": tr.task.name if tr.task else tr.task_id,
                    "status": tr.status,
                    "context_env": ctx_env,
                    "output_json": out_json,
                    "user_input": user_inp,
                }
            )

        stages_out.append(
            {
                "stage_run_id": sr.id,
                "stage_name": sr.stage.name if sr.stage else sr.stage_id,
                "status": sr.status,
                "runtime_properties": json.loads(sr.runtime_properties or "{}"),
                "tasks": tasks_out,
            }
        )

    return jsonify(
        {
            "run_id": run.id,
            "pipeline": {
                "id": pipeline.id if pipeline else None,
                "name": pipeline.name if pipeline else None,
                "git_repo": pipeline.git_repo if pipeline else None,
                "git_branch": pipeline.git_branch if pipeline else None,
            },
            "triggered_by": run.triggered_by,
            "commit_sha": run.commit_sha,
            "artifact_id": run.artifact_id,
            "runtime_properties": json.loads(run.runtime_properties or "{}"),
            "stages": stages_out,
        }
    )


# ── Framework audit reports ───────────────────────────────────────────────────


@runs_bp.get("/api/v1/pipeline-runs/<run_id>/audit/isae")
def get_isae_report(run_id: str):
    """Return ISAE 3000 / SOC 2 Trust Service Criteria report for a pipeline run."""
    from app.services.framework_audit_service import build_isae_report

    report = build_isae_report(run_id)
    return jsonify(report)


@runs_bp.get("/api/v1/pipeline-runs/<run_id>/audit/acf")
def get_acf_report(run_id: str):
    """Return ACF (Australian Assurance & Compliance Framework) report for a pipeline run."""
    from app.services.framework_audit_service import build_acf_report

    report = build_acf_report(run_id)
    return jsonify(report)


@runs_bp.get("/api/v1/pipeline-runs/<run_id>/audit/<framework>/pdf")
def export_run_audit_pdf(run_id: str, framework: str):
    """Export ACF or ISAE audit report as PDF."""
    import io

    from flask import send_file

    from app.services.framework_audit_service import build_acf_report, build_isae_report

    try:
        if framework == "isae":
            report = build_isae_report(run_id)
        elif framework == "acf":
            report = build_acf_report(run_id)
        else:
            return jsonify({"error": f"Unknown framework: {framework}. Use 'isae' or 'acf'"}), 400
    except Exception as exc:
        return jsonify({"error": f"Failed to build {framework.upper()} report: {exc}"}), 500

    from app.services.pdf_service import export_audit_report_pdf

    try:
        pdf_bytes = export_audit_report_pdf(report)
    except Exception as exc:
        return jsonify({"error": f"PDF generation failed: {exc}"}), 500
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{framework}_audit_{run_id}.pdf",
    )


# ── Release runs ──────────────────────────────────────────────────────────────


@runs_bp.get("/api/v1/releases/<release_id>/runs")
def list_release_runs(release_id: str):
    """Return runs for a release, newest first.

    Query params: ``limit`` (default 50, max 200), ``offset`` (default 0).
    """
    db.get_or_404(Release, release_id)
    query = ReleaseRun.query.filter_by(release_id=release_id).order_by(ReleaseRun.started_at.desc())
    items, meta = paginate(query)
    return jsonify({"items": [r.to_dict() for r in items], "meta": meta})


@runs_bp.post("/api/v1/releases/<release_id>/runs")
def create_release_run(release_id: str):
    """Trigger a new release run.

    Optional body: ``triggered_by``
    """
    data = request.get_json(silent=True) or {}
    run = start_release_run(
        release_id=release_id,
        triggered_by=data.get("triggered_by", "system"),
        app=current_app._get_current_object(),
    )
    return jsonify(run.to_dict()), 201


@runs_bp.get("/api/v1/release-runs/<run_id>")
def get_release_run(run_id: str):
    """Return a single release run with its pipeline runs."""
    run = db.get_or_404(ReleaseRun, run_id)
    return jsonify(run.to_dict(include_pipeline_runs=True))


@runs_bp.patch("/api/v1/release-runs/<run_id>")
def update_release_run(run_id: str):
    """Update a release run's status.

    Optional body: ``status``
    """
    run = db.get_or_404(ReleaseRun, run_id)
    data = request.get_json(silent=True) or {}
    if "status" in data:
        new_status = data["status"]
        if new_status not in VALID_STATUSES:
            return jsonify(
                {"error": f"Invalid status '{new_status}'. Valid values: {sorted(VALID_STATUSES)}"}
            ), 400
        run = update_run_status(run, new_status)
    return jsonify(run.to_dict())
