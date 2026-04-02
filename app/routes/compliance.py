"""HTTP handlers for compliance rules and the immutable audit event log."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.domain.enums import ComplianceRating
from app.extensions import db
from app.models.compliance import AuditEvent, ComplianceRule
from app.services.id_service import resource_id

compliance_bp = Blueprint("compliance", __name__, url_prefix="/api/v1/compliance")

VALID_RATINGS: frozenset[str] = frozenset(ComplianceRating)


@compliance_bp.get("/rules")
def list_rules():
    """Return all active compliance admission rules."""
    rules = ComplianceRule.query.filter_by(is_active=True).all()
    return jsonify([r.to_dict() for r in rules])


@compliance_bp.post("/rules")
def create_rule():
    """Create a compliance admission rule.

    Required body: ``scope``, ``min_rating``
    Optional: ``description``

    ``scope`` examples: ``environment:prod``, ``product:api-service``, ``organization``
    ``min_rating`` must be one of: Bronze, Silver, Gold, Platinum
    """
    data = request.get_json(silent=True) or {}
    scope = (data.get("scope") or "").strip()
    min_rating = (data.get("min_rating") or "").strip()

    if not scope:
        return jsonify({"error": "scope is required"}), 400
    if min_rating not in VALID_RATINGS:
        return jsonify({"error": f"min_rating must be one of: {sorted(VALID_RATINGS)}"}), 400

    rule = ComplianceRule(
        id=resource_id("rule"),
        description=data.get("description"),
        scope=scope,
        min_rating=min_rating,
    )
    db.session.add(rule)
    db.session.commit()
    return jsonify(rule.to_dict()), 201


@compliance_bp.patch("/rules/<rule_id>")
def update_rule(rule_id: str):
    """Update a compliance rule's description, scope, or min_rating."""
    rule = db.get_or_404(ComplianceRule, rule_id)
    data = request.get_json(silent=True) or {}
    if "description" in data:
        rule.description = data["description"]
    if "scope" in data:
        scope = (data["scope"] or "").strip()
        if not scope:
            return jsonify({"error": "scope cannot be empty"}), 400
        rule.scope = scope
    if "min_rating" in data:
        if data["min_rating"] not in VALID_RATINGS:
            return jsonify({"error": f"min_rating must be one of: {sorted(VALID_RATINGS)}"}), 400
        rule.min_rating = data["min_rating"]
    db.session.commit()
    return jsonify(rule.to_dict())


@compliance_bp.delete("/rules/<rule_id>")
def disable_rule(rule_id: str):
    """Soft-delete (disable) a compliance rule — it is not physically removed."""
    rule = db.get_or_404(ComplianceRule, rule_id)
    rule.is_active = False
    db.session.commit()
    return "", 204


@compliance_bp.get("/iso27001")
def get_iso27001():
    """Evaluate the platform against ISO/IEC 27001:2022 Annex A controls."""
    from app.services.iso27001_service import evaluate_iso27001

    return jsonify(evaluate_iso27001())


@compliance_bp.get("/audit-events")
def list_audit_events():
    """Return recent audit events, optionally filtered by resource.

    Query params:
        ``resource_type`` — filter by resource type (e.g. ``release``)
        ``resource_id``   — filter by specific resource ID
        ``limit``         — maximum number of events to return (default 100)
    """
    resource_type = request.args.get("resource_type")
    resource_id_filter = request.args.get("resource_id")
    limit = min(int(request.args.get("limit", 100)), 500)

    query = AuditEvent.query
    if resource_type:
        query = query.filter_by(resource_type=resource_type)
    if resource_id_filter:
        query = query.filter_by(resource_id=resource_id_filter)

    events = query.order_by(AuditEvent.timestamp.desc()).limit(limit).all()
    return jsonify([e.to_dict() for e in events])
