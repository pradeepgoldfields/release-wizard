"""HTTP handlers for Pipeline and Stage resources.

All business logic is delegated to :mod:`app.services.pipeline_service`.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.pipeline import Pipeline, Stage
from app.models.product import Product
from app.models.task import Task
from app.services.id_service import resource_id
from app.services.pipeline_service import create_pipeline, update_compliance_score
from app.utils import paginate

pipelines_bp = Blueprint(
    "pipelines", __name__, url_prefix="/api/v1/products/<product_id>/pipelines"
)


@pipelines_bp.get("")
def list_pipelines(product_id: str):
    """Return pipelines for a product.

    Query params: ``limit`` (default 50, max 200), ``offset`` (default 0).
    """
    db.get_or_404(Product, product_id)
    query = Pipeline.query.filter_by(product_id=product_id).order_by(Pipeline.name)
    items, meta = paginate(query)
    return jsonify({"items": [p.to_dict() for p in items], "meta": meta})


@pipelines_bp.post("")
def create_pipeline_endpoint(product_id: str):
    """Create a new pipeline under a product.

    Required body: ``name``
    Optional: ``kind``, ``git_repo``, ``git_branch``, ``stages``
    """
    db.get_or_404(Product, product_id)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    pipeline = create_pipeline(
        product_id=product_id,
        name=name,
        kind=data.get("kind", "ci"),
        git_repo=data.get("git_repo"),
        git_branch=data.get("git_branch", "main"),
        stages=data.get("stages"),
        application_id=data.get("application_id"),
    )
    return jsonify(pipeline.to_dict(include_stages=True)), 201


@pipelines_bp.get("/<pipeline_id>")
def get_pipeline(product_id: str, pipeline_id: str):
    """Return a single pipeline with its stages."""
    pipeline = Pipeline.query.filter_by(id=pipeline_id, product_id=product_id).first_or_404()
    return jsonify(pipeline.to_dict(include_stages=True))


@pipelines_bp.put("/<pipeline_id>")
def update_pipeline(product_id: str, pipeline_id: str):
    """Update mutable pipeline fields."""
    pipeline = Pipeline.query.filter_by(id=pipeline_id, product_id=product_id).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ("name", "kind", "git_repo", "git_branch", "definition_sha", "application_id"):
        if field in data:
            setattr(pipeline, field, data[field])
    db.session.commit()
    return jsonify(pipeline.to_dict(include_stages=True))


@pipelines_bp.delete("/<pipeline_id>")
def delete_pipeline(product_id: str, pipeline_id: str):
    """Delete a pipeline and all its stages and runs."""
    pipeline = Pipeline.query.filter_by(id=pipeline_id, product_id=product_id).first_or_404()
    db.session.delete(pipeline)
    db.session.commit()
    return "", 204


@pipelines_bp.post("/<pipeline_id>/copy")
def copy_pipeline(product_id: str, pipeline_id: str):
    """Duplicate a pipeline (with all its stages and tasks) into the same or another product."""
    from sqlalchemy.orm import joinedload

    src = (
        Pipeline.query.options(joinedload(Pipeline.stages).joinedload(Stage.tasks))
        .filter_by(id=pipeline_id, product_id=product_id)
        .first_or_404()
    )
    data = request.get_json(silent=True) or {}
    new_name = (data.get("name") or f"{src.name} (Copy)").strip()
    dest_product_id = data.get("product_id") or product_id

    stages_def = []
    for s in sorted(src.stages, key=lambda x: x.order):
        stages_def.append(
            {
                "name": s.name,
                "order": s.order,
                "container_image": s.container_image,
                "run_language": s.run_language,
                "run_code": s.run_code,
                "run_file": s.run_file,
                "tasks": [
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
                    for tk in sorted(s.tasks, key=lambda x: x.order)
                ],
            }
        )

    new_pipeline = create_pipeline(
        product_id=dest_product_id,
        name=new_name,
        kind=src.kind or "ci",
        git_repo=data.get("git_repo") or src.git_repo,
        git_branch=data.get("git_branch") or src.git_branch or "main",
        application_id=data.get("application_id") or src.application_id,
        stages=stages_def,
    )
    return jsonify(new_pipeline.to_dict(include_stages=True)), 201


@pipelines_bp.post("/<pipeline_id>/compliance")
def update_pipeline_compliance(product_id: str, pipeline_id: str):
    """Recalculate and persist the weighted compliance score for a pipeline.

    Required body: ``mandatory_pct``, ``best_practice_pct``, ``runtime_pct``, ``metadata_pct``
    All values are percentages (0–100).
    """
    data = request.get_json(silent=True) or {}
    pipeline = update_compliance_score(
        product_id=product_id,
        pipeline_id=pipeline_id,
        mandatory_pct=float(data.get("mandatory_pct", 0)),
        best_practice_pct=float(data.get("best_practice_pct", 0)),
        runtime_pct=float(data.get("runtime_pct", 0)),
        metadata_pct=float(data.get("metadata_pct", 0)),
    )
    return jsonify(
        {
            "compliance_score": pipeline.compliance_score,
            "compliance_rating": pipeline.compliance_rating,
        }
    )


# ── Stages ───────────────────────────────────────────────────────────────────


@pipelines_bp.post("/<pipeline_id>/stages")
def create_stage(product_id: str, pipeline_id: str):
    """Create a new stage within a pipeline.

    Required body: ``name``
    Optional: ``order``, ``run_language``, ``container_image``, ``is_protected``
    """
    pipeline = Pipeline.query.filter_by(id=pipeline_id, product_id=product_id).first_or_404()
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    stage = Stage(
        id=resource_id("stg"),
        pipeline_id=pipeline.id,
        name=name,
        order=int(data.get("order", len(pipeline.stages))),
        run_language=data.get("run_language", "bash"),
        container_image=data.get("container_image"),
        is_protected=bool(data.get("is_protected", False)),
        accent_color=data.get("accent_color") or None,
        execution_mode=data.get("execution_mode", "sequential"),
    )
    db.session.add(stage)
    db.session.commit()
    return jsonify(stage.to_dict(include_tasks=True)), 201


@pipelines_bp.put("/<pipeline_id>/stages/<stage_id>")
def update_stage(product_id: str, pipeline_id: str, stage_id: str):
    """Update mutable stage fields."""
    Pipeline.query.filter_by(id=pipeline_id, product_id=product_id).first_or_404()
    stage = Stage.query.filter_by(id=stage_id, pipeline_id=pipeline_id).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ("name", "run_language", "container_image", "accent_color"):
        if field in data:
            setattr(stage, field, data[field] or None)
    if "order" in data:
        stage.order = int(data["order"])
    if "is_protected" in data:
        stage.is_protected = bool(data["is_protected"])
    if "execution_mode" in data:
        stage.execution_mode = (
            data["execution_mode"]
            if data["execution_mode"] in ("sequential", "parallel")
            else "sequential"
        )
    db.session.commit()
    return jsonify(stage.to_dict(include_tasks=True))


@pipelines_bp.delete("/<pipeline_id>/stages/<stage_id>")
def delete_stage(product_id: str, pipeline_id: str, stage_id: str):
    """Delete a stage and all its tasks."""
    Pipeline.query.filter_by(id=pipeline_id, product_id=product_id).first_or_404()
    stage = Stage.query.filter_by(id=stage_id, pipeline_id=pipeline_id).first_or_404()
    db.session.delete(stage)
    db.session.commit()
    return "", 204


# ── Stage Tasks ──────────────────────────────────────────────────────────────


@pipelines_bp.get("/<pipeline_id>/stages/<stage_id>/tasks")
def list_tasks(product_id: str, pipeline_id: str, stage_id: str):
    """Return all tasks for a stage, ordered by sequence."""
    stage = Stage.query.filter_by(id=stage_id, pipeline_id=pipeline_id).first_or_404()
    return jsonify([t.to_dict() for t in stage.tasks])


@pipelines_bp.post("/<pipeline_id>/stages/<stage_id>/tasks")
def create_task(product_id: str, pipeline_id: str, stage_id: str):
    """Create a new task within a stage.

    Required body: ``name``
    Optional: ``description``, ``order``, ``run_language``, ``run_code``,
              ``execution_mode``, ``on_error``, ``timeout``, ``is_required``
    """
    Stage.query.filter_by(id=stage_id, pipeline_id=pipeline_id).first_or_404()
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    task = Task(
        id=resource_id("task"),
        stage_id=stage_id,
        name=name,
        description=data.get("description"),
        order=int(data.get("order", 0)),
        run_language=data.get("run_language", "bash"),
        run_code=data.get("run_code", ""),
        execution_mode=data.get("execution_mode", "sequential"),
        on_error=data.get("on_error", "fail"),
        timeout=int(data.get("timeout", 300)),
        is_required=bool(data.get("is_required", True)),
        task_type=data.get("task_type") or None,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@pipelines_bp.get("/<pipeline_id>/stages/<stage_id>/tasks/<task_id>")
def get_task(product_id: str, pipeline_id: str, stage_id: str, task_id: str):
    """Return a single task."""
    Stage.query.filter_by(id=stage_id, pipeline_id=pipeline_id).first_or_404()
    task = Task.query.filter_by(id=task_id, stage_id=stage_id).first_or_404()
    return jsonify(task.to_dict())


@pipelines_bp.put("/<pipeline_id>/stages/<stage_id>/tasks/<task_id>")
def update_task(product_id: str, pipeline_id: str, stage_id: str, task_id: str):
    """Update a task's fields."""
    Stage.query.filter_by(id=stage_id, pipeline_id=pipeline_id).first_or_404()
    task = Task.query.filter_by(id=task_id, stage_id=stage_id).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ("name", "description", "run_language", "run_code", "execution_mode", "on_error"):
        if field in data:
            setattr(task, field, data[field])
    if "order" in data:
        task.order = int(data["order"])
    if "timeout" in data:
        task.timeout = int(data["timeout"])
    if "is_required" in data:
        task.is_required = bool(data["is_required"])
    if "task_type" in data:
        task.task_type = data["task_type"] or None
    db.session.commit()
    return jsonify(task.to_dict())


@pipelines_bp.delete("/<pipeline_id>/stages/<stage_id>/tasks/<task_id>")
def delete_task(product_id: str, pipeline_id: str, stage_id: str, task_id: str):
    """Delete a task from a stage."""
    Stage.query.filter_by(id=stage_id, pipeline_id=pipeline_id).first_or_404()
    task = Task.query.filter_by(id=task_id, stage_id=stage_id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    return "", 204
