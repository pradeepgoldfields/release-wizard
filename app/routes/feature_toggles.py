"""Feature toggle (feature flag) API."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.feature_toggle import FeatureToggle
from app.routes._authz import current_user_id, require_admin
from app.services.id_service import resource_id

feature_toggles_bp = Blueprint("feature_toggles", __name__, url_prefix="/api/v1/feature-toggles")


@feature_toggles_bp.get("")
def list_toggles():
    """Return all feature toggles. Any authenticated user can read."""
    current_user_id()
    toggles = FeatureToggle.query.order_by(FeatureToggle.category, FeatureToggle.label).all()
    return jsonify([t.to_dict() for t in toggles])


@feature_toggles_bp.post("")
def create_toggle():
    """Create a feature toggle. Requires admin."""
    uid = current_user_id()
    err = require_admin(uid)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    label = (data.get("label") or "").strip()
    if not key or not label:
        return jsonify({"error": "key and label are required"}), 400
    if FeatureToggle.query.filter_by(key=key).first():
        return jsonify({"error": f"Toggle '{key}' already exists"}), 409
    toggle = FeatureToggle(
        id=resource_id("ftg"),
        key=key,
        label=label,
        description=data.get("description", ""),
        category=data.get("category", "general"),
        enabled=bool(data.get("enabled", False)),
    )
    db.session.add(toggle)
    db.session.commit()
    return jsonify(toggle.to_dict()), 201


@feature_toggles_bp.get("/<toggle_id>")
def get_toggle(toggle_id: str):
    """Return a single toggle by id or key."""
    current_user_id()
    toggle = (
        FeatureToggle.query.filter_by(id=toggle_id).first()
        or FeatureToggle.query.filter_by(key=toggle_id).first_or_404()
    )
    return jsonify(toggle.to_dict())


@feature_toggles_bp.patch("/<toggle_id>")
def update_toggle(toggle_id: str):
    """Update a toggle (enable/disable or change metadata). Requires admin."""
    uid = current_user_id()
    err = require_admin(uid)
    if err:
        return err
    toggle = (
        FeatureToggle.query.filter_by(id=toggle_id).first()
        or FeatureToggle.query.filter_by(key=toggle_id).first_or_404()
    )
    data = request.get_json(silent=True) or {}
    for field in ("label", "description", "category"):
        if field in data:
            setattr(toggle, field, data[field])
    if "enabled" in data:
        toggle.enabled = bool(data["enabled"])
    db.session.commit()
    return jsonify(toggle.to_dict())


@feature_toggles_bp.delete("/<toggle_id>")
def delete_toggle(toggle_id: str):
    """Delete a feature toggle. Requires admin."""
    uid = current_user_id()
    err = require_admin(uid)
    if err:
        return err
    toggle = (
        FeatureToggle.query.filter_by(id=toggle_id).first()
        or FeatureToggle.query.filter_by(key=toggle_id).first_or_404()
    )
    db.session.delete(toggle)
    db.session.commit()
    return "", 204
