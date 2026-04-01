"""HTTP handlers for Release resources and pipeline admission control."""

from __future__ import annotations

import io
import json

from flask import Blueprint, jsonify, request, send_file

from app.extensions import db
from app.models.application import ApplicationArtifact
from app.models.pipeline import Pipeline
from app.models.release import Release, ReleaseApplicationGroup
from app.routes._authz import current_user_id, require_product_access
from app.services.audit_service import build_release_audit_report
from app.services.id_service import resource_id
from app.services.pdf_service import export_audit_report_pdf
from app.services.release_service import attach_pipeline_to_release, create_release

releases_bp = Blueprint("releases", __name__, url_prefix="/api/v1/products/<product_id>/releases")


@releases_bp.get("")
def list_releases(product_id: str):
    """Return all releases for a product. Requires releases:view."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "releases:view")
    if err:
        return err
    releases = (
        Release.query.filter_by(product_id=product_id).order_by(Release.created_at.desc()).all()
    )
    return jsonify([r.to_dict() for r in releases])


@releases_bp.post("")
def create_release_endpoint(product_id: str):
    """Create a new release. Requires releases:create."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "releases:create")
    if err:
        return err
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    release = create_release(
        product_id=product_id,
        name=name,
        version=data.get("version"),
        description=data.get("description"),
        created_by=data.get("created_by", "system"),
    )
    return jsonify(release.to_dict()), 201


@releases_bp.get("/<release_id>")
def get_release(product_id: str, release_id: str):
    """Return a single release. Requires releases:view."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "releases:view")
    if err:
        return err
    release = Release.query.filter_by(id=release_id, product_id=product_id).first_or_404()
    return jsonify(release.to_dict(include_pipelines=True))


@releases_bp.put("/<release_id>")
def update_release(product_id: str, release_id: str):
    """Update a release. Requires releases:edit."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "releases:edit")
    if err:
        return err
    release = Release.query.filter_by(id=release_id, product_id=product_id).first_or_404()
    data = request.get_json(silent=True) or {}
    if "name" in data:
        release.name = (data["name"] or "").strip() or release.name
    if "version" in data:
        release.version = data["version"] or None
    if "description" in data:
        release.description = data["description"] or None
    db.session.commit()
    return jsonify(release.to_dict())


@releases_bp.delete("/<release_id>")
def delete_release(product_id: str, release_id: str):
    """Delete a release. Requires releases:delete."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "releases:delete")
    if err:
        return err
    release = Release.query.filter_by(id=release_id, product_id=product_id).first_or_404()
    db.session.delete(release)
    db.session.commit()
    return "", 204


# ── Pipeline attachment ────────────────────────────────────────────────────────


@releases_bp.post("/<release_id>/pipelines")
def attach_pipeline(product_id: str, release_id: str):
    """Attach a pipeline to a release. Requires releases:edit."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "releases:edit")
    if err:
        return err
    data = request.get_json(silent=True) or {}
    pipeline_id = (data.get("pipeline_id") or "").strip()
    if not pipeline_id:
        return jsonify({"error": "pipeline_id is required"}), 400
    result = attach_pipeline_to_release(
        product_id=product_id,
        release_id=release_id,
        pipeline_id=pipeline_id,
        requested_by=data.get("requested_by", "unknown"),
    )
    if not result["allowed"]:
        return jsonify(
            {
                "error": "Pipeline does not meet compliance requirements",
                "violations": result["violations"],
            }
        ), 422
    return jsonify({"release_id": release_id, "pipeline_id": pipeline_id, "admission": "passed"}), 200


@releases_bp.delete("/<release_id>/pipelines/<pipeline_id>")
def detach_pipeline(product_id: str, release_id: str, pipeline_id: str):
    """Remove a pipeline from a release. Requires releases:edit."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "releases:edit")
    if err:
        return err
    release = Release.query.filter_by(id=release_id, product_id=product_id).first_or_404()
    pipeline = db.get_or_404(Pipeline, pipeline_id)
    if pipeline in release.pipelines:
        release.pipelines.remove(pipeline)
        db.session.commit()
    return "", 204


# ── Application groups ────────────────────────────────────────────────────────


@releases_bp.get("/<release_id>/application-groups")
def list_application_groups(product_id: str, release_id: str):
    """Return application groups for a release. Requires releases:view."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "releases:view")
    if err:
        return err
    release = Release.query.filter_by(id=release_id, product_id=product_id).first_or_404()
    return jsonify([g.to_dict() for g in release.application_groups])


@releases_bp.post("/<release_id>/application-groups")
def add_application_group(product_id: str, release_id: str):
    """Attach an application group to a release. Requires releases:edit."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "releases:edit")
    if err:
        return err
    release = Release.query.filter_by(id=release_id, product_id=product_id).first_or_404()
    data = request.get_json(silent=True) or {}
    application_id = (data.get("application_id") or "").strip()
    pipeline_ids = data.get("pipeline_ids") or []
    if not application_id:
        return jsonify({"error": "application_id is required"}), 400
    if not isinstance(pipeline_ids, list):
        return jsonify({"error": "pipeline_ids must be a list"}), 400
    app = ApplicationArtifact.query.filter_by(
        id=application_id, product_id=product_id
    ).first_or_404()
    existing = ReleaseApplicationGroup.query.filter_by(
        release_id=release_id, application_id=application_id
    ).first()
    if existing:
        db.session.delete(existing)
    group = ReleaseApplicationGroup(
        id=resource_id("rag"),
        release_id=release.id,
        application_id=app.id,
        execution_mode=data.get("execution_mode", "sequential"),
        pipeline_ids=json.dumps(pipeline_ids),
        order=data.get("order", len(release.application_groups)),
    )
    db.session.add(group)
    db.session.commit()
    return jsonify(group.to_dict()), 201


@releases_bp.delete("/<release_id>/application-groups/<group_id>")
def remove_application_group(product_id: str, release_id: str, group_id: str):
    """Remove an application group. Requires releases:edit."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "releases:edit")
    if err:
        return err
    group = ReleaseApplicationGroup.query.filter_by(
        id=group_id, release_id=release_id
    ).first_or_404()
    db.session.delete(group)
    db.session.commit()
    return "", 204


# ── Audit report ───────────────────────────────────────────────────────────────


@releases_bp.get("/<release_id>/audit")
def get_audit_report(product_id: str, release_id: str):
    """Return the audit report as JSON. Requires releases:view."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "releases:view")
    if err:
        return err
    Release.query.filter_by(id=release_id, product_id=product_id).first_or_404()
    report = build_release_audit_report(release_id)
    return jsonify(report)


@releases_bp.get("/<release_id>/audit/export")
def export_audit_pdf(product_id: str, release_id: str):
    """Stream the audit report as PDF. Requires releases:view."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "releases:view")
    if err:
        return err
    Release.query.filter_by(id=release_id, product_id=product_id).first_or_404()
    report = build_release_audit_report(release_id)
    try:
        pdf_bytes = export_audit_report_pdf(report)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 501
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"audit_{release_id}.pdf",
    )
