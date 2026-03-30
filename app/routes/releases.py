"""HTTP handlers for Release resources and pipeline admission control."""

from __future__ import annotations

import io

from flask import Blueprint, jsonify, request, send_file

from app.extensions import db
from app.models.pipeline import Pipeline
from app.models.product import Product
from app.models.release import Release
from app.services.audit_service import build_release_audit_report
from app.services.pdf_service import export_audit_report_pdf
from app.services.release_service import attach_pipeline_to_release, create_release

releases_bp = Blueprint("releases", __name__, url_prefix="/api/v1/products/<product_id>/releases")


@releases_bp.get("")
def list_releases(product_id: str):
    """Return all releases for a product, newest first."""
    db.get_or_404(Product, product_id)
    releases = (
        Release.query.filter_by(product_id=product_id).order_by(Release.created_at.desc()).all()
    )
    return jsonify([r.to_dict() for r in releases])


@releases_bp.post("")
def create_release_endpoint(product_id: str):
    """Create a new release under a product.

    Required body: ``name``
    Optional: ``version``, ``description``, ``created_by``
    """
    db.get_or_404(Product, product_id)
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
    """Return a single release with its attached pipelines."""
    release = Release.query.filter_by(id=release_id, product_id=product_id).first_or_404()
    return jsonify(release.to_dict(include_pipelines=True))


@releases_bp.put("/<release_id>")
def update_release(product_id: str, release_id: str):
    """Update a release's name, version, or description."""
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
    """Permanently delete a release."""
    release = Release.query.filter_by(id=release_id, product_id=product_id).first_or_404()
    db.session.delete(release)
    db.session.commit()
    return "", 204


# ── Pipeline attachment ────────────────────────────────────────────────────────


@releases_bp.post("/<release_id>/pipelines")
def attach_pipeline(product_id: str, release_id: str):
    """Attach a pipeline to a release, subject to compliance admission rules.

    Required body: ``pipeline_id``
    Optional: ``requested_by``
    """
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

    return jsonify(
        {
            "release_id": release_id,
            "pipeline_id": pipeline_id,
            "admission": "passed",
        }
    ), 200


@releases_bp.delete("/<release_id>/pipelines/<pipeline_id>")
def detach_pipeline(product_id: str, release_id: str, pipeline_id: str):
    """Remove a pipeline from a release."""
    release = Release.query.filter_by(id=release_id, product_id=product_id).first_or_404()
    pipeline = db.get_or_404(Pipeline, pipeline_id)
    if pipeline in release.pipelines:
        release.pipelines.remove(pipeline)
        db.session.commit()
    return "", 204


# ── Audit report ───────────────────────────────────────────────────────────────


@releases_bp.get("/<release_id>/audit")
def get_audit_report(product_id: str, release_id: str):
    """Return the structured audit report for a release as JSON."""
    Release.query.filter_by(id=release_id, product_id=product_id).first_or_404()
    report = build_release_audit_report(release_id)
    return jsonify(report)


@releases_bp.post("/<release_id>/audit/export")
def export_audit_pdf(product_id: str, release_id: str):
    """Generate and stream the audit report as a PDF file.

    Requires WeasyPrint system libraries (available inside the UBI container).
    Returns 501 with a helpful message if libraries are absent (e.g. on Windows dev).
    """
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
