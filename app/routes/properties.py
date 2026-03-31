"""Property & ParameterValue API endpoints.

Design-time properties (CRUD on definition objects):
  GET    /api/v1/properties/{owner_type}/{owner_id}
  POST   /api/v1/properties/{owner_type}/{owner_id}
  PUT    /api/v1/properties/{owner_type}/{owner_id}/{name}
  DELETE /api/v1/properties/{owner_type}/{owner_id}/{name}

Runtime parameter values (overrides on execution objects):
  GET    /api/v1/parameter-values/{run_type}/{run_id}
  POST   /api/v1/parameter-values/{run_type}/{run_id}
  DELETE /api/v1/parameter-values/{run_type}/{run_id}/{name}

Resolved view (full hierarchy for a pipeline run + optional stage/task context):
  GET    /api/v1/properties/resolve/pipeline-run/{pipeline_run_id}
  GET    /api/v1/properties/resolve/pipeline-run/{pipeline_run_id}/stage-run/{stage_run_id}
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

properties_bp = Blueprint("properties", __name__, url_prefix="/api/v1")

_VALID_OWNER_TYPES = {"product", "pipeline", "stage", "task"}
_VALID_RUN_TYPES = {"pipeline_run", "stage_run", "task_run"}


# ── Design-time property endpoints ───────────────────────────────────────────


@properties_bp.get("/properties/<owner_type>/<owner_id>")
def list_properties(owner_type: str, owner_id: str):
    if owner_type not in _VALID_OWNER_TYPES:
        return jsonify({"error": f"Invalid owner_type: {owner_type}"}), 400
    from app.services.property_service import list_properties as _list

    return jsonify([p.to_dict() for p in _list(owner_type, owner_id)])


@properties_bp.post("/properties/<owner_type>/<owner_id>")
def create_property(owner_type: str, owner_id: str):
    if owner_type not in _VALID_OWNER_TYPES:
        return jsonify({"error": f"Invalid owner_type: {owner_type}"}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    from app.services.property_service import set_property

    prop = set_property(
        owner_type,
        owner_id,
        name,
        data.get("value"),
        value_type=data.get("value_type", "string"),
        description=data.get("description"),
        is_required=bool(data.get("is_required", False)),
    )
    return jsonify(prop.to_dict()), 201


@properties_bp.put("/properties/<owner_type>/<owner_id>/<path:name>")
def update_property(owner_type: str, owner_id: str, name: str):
    if owner_type not in _VALID_OWNER_TYPES:
        return jsonify({"error": f"Invalid owner_type: {owner_type}"}), 400
    data = request.get_json(silent=True) or {}
    from app.services.property_service import set_property

    prop = set_property(
        owner_type,
        owner_id,
        name,
        data.get("value"),
        value_type=data.get("value_type", "string"),
        description=data.get("description"),
        is_required=bool(data.get("is_required", False)),
    )
    return jsonify(prop.to_dict())


@properties_bp.delete("/properties/<owner_type>/<owner_id>/<path:name>")
def delete_property(owner_type: str, owner_id: str, name: str):
    if owner_type not in _VALID_OWNER_TYPES:
        return jsonify({"error": f"Invalid owner_type: {owner_type}"}), 400
    from app.services.property_service import delete_property as _del

    _del(owner_type, owner_id, name)
    return "", 204


# ── Runtime parameter value endpoints ────────────────────────────────────────


@properties_bp.get("/parameter-values/<run_type>/<run_id>")
def list_param_values(run_type: str, run_id: str):
    if run_type not in _VALID_RUN_TYPES:
        return jsonify({"error": f"Invalid run_type: {run_type}"}), 400
    from app.services.property_service import list_parameter_values

    return jsonify([pv.to_dict() for pv in list_parameter_values(run_type, run_id)])


@properties_bp.post("/parameter-values/<run_type>/<run_id>")
def set_param_value(run_type: str, run_id: str):
    if run_type not in _VALID_RUN_TYPES:
        return jsonify({"error": f"Invalid run_type: {run_type}"}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    from app.services.property_service import set_parameter_value

    pv = set_parameter_value(run_type, run_id, name, data.get("value"))
    return jsonify(pv.to_dict()), 201


@properties_bp.delete("/parameter-values/<run_type>/<run_id>/<path:name>")
def delete_param_value(run_type: str, run_id: str, name: str):
    if run_type not in _VALID_RUN_TYPES:
        return jsonify({"error": f"Invalid run_type: {run_type}"}), 400
    from app.services.property_service import delete_parameter_value

    delete_parameter_value(run_type, run_id, name)
    return "", 204


# ── Resolved view ─────────────────────────────────────────────────────────────


@properties_bp.get("/properties/resolve/pipeline-run/<pipeline_run_id>")
def resolve_for_pipeline_run(pipeline_run_id: str):
    """Return all resolved properties for a pipeline run (pipeline + product scope)."""
    from app.models.run import PipelineRun
    from app.services.property_service import resolve_all

    run = PipelineRun.query.get_or_404(pipeline_run_id)
    pipeline = run.pipeline
    product = pipeline.product if pipeline else None
    resolved = resolve_all(pipeline_run=run, pipeline=pipeline, product=product)
    return jsonify({"pipeline_run_id": pipeline_run_id, "properties": resolved})


@properties_bp.get("/properties/resolve/pipeline-run/<pipeline_run_id>/stage-run/<stage_run_id>")
def resolve_for_stage_run(pipeline_run_id: str, stage_run_id: str):
    """Return all resolved properties in stage context (task+stage+pipeline+product)."""
    from app.models.run import PipelineRun, StageRun
    from app.services.property_service import resolve_all

    run = PipelineRun.query.get_or_404(pipeline_run_id)
    sr = StageRun.query.get_or_404(stage_run_id)
    pipeline = run.pipeline
    stage = sr.stage
    product = pipeline.product if pipeline else None
    resolved = resolve_all(
        pipeline_run=run,
        stage_run=sr,
        pipeline=pipeline,
        stage=stage,
        product=product,
    )
    return jsonify(
        {
            "pipeline_run_id": pipeline_run_id,
            "stage_run_id": stage_run_id,
            "properties": resolved,
        }
    )
