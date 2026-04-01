"""Framework controls configuration API.

GET    /api/v1/framework-controls/<framework>          — list all controls (merged with built-ins)
PUT    /api/v1/framework-controls/<framework>/<id>     — update (enable/disable/override fields)
POST   /api/v1/framework-controls/<framework>          — add a custom control
DELETE /api/v1/framework-controls/<framework>/<id>     — delete a custom control (built-ins can only be disabled)
POST   /api/v1/framework-controls/<framework>/reset    — reset all to defaults (delete all DB rows for framework)
"""

from __future__ import annotations

import json

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.framework_control import FrameworkControl

framework_controls_bp = Blueprint(
    "framework_controls", __name__, url_prefix="/api/v1/framework-controls"
)


def _builtin_controls(framework: str) -> list[dict]:
    if framework == "isae":
        from app.services.framework_audit_service import SOC2_CRITERIA

        return SOC2_CRITERIA
    if framework == "acf":
        from app.services.framework_audit_service import ACF_DOMAINS

        return ACF_DOMAINS
    return []


def _merge(builtin: dict, override: FrameworkControl) -> dict:
    """Merge a built-in control dict with a DB override row."""
    merged = dict(builtin)
    merged["enabled"] = override.enabled
    merged["is_builtin"] = override.is_builtin
    merged["updated_at"] = override.updated_at.isoformat() if override.updated_at else None
    merged["updated_by"] = override.updated_by
    if override.title is not None:
        merged["title"] = override.title
    if override.description is not None:
        merged["description"] = override.description
    if override.category is not None:
        merged["category"] = override.category
    if override.category_label is not None:
        merged["category_label"] = override.category_label
    if override.task_types_json is not None:
        merged["task_types"] = json.loads(override.task_types_json)
    if override.dimension_keys_json is not None:
        merged["dimension_keys"] = json.loads(override.dimension_keys_json)
    if override.evidence_keywords_json is not None:
        merged["evidence_keywords"] = json.loads(override.evidence_keywords_json)
    if override.weight is not None:
        merged["weight"] = override.weight
    return merged


@framework_controls_bp.get("/<framework>")
def list_controls(framework: str):
    if framework not in ("isae", "acf"):
        return jsonify({"error": "framework must be 'isae' or 'acf'"}), 400

    builtins = _builtin_controls(framework)
    overrides = {r.id: r for r in FrameworkControl.query.filter_by(framework=framework).all()}

    result = []
    # Built-in controls (merged with any DB overrides)
    for b in builtins:
        ctrl_id = b["id"]
        if ctrl_id in overrides:
            result.append(_merge(b, overrides[ctrl_id]))
        else:
            result.append(
                {**b, "enabled": True, "is_builtin": True, "updated_at": None, "updated_by": None}
            )

    # Custom controls (not in built-ins)
    builtin_ids = {b["id"] for b in builtins}
    for row in overrides.values():
        if row.id not in builtin_ids:
            result.append(row.to_dict())

    return jsonify(result)


@framework_controls_bp.put("/<framework>/<ctrl_id>")
def update_control(framework: str, ctrl_id: str):
    if framework not in ("isae", "acf"):
        return jsonify({"error": "framework must be 'isae' or 'acf'"}), 400

    data = request.get_json(silent=True) or {}
    from app.routes.auth import _current_user

    user = _current_user()

    row = FrameworkControl.query.filter_by(framework=framework, id=ctrl_id).first()
    if not row:
        # Determine if this is a built-in ID
        builtin_ids = {b["id"] for b in _builtin_controls(framework)}
        is_builtin = ctrl_id in builtin_ids
        row = FrameworkControl(id=ctrl_id, framework=framework, is_builtin=is_builtin)
        db.session.add(row)

    if "enabled" in data:
        row.enabled = bool(data["enabled"])
    if "title" in data:
        row.title = data["title"] or None
    if "description" in data:
        row.description = data["description"] or None
    if "category" in data:
        row.category = data["category"] or None
    if "category_label" in data:
        row.category_label = data["category_label"] or None
    if "task_types" in data:
        row.task_types_json = (
            json.dumps(data["task_types"]) if data["task_types"] is not None else None
        )
    if "dimension_keys" in data:
        row.dimension_keys_json = (
            json.dumps(data["dimension_keys"]) if data["dimension_keys"] is not None else None
        )
    if "evidence_keywords" in data:
        row.evidence_keywords_json = (
            json.dumps(data["evidence_keywords"]) if data["evidence_keywords"] is not None else None
        )
    if "weight" in data:
        row.weight = int(data["weight"]) if data["weight"] is not None else None

    row.updated_by = user.username if user else None
    db.session.commit()

    # Return merged view
    builtins = {b["id"]: b for b in _builtin_controls(framework)}
    if ctrl_id in builtins:
        return jsonify(_merge(builtins[ctrl_id], row))
    return jsonify(row.to_dict())


@framework_controls_bp.post("/<framework>")
def add_custom_control(framework: str):
    if framework not in ("isae", "acf"):
        return jsonify({"error": "framework must be 'isae' or 'acf'"}), 400

    data = request.get_json(silent=True) or {}
    ctrl_id = (data.get("id") or "").strip()
    if not ctrl_id:
        return jsonify({"error": "id is required"}), 400
    if FrameworkControl.query.filter_by(framework=framework, id=ctrl_id).first():
        return jsonify({"error": f"Control '{ctrl_id}' already exists"}), 409

    from app.routes.auth import _current_user

    user = _current_user()

    row = FrameworkControl(
        id=ctrl_id,
        framework=framework,
        is_builtin=False,
        enabled=True,
        title=data.get("title") or ctrl_id,
        description=data.get("description"),
        category=data.get("category"),
        category_label=data.get("category_label"),
        task_types_json=json.dumps(data["task_types"]) if data.get("task_types") else None,
        dimension_keys_json=json.dumps(data["dimension_keys"])
        if data.get("dimension_keys")
        else None,
        evidence_keywords_json=json.dumps(data["evidence_keywords"])
        if data.get("evidence_keywords")
        else None,
        weight=int(data["weight"]) if data.get("weight") else 2,
        updated_by=user.username if user else None,
    )
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict()), 201


@framework_controls_bp.delete("/<framework>/<ctrl_id>")
def delete_control(framework: str, ctrl_id: str):
    if framework not in ("isae", "acf"):
        return jsonify({"error": "framework must be 'isae' or 'acf'"}), 400

    row = FrameworkControl.query.filter_by(framework=framework, id=ctrl_id).first()
    if not row:
        return "", 204

    builtin_ids = {b["id"] for b in _builtin_controls(framework)}
    if ctrl_id in builtin_ids:
        return jsonify(
            {"error": "Built-in controls cannot be deleted — use enabled=false to disable them"}
        ), 400

    db.session.delete(row)
    db.session.commit()
    return "", 204


@framework_controls_bp.post("/<framework>/reset")
def reset_controls(framework: str):
    if framework not in ("isae", "acf"):
        return jsonify({"error": "framework must be 'isae' or 'acf'"}), 400

    FrameworkControl.query.filter_by(framework=framework).delete()
    db.session.commit()
    return jsonify({"ok": True, "message": f"{framework.upper()} controls reset to defaults"})
