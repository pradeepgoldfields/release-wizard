"""HTTP handlers for PipelineRun and ReleaseRun resources.

Each run is identified by a time-sortable ULID-based ID:
  PipelineRun  →  ``plrun_<ULID>``
  ReleaseRun   →  ``rrun_<ULID>``
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.domain.enums import RunStatus
from app.extensions import db
from app.models.pipeline import Pipeline
from app.models.release import Release
from app.models.run import PipelineRun, ReleaseRun
from app.services.run_service import start_pipeline_run, start_release_run, update_run_status

runs_bp = Blueprint("runs", __name__)

#: Valid status values accepted by the PATCH endpoint.
VALID_STATUSES: frozenset[str] = frozenset(RunStatus)


# ── Pipeline runs ─────────────────────────────────────────────────────────────


@runs_bp.get("/api/v1/pipelines/<pipeline_id>/runs")
def list_pipeline_runs(pipeline_id: str):
    """Return all runs for a pipeline, newest first."""
    db.get_or_404(Pipeline, pipeline_id)
    runs = (
        PipelineRun.query.filter_by(pipeline_id=pipeline_id)
        .order_by(PipelineRun.started_at.desc())
        .all()
    )
    return jsonify([r.to_dict() for r in runs])


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


# ── Release runs ──────────────────────────────────────────────────────────────


@runs_bp.get("/api/v1/releases/<release_id>/runs")
def list_release_runs(release_id: str):
    """Return all runs for a release, newest first."""
    db.get_or_404(Release, release_id)
    runs = (
        ReleaseRun.query.filter_by(release_id=release_id)
        .order_by(ReleaseRun.started_at.desc())
        .all()
    )
    return jsonify([r.to_dict() for r in runs])


@runs_bp.post("/api/v1/releases/<release_id>/runs")
def create_release_run(release_id: str):
    """Trigger a new release run.

    Optional body: ``triggered_by``
    """
    data = request.get_json(silent=True) or {}
    run = start_release_run(
        release_id=release_id,
        triggered_by=data.get("triggered_by", "system"),
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
