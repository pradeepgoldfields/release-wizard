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
from app.models.task import ApprovalDecision, TaskRun
from app.routes._authz import current_user_id, require_product_access
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


def _pipeline_product_id(pipeline_id: str) -> str | None:
    """Return the product_id for a pipeline, or None if not found."""
    pl = db.session.get(Pipeline, pipeline_id)
    return pl.product_id if pl else None


def _release_product_id(release_id: str) -> str | None:
    """Return the product_id for a release, or None if not found."""
    rel = db.session.get(Release, release_id)
    return rel.product_id if rel else None


# ── Pipeline runs ─────────────────────────────────────────────────────────────


@runs_bp.get("/api/v1/pipelines/<pipeline_id>/runs")
def list_pipeline_runs(pipeline_id: str):
    """Return runs for a pipeline. Requires pipelines:view."""
    uid = current_user_id()
    pid = _pipeline_product_id(pipeline_id)
    if pid:
        err = require_product_access(uid, pid, "pipelines:view")
        if err:
            return err
    db.get_or_404(Pipeline, pipeline_id)
    query = PipelineRun.query.filter_by(pipeline_id=pipeline_id).order_by(
        PipelineRun.started_at.desc()
    )
    items, meta = paginate(query)
    return jsonify({"items": [r.to_dict() for r in items], "meta": meta})


@runs_bp.post("/api/v1/pipelines/<pipeline_id>/runs")
def create_pipeline_run(pipeline_id: str):
    """Trigger a new pipeline run. Requires pipelines:execute."""
    uid = current_user_id()
    pid = _pipeline_product_id(pipeline_id)
    if pid:
        err = require_product_access(uid, pid, "pipelines:execute")
        if err:
            return err
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
    """Return a single pipeline run. Requires pipelines:view."""
    uid = current_user_id()
    run = db.get_or_404(PipelineRun, run_id)
    pid = _pipeline_product_id(run.pipeline_id)
    if pid:
        err = require_product_access(uid, pid, "pipelines:view")
        if err:
            return err
    return jsonify(run.to_dict(include_stages=True))


@runs_bp.post("/api/v1/pipeline-runs/<run_id>/rerun")
def rerun_pipeline_run(run_id: str):
    """Re-trigger a pipeline run. Requires pipelines:execute."""
    uid = current_user_id()
    original = db.get_or_404(PipelineRun, run_id)
    pid = _pipeline_product_id(original.pipeline_id)
    if pid:
        err = require_product_access(uid, pid, "pipelines:execute")
        if err:
            return err
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
    """Re-run from a specific stage. Requires pipelines:execute."""
    uid = current_user_id()
    run = db.get_or_404(PipelineRun, run_id)
    pid = _pipeline_product_id(run.pipeline_id)
    if pid:
        err = require_product_access(uid, pid, "pipelines:execute")
        if err:
            return err
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
    """Update a pipeline run's status or artifact ID. Requires pipelines:edit."""
    uid = current_user_id()
    run = db.get_or_404(PipelineRun, run_id)
    pid = _pipeline_product_id(run.pipeline_id)
    if pid:
        err = require_product_access(uid, pid, "pipelines:edit")
        if err:
            return err
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
    """Return the full execution context for a pipeline run. Requires pipelines:view."""
    uid = current_user_id()
    run = db.get_or_404(PipelineRun, run_id)
    pid = _pipeline_product_id(run.pipeline_id)
    if pid:
        err = require_product_access(uid, pid, "pipelines:view")
        if err:
            return err
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
    """Return ISAE 3000 report. Requires compliance:view."""
    uid = current_user_id()
    run = db.get_or_404(PipelineRun, run_id)
    pid = _pipeline_product_id(run.pipeline_id)
    if pid:
        err = require_product_access(uid, pid, "compliance:view")
        if err:
            return err
    from app.services.framework_audit_service import build_isae_report  # noqa: PLC0415

    return jsonify(build_isae_report(run_id))


@runs_bp.get("/api/v1/pipeline-runs/<run_id>/audit/acf")
def get_acf_report(run_id: str):
    """Return ACF report. Requires compliance:view."""
    uid = current_user_id()
    run = db.get_or_404(PipelineRun, run_id)
    pid = _pipeline_product_id(run.pipeline_id)
    if pid:
        err = require_product_access(uid, pid, "compliance:view")
        if err:
            return err
    from app.services.framework_audit_service import build_acf_report  # noqa: PLC0415

    return jsonify(build_acf_report(run_id))


@runs_bp.get("/api/v1/pipeline-runs/<run_id>/audit/<framework>/pdf")
def export_run_audit_pdf(run_id: str, framework: str):
    """Export audit report as PDF. Requires compliance:view."""
    import io  # noqa: PLC0415

    from flask import send_file  # noqa: PLC0415

    uid = current_user_id()
    run = db.get_or_404(PipelineRun, run_id)
    pid = _pipeline_product_id(run.pipeline_id)
    if pid:
        err = require_product_access(uid, pid, "compliance:view")
        if err:
            return err

    from app.services.framework_audit_service import (  # noqa: PLC0415
        build_acf_report,
        build_isae_report,
    )

    try:
        if framework == "isae":
            report = build_isae_report(run_id)
        elif framework == "acf":
            report = build_acf_report(run_id)
        else:
            return jsonify({"error": f"Unknown framework: {framework}. Use 'isae' or 'acf'"}), 400
    except Exception as exc:
        return jsonify({"error": f"Failed to build {framework.upper()} report: {exc}"}), 500

    from app.services.pdf_service import export_audit_report_pdf  # noqa: PLC0415

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
    """Return runs for a release. Requires releases:view."""
    uid = current_user_id()
    pid = _release_product_id(release_id)
    if pid:
        err = require_product_access(uid, pid, "releases:view")
        if err:
            return err
    db.get_or_404(Release, release_id)
    query = ReleaseRun.query.filter_by(release_id=release_id).order_by(ReleaseRun.started_at.desc())
    items, meta = paginate(query)
    return jsonify({"items": [r.to_dict() for r in items], "meta": meta})


@runs_bp.post("/api/v1/releases/<release_id>/runs")
def create_release_run(release_id: str):
    """Trigger a new release run. Requires releases:execute."""
    uid = current_user_id()
    pid = _release_product_id(release_id)
    if pid:
        err = require_product_access(uid, pid, "releases:execute")
        if err:
            return err
    data = request.get_json(silent=True) or {}
    run = start_release_run(
        release_id=release_id,
        triggered_by=data.get("triggered_by", "system"),
        app=current_app._get_current_object(),
    )
    return jsonify(run.to_dict()), 201


@runs_bp.get("/api/v1/release-runs/<run_id>")
def get_release_run(run_id: str):
    """Return a single release run. Requires releases:view."""
    uid = current_user_id()
    run = db.get_or_404(ReleaseRun, run_id)
    pid = _release_product_id(run.release_id)
    if pid:
        err = require_product_access(uid, pid, "releases:view")
        if err:
            return err
    return jsonify(run.to_dict(include_pipeline_runs=True))


@runs_bp.patch("/api/v1/release-runs/<run_id>")
def update_release_run(run_id: str):
    """Update a release run's status. Requires releases:edit."""
    uid = current_user_id()
    run = db.get_or_404(ReleaseRun, run_id)
    pid = _release_product_id(run.release_id)
    if pid:
        err = require_product_access(uid, pid, "releases:edit")
        if err:
            return err
    data = request.get_json(silent=True) or {}
    if "status" in data:
        new_status = data["status"]
        if new_status not in VALID_STATUSES:
            return jsonify(
                {"error": f"Invalid status '{new_status}'. Valid values: {sorted(VALID_STATUSES)}"}
            ), 400
        run = update_run_status(run, new_status)
    return jsonify(run.to_dict())


# ── Approval decisions ────────────────────────────────────────────────────────


@runs_bp.get("/api/v1/task-runs/<task_run_id>/approvals")
def list_approvals(task_run_id: str):
    """Return all approval decisions for a task run. Requires pipelines:view."""
    uid = current_user_id()
    tr = db.get_or_404(TaskRun, task_run_id)
    sr = tr.stage_run
    if sr:
        run = db.session.get(PipelineRun, sr.pipeline_run_id)
        if run:
            pid = _pipeline_product_id(run.pipeline_id)
            if pid:
                err = require_product_access(uid, pid, "pipelines:view")
                if err:
                    return err
    return jsonify([d.to_dict() for d in tr.approval_decisions])


@runs_bp.post("/api/v1/task-runs/<task_run_id>/approvals")
def submit_approval(task_run_id: str):
    """Submit an approve or reject decision for an approval task run.
    Requires the calling user to be a listed approver.
    Body: {"decision": "approved"|"rejected", "comment": "..."}
    """
    import json as _json  # noqa: PLC0415
    from datetime import UTC, datetime  # noqa: PLC0415

    from app.models.auth import Group, Role, RoleBinding, User  # noqa: PLC0415
    from app.services.id_service import resource_id  # noqa: PLC0415

    uid = current_user_id()
    tr = db.get_or_404(TaskRun, task_run_id)

    if tr.status != "AwaitingApproval":
        return jsonify({"error": f"Task run is not awaiting approval (status: {tr.status})"}), 409

    task = tr.task
    approvers_spec = []
    if task and task.approval_approvers:
        try:
            approvers_spec = _json.loads(task.approval_approvers)
        except (ValueError, TypeError):
            approvers_spec = []

    user = db.session.get(User, uid)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Verify calling user is an eligible approver
    is_eligible = not approvers_spec  # if no specs, anyone with access can approve
    for spec in approvers_spec:
        ref_type = spec.get("type", "user")
        ref = spec.get("ref", "")
        if ref_type == "user" and ref in (user.username, user.id):
            is_eligible = True
            break
        if ref_type == "group":
            grp = Group.query.filter_by(name=ref).first()
            if grp and user in grp.members:
                is_eligible = True
                break
        if ref_type == "role":
            role = Role.query.filter_by(name=ref).first()
            if role and RoleBinding.query.filter_by(user_id=uid, role_id=role.id).first():
                is_eligible = True
                break

    if not is_eligible:
        return jsonify({"error": "You are not a listed approver for this task"}), 403

    existing = ApprovalDecision.query.filter_by(task_run_id=task_run_id, user_id=uid).first()
    if existing:
        return jsonify({"error": "You have already submitted a decision"}), 409

    data = request.get_json(silent=True) or {}
    decision = data.get("decision", "").lower()
    if decision not in ("approved", "rejected"):
        return jsonify({"error": "decision must be 'approved' or 'rejected'"}), 400

    ad = ApprovalDecision(
        id=resource_id("apv"),
        task_run_id=task_run_id,
        user_id=uid,
        decision=decision,
        comment=data.get("comment"),
        decided_at=datetime.now(UTC),
    )
    db.session.add(ad)

    if decision == "rejected":
        tr.status = "Failed"
        tr.finished_at = datetime.now(UTC)
        tr.logs = (tr.logs or "") + f"\n[REJECTED by {user.username}] {data.get('comment', '')}"
        db.session.commit()
        return jsonify({"status": "rejected", "task_run": tr.to_dict()}), 200

    db.session.flush()
    approved_count = ApprovalDecision.query.filter_by(
        task_run_id=task_run_id, decision="approved"
    ).count()
    required = (task.approval_required_count or 0) if task else 0
    total_approvers = len(approvers_spec)
    threshold = required if required > 0 else (total_approvers or 1)

    if approved_count >= threshold:
        tr.status = "Succeeded"
        tr.finished_at = datetime.now(UTC)
        tr.logs = (tr.logs or "") + f"\n[APPROVED — {approved_count}/{threshold} approvals received]"

    db.session.commit()
    return jsonify({
        "status": "recorded",
        "approvals": approved_count,
        "required": threshold,
        "task_run": tr.to_dict(),
    }), 200
