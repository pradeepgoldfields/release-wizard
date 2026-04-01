"""Pipeline Templates API.

GET    /api/v1/pipeline-templates              — list all templates
POST   /api/v1/pipeline-templates              — create template
GET    /api/v1/pipeline-templates/<id>         — get single template (with stages)
PUT    /api/v1/pipeline-templates/<id>         — update template
DELETE /api/v1/pipeline-templates/<id>         — delete template
POST   /api/v1/pipeline-templates/from-pipeline/<pipeline_id>  — create template from existing pipeline
POST   /api/v1/pipeline-templates/<id>/create-pipeline         — create a new pipeline from this template
"""

from __future__ import annotations

import json

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.pipeline_template import PipelineTemplate
from app.services.id_service import resource_id

templates_bp = Blueprint("templates", __name__, url_prefix="/api/v1/pipeline-templates")


@templates_bp.get("")
def list_templates():
    q = request.args.get("q", "").strip().lower()
    kind = request.args.get("kind", "").strip()
    category = request.args.get("category", "").strip()

    rows = PipelineTemplate.query.order_by(PipelineTemplate.name).all()
    result = []
    for t in rows:
        d = t.to_dict(include_definition=False)
        if (
            q
            and q not in t.name.lower()
            and q not in (t.description or "").lower()
            and q not in (t.tags or "").lower()
        ):
            continue
        if kind and t.kind != kind:
            continue
        if category and t.category != category:
            continue
        result.append(d)
    return jsonify(result)


@templates_bp.post("")
def create_template():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    from app.routes.auth import _current_user

    user = _current_user()

    t = PipelineTemplate(
        id=resource_id("tmpl"),
        name=name,
        description=data.get("description"),
        kind=data.get("kind", "ci"),
        category=data.get("category"),
        tags=", ".join(data.get("tags") or [])
        if isinstance(data.get("tags"), list)
        else (data.get("tags") or ""),
        definition_json=json.dumps(data.get("stages") or []),
        created_by=user.username if user else None,
    )
    db.session.add(t)
    db.session.commit()
    return jsonify(t.to_dict()), 201


@templates_bp.get("/<tmpl_id>")
def get_template(tmpl_id: str):
    t = db.get_or_404(PipelineTemplate, tmpl_id)
    return jsonify(t.to_dict())


@templates_bp.put("/<tmpl_id>")
def update_template(tmpl_id: str):
    t = db.get_or_404(PipelineTemplate, tmpl_id)
    data = request.get_json(silent=True) or {}
    for field in ("name", "description", "kind", "category"):
        if field in data:
            setattr(t, field, data[field])
    if "tags" in data:
        tags = data["tags"]
        t.tags = ", ".join(tags) if isinstance(tags, list) else (tags or "")
    if "stages" in data:
        t.definition_json = json.dumps(data["stages"] or [])
    db.session.commit()
    return jsonify(t.to_dict())


@templates_bp.delete("/<tmpl_id>")
def delete_template(tmpl_id: str):
    t = db.get_or_404(PipelineTemplate, tmpl_id)
    db.session.delete(t)
    db.session.commit()
    return "", 204


@templates_bp.post("/from-pipeline/<pipeline_id>")
def template_from_pipeline(pipeline_id: str):
    """Save an existing pipeline as a reusable template."""
    from sqlalchemy.orm import joinedload

    from app.models.pipeline import Pipeline, Stage

    pipeline = (
        Pipeline.query.options(joinedload(Pipeline.stages).joinedload(Stage.tasks))
        .filter_by(id=pipeline_id)
        .first_or_404()
    )

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or f"{pipeline.name} (Template)").strip()

    stages_def = []
    for s in sorted(pipeline.stages, key=lambda x: x.order):
        tasks_def = []
        for tk in sorted(s.tasks, key=lambda x: x.order):
            tasks_def.append(
                {
                    "name": tk.name,
                    "description": tk.description,
                    "order": tk.order,
                    "run_language": tk.run_language,
                    "run_code": tk.run_code,
                    "execution_mode": tk.execution_mode,
                    "on_error": tk.on_error,
                    "timeout": tk.timeout,
                    "is_required": tk.is_required,
                    "task_type": tk.task_type or "",
                }
            )
        stages_def.append(
            {
                "name": s.name,
                "order": s.order,
                "container_image": s.container_image,
                "run_language": s.run_language,
                "run_code": s.run_code,
                "run_file": s.run_file,
                "tasks": tasks_def,
            }
        )

    from app.routes.auth import _current_user

    user = _current_user()

    t = PipelineTemplate(
        id=resource_id("tmpl"),
        name=name,
        description=data.get("description") or f"Created from pipeline '{pipeline.name}'",
        kind=pipeline.kind or "ci",
        category=data.get("category"),
        tags=data.get("tags") or "",
        definition_json=json.dumps(stages_def),
        created_by=user.username if user else None,
    )
    db.session.add(t)
    db.session.commit()
    return jsonify(t.to_dict()), 201


@templates_bp.post("/<tmpl_id>/create-pipeline")
def create_pipeline_from_template(tmpl_id: str):
    """Create a new pipeline under a product, copying stages from a template."""
    t = db.get_or_404(PipelineTemplate, tmpl_id)
    data = request.get_json(silent=True) or {}

    product_id = data.get("product_id")
    name = (data.get("name") or t.name).strip()
    if not product_id:
        return jsonify({"error": "product_id is required"}), 400
    if not name:
        return jsonify({"error": "name is required"}), 400

    try:
        stages = json.loads(t.definition_json or "[]")
    except Exception:
        stages = []

    from app.services.pipeline_service import create_pipeline

    pipeline = create_pipeline(
        product_id=product_id,
        name=name,
        kind=data.get("kind") or t.kind or "ci",
        git_repo=data.get("git_repo"),
        git_branch=data.get("git_branch", "main"),
        application_id=data.get("application_id"),
        stages=_new_stage_ids(stages),
    )
    return jsonify(pipeline.to_dict(include_stages=True)), 201


@templates_bp.get("/<tmpl_id>/export")
def export_template_yaml(tmpl_id: str):
    """Export a template definition as YAML (mirrors the pipeline export format)."""
    import yaml  # noqa: PLC0415
    from flask import Response  # noqa: PLC0415

    t = db.get_or_404(PipelineTemplate, tmpl_id)
    try:
        stages_raw = json.loads(t.definition_json or "[]")
    except Exception:
        stages_raw = []

    data = {
        "apiVersion": "conduit/v1",
        "kind": "PipelineTemplate",
        "metadata": {
            "name": t.name,
            "description": t.description or "",
            "kind": t.kind or "ci",
            "category": t.category or "",
            "tags": [s.strip() for s in (t.tags or "").split(",") if s.strip()],
        },
        "spec": {
            "stages": [
                {
                    "name": s.get("name", ""),
                    "order": s.get("order", i + 1),
                    "container_image": s.get("container_image", ""),
                    "run_language": s.get("run_language", "bash"),
                    "tasks": [
                        {
                            "name": tk.get("name", ""),
                            "order": tk.get("order", j + 1),
                            "run_language": tk.get("run_language", "bash"),
                            "execution_mode": tk.get("execution_mode", "sequential"),
                            "on_error": tk.get("on_error", "fail"),
                            "timeout": tk.get("timeout", 300),
                            "is_required": tk.get("is_required", True),
                            "task_type": tk.get("task_type", ""),
                            "run_code": tk.get("run_code", ""),
                        }
                        for j, tk in enumerate(s.get("tasks", []))
                    ],
                }
                for i, s in enumerate(stages_raw)
            ]
        },
    }
    return Response(
        yaml.dump(data, allow_unicode=True, sort_keys=False),
        mimetype="text/yaml",
    )


@templates_bp.post("/<tmpl_id>/import")
def import_template_yaml(tmpl_id: str):
    """Import YAML into a template, replacing its stage definition."""
    import yaml

    t = db.get_or_404(PipelineTemplate, tmpl_id)
    raw = request.get_data(as_text=True)
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return jsonify({"error": f"Invalid YAML: {exc}"}), 400

    # Accept both bare spec and wrapped apiVersion document
    spec = doc.get("spec", doc) if isinstance(doc, dict) else {}
    meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}

    stages_raw = spec.get("stages", [])
    if not isinstance(stages_raw, list):
        return jsonify({"error": "'stages' must be a list"}), 400

    # Update metadata fields if present in YAML
    if meta.get("name"):
        t.name = meta["name"]
    if "description" in meta:
        t.description = meta["description"]
    if "kind" in meta:
        t.kind = meta["kind"]
    if "category" in meta:
        t.category = meta["category"]
    if "tags" in meta:
        tags = meta["tags"]
        t.tags = ", ".join(tags) if isinstance(tags, list) else (tags or "")

    t.definition_json = json.dumps(stages_raw)
    db.session.commit()
    return jsonify(t.to_dict())


def _new_stage_ids(stages: list[dict]) -> list[dict]:
    """Strip existing IDs from template stages/tasks so fresh ones are generated."""
    result = []
    for s in stages:
        new_s = {k: v for k, v in s.items() if k != "id"}
        new_s["tasks"] = [{k: v for k, v in tk.items() if k != "id"} for tk in s.get("tasks", [])]
        result.append(new_s)
    return result
