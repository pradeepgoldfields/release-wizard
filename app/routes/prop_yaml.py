"""Property YAML Language — parse, validate, export, and apply property definitions.

The property YAML language lets you define all properties for a scope (product,
pipeline, stage, or task) in a single document, edit them in a text editor, and
push them back to the database in one operation.

Document schema
---------------
Each document is a mapping with two top-level keys:

    scope:
      type: pipeline          # product | pipeline | stage | task
      id: <owner_id>          # the resource UUID
      name: My Pipeline       # informational only, not stored

    properties:
      DEPLOY_TIMEOUT:         # property name (key)
        type: number          # string | number | boolean | secret | json
        value: 300
        description: Seconds before a deploy is considered timed out
        required: true

      DATABASE_URL:
        type: secret
        value: ""             # leave blank — set at runtime
        required: true

      FEATURE_FLAGS:
        type: json
        value:
          new_ui: true
          beta_mode: false

      ENVIRONMENT:
        type: string
        value: staging
        description: Target environment for this pipeline

Endpoints
---------
  GET  /api/v1/prop-yaml/{owner_type}/{owner_id}          export scope → YAML text
  POST /api/v1/prop-yaml/{owner_type}/{owner_id}/validate  parse + validate, return errors
  POST /api/v1/prop-yaml/{owner_type}/{owner_id}/apply     parse + validate + upsert
"""

from __future__ import annotations

import json as _json
from typing import Any

import yaml
from flask import Blueprint, Response, jsonify, request

from app.extensions import db

prop_yaml_bp = Blueprint("prop_yaml", __name__, url_prefix="/api/v1")

_VALID_OWNER_TYPES: frozenset[str] = frozenset({"product", "pipeline", "stage", "task"})
_VALID_VALUE_TYPES: frozenset[str] = frozenset({"string", "number", "boolean", "secret", "json"})


# ── Serialisation helpers ─────────────────────────────────────────────────────


def _coerce_value_for_yaml(value: str | None, value_type: str) -> Any:
    """Return value in a YAML-friendly Python form (not always a string)."""
    if value is None:
        return None
    if value_type == "number":
        try:
            return float(value) if "." in value else int(value)
        except (ValueError, TypeError):
            return value
    if value_type == "boolean":
        return value.lower() in ("true", "1", "yes")
    if value_type == "json":
        try:
            return _json.loads(value)
        except (ValueError, TypeError):
            return value
    if value_type == "secret":
        return ""  # never export secret values
    return value


def _export_scope(owner_type: str, owner_id: str) -> dict[str, Any]:
    """Build the property YAML document for a single scope."""
    from app.models.property import Property

    props = (
        Property.query.filter_by(owner_type=owner_type, owner_id=owner_id)
        .order_by(Property.name)
        .all()
    )

    # Try to look up a human name for the scope
    scope_name = _scope_name(owner_type, owner_id)

    prop_map: dict[str, Any] = {}
    for p in props:
        entry: dict[str, Any] = {"type": p.value_type or "string"}
        if p.value_type == "secret":
            entry["value"] = ""  # never export secrets
        else:
            entry["value"] = _coerce_value_for_yaml(p.value, p.value_type or "string")
        if p.description:
            entry["description"] = p.description
        if p.is_required:
            entry["required"] = True
        prop_map[p.name] = entry

    return {
        "scope": {
            "type": owner_type,
            "id": owner_id,
            "name": scope_name,
        },
        "properties": prop_map,
    }


def _scope_name(owner_type: str, owner_id: str) -> str:
    """Return a human-readable name for the scope, or the ID if not found."""
    try:
        if owner_type == "product":
            from app.models.product import Product

            obj = db.session.get(Product, owner_id)
        elif owner_type == "pipeline":
            from app.models.pipeline import Pipeline

            obj = db.session.get(Pipeline, owner_id)
        elif owner_type == "stage":
            from app.models.pipeline import Stage

            obj = db.session.get(Stage, owner_id)
        elif owner_type == "task":
            from app.models.task import Task

            obj = db.session.get(Task, owner_id)
        else:
            return owner_id
        return obj.name if obj and hasattr(obj, "name") else owner_id
    except Exception:
        return owner_id


# ── Validation ────────────────────────────────────────────────────────────────


class _ValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _parse_and_validate(raw: str) -> tuple[str, str, list[dict[str, Any]]]:
    """Parse YAML text and return (owner_type, owner_id, prop_specs).

    Raises _ValidationError with a list of human-readable messages on any problem.
    """
    errors: list[str] = []

    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise _ValidationError([f"YAML parse error: {exc}"]) from exc

    if not isinstance(doc, dict):
        raise _ValidationError(["Document must be a YAML mapping"])

    # ── scope block ──────────────────────────────────────────────────────────
    scope = doc.get("scope")
    if not isinstance(scope, dict):
        errors.append("'scope' must be a mapping with keys: type, id")
        raise _ValidationError(errors)

    owner_type = str(scope.get("type") or "").strip()
    owner_id = str(scope.get("id") or "").strip()

    if owner_type not in _VALID_OWNER_TYPES:
        errors.append(
            f"scope.type must be one of: {', '.join(sorted(_VALID_OWNER_TYPES))}; got {owner_type!r}"
        )
    if not owner_id:
        errors.append("scope.id is required")

    if errors:
        raise _ValidationError(errors)

    # ── properties block ─────────────────────────────────────────────────────
    raw_props = doc.get("properties")
    if raw_props is None:
        return owner_type, owner_id, []

    if not isinstance(raw_props, dict):
        raise _ValidationError(["'properties' must be a mapping of name → definition"])

    prop_specs: list[dict[str, Any]] = []

    for name, defn in raw_props.items():
        name = str(name).strip()
        if not name:
            errors.append("Property name cannot be empty")
            continue

        if defn is None:
            # bare key — treat as string with no value
            defn = {}

        if not isinstance(defn, dict):
            # shorthand: PROP_NAME: some_value  (type inferred)
            defn = {"value": defn}

        value_type = str(defn.get("type") or "string").strip()
        if value_type not in _VALID_VALUE_TYPES:
            errors.append(
                f"  {name}: type must be one of {', '.join(sorted(_VALID_VALUE_TYPES))}; got {value_type!r}"
            )
            value_type = "string"

        raw_value = defn.get("value")
        # Normalise value to string for storage (same as the DB model)
        if raw_value is None:
            str_value = None
        elif value_type == "boolean":
            str_value = "true" if raw_value in (True, "true", "1", "yes") else "false"
        elif value_type == "number":
            str_value = str(raw_value)
        elif value_type == "json":
            if isinstance(raw_value, dict | list):
                str_value = _json.dumps(raw_value)
            else:
                try:
                    _json.loads(str(raw_value))  # validate it parses
                    str_value = str(raw_value)
                except (ValueError, TypeError):
                    errors.append(f"  {name}: value is not valid JSON")
                    str_value = str(raw_value)
        else:
            str_value = str(raw_value) if raw_value is not None else None

        is_required = bool(defn.get("required", False))
        description = str(defn.get("description") or "").strip() or None

        prop_specs.append(
            {
                "name": name,
                "value_type": value_type,
                "value": str_value,
                "description": description,
                "is_required": is_required,
            }
        )

    if errors:
        raise _ValidationError(errors)

    return owner_type, owner_id, prop_specs


# ── Routes ────────────────────────────────────────────────────────────────────


@prop_yaml_bp.get("/prop-yaml/<owner_type>/<owner_id>")
def export_prop_yaml(owner_type: str, owner_id: str):
    """Return properties for a scope as a YAML document."""
    if owner_type not in _VALID_OWNER_TYPES:
        return jsonify({"error": f"Invalid owner_type: {owner_type}"}), 400

    doc = _export_scope(owner_type, owner_id)
    return Response(
        yaml.dump(doc, allow_unicode=True, sort_keys=False, default_flow_style=False),
        mimetype="text/yaml",
    )


@prop_yaml_bp.post("/prop-yaml/<owner_type>/<owner_id>/validate")
def validate_prop_yaml(owner_type: str, owner_id: str):
    """Parse and validate a property YAML document; return errors or the parsed spec."""
    if owner_type not in _VALID_OWNER_TYPES:
        return jsonify({"error": f"Invalid owner_type: {owner_type}"}), 400

    content_type = request.content_type or ""
    if "yaml" in content_type or "text/plain" in content_type:
        raw = request.get_data(as_text=True)
    else:
        body = request.get_json(silent=True) or {}
        raw = body.get("yaml", "")

    try:
        owner_type_doc, owner_id_doc, prop_specs = _parse_and_validate(raw)
    except _ValidationError as exc:
        return jsonify({"valid": False, "errors": exc.errors}), 422

    # Warn if the scope in the document doesn't match the URL
    warnings: list[str] = []
    if owner_type_doc != owner_type or owner_id_doc != owner_id:
        warnings.append(
            f"Document scope ({owner_type_doc}/{owner_id_doc}) "
            f"does not match URL ({owner_type}/{owner_id}); URL takes precedence on apply"
        )

    return jsonify(
        {
            "valid": True,
            "warnings": warnings,
            "property_count": len(prop_specs),
            "properties": prop_specs,
        }
    )


@prop_yaml_bp.post("/prop-yaml/<owner_type>/<owner_id>/apply")
def apply_prop_yaml(owner_type: str, owner_id: str):
    """Parse a property YAML document and upsert all properties to the database.

    Existing properties not present in the document are left untouched.
    Pass ``replace: true`` in the JSON body (or as ?replace=true) to delete
    any properties on this scope that are *not* in the document.
    """
    if owner_type not in _VALID_OWNER_TYPES:
        return jsonify({"error": f"Invalid owner_type: {owner_type}"}), 400

    content_type = request.content_type or ""
    replace = request.args.get("replace", "false").lower() == "true"

    if "yaml" in content_type or "text/plain" in content_type:
        raw = request.get_data(as_text=True)
    else:
        body = request.get_json(silent=True) or {}
        raw = body.get("yaml", "")
        replace = replace or bool(body.get("replace", False))

    try:
        _, _, prop_specs = _parse_and_validate(raw)
    except _ValidationError as exc:
        return jsonify({"error": "Validation failed", "errors": exc.errors}), 422

    from app.models.property import Property
    from app.services.property_service import set_property

    if replace:
        incoming_names = {s["name"] for s in prop_specs}
        Property.query.filter_by(owner_type=owner_type, owner_id=owner_id).filter(
            Property.name.notin_(incoming_names)
        ).delete(synchronize_session="fetch")

    created = 0
    updated = 0
    for spec in prop_specs:
        existing = Property.query.filter_by(
            owner_type=owner_type, owner_id=owner_id, name=spec["name"]
        ).first()
        set_property(
            owner_type,
            owner_id,
            spec["name"],
            spec["value"],
            value_type=spec["value_type"],
            description=spec["description"],
            is_required=spec["is_required"],
        )
        if existing:
            updated += 1
        else:
            created += 1

    db.session.commit()

    return jsonify(
        {
            "applied": True,
            "created": created,
            "updated": updated,
            "scope": {"type": owner_type, "id": owner_id},
        }
    )
