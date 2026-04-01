"""YAML export / import for all major resources."""

from __future__ import annotations

import yaml
from flask import Blueprint, Response, jsonify, request

from app.extensions import db
from app.models.environment import Environment
from app.models.pipeline import Pipeline, Stage
from app.models.product import Product
from app.models.release import Release
from app.models.task import AgentPool, Task
from app.services.id_service import resource_id

yaml_bp = Blueprint("yaml_io", __name__, url_prefix="/api/v1")


def _yaml_response(data: dict) -> Response:
    return Response(yaml.dump(data, allow_unicode=True, sort_keys=False), mimetype="text/yaml")


# ── Product export ──────────────────────────────────────────────────────────


@yaml_bp.get("/products/<product_id>/export")
def export_product(product_id: str):
    """Export a product with all its relationships as YAML."""
    product = db.get_or_404(Product, product_id)
    releases = Release.query.filter_by(product_id=product_id).all()
    pipelines = Pipeline.query.filter_by(product_id=product_id).all()

    data = {
        "apiVersion": "conduit/v1",
        "kind": "Product",
        "metadata": {"name": product.name},
        "spec": {
            "description": product.description,
            "environments": [e.name for e in product.environments],
            "releases": [
                {
                    "name": r.name,
                    "version": r.version,
                    "description": r.description,
                    "pipelines": [p.name for p in r.pipelines],
                }
                for r in releases
            ],
            "pipelines": [
                {
                    "name": pl.name,
                    "kind": pl.kind,
                    "git_repo": pl.git_repo,
                    "git_branch": pl.git_branch,
                    "stages": [
                        {
                            "name": s.name,
                            "order": s.order,
                            "tasks": [
                                {
                                    "name": t.name,
                                    "run_language": t.run_language,
                                    "execution_mode": t.execution_mode,
                                    "on_error": t.on_error,
                                    "timeout": t.timeout,
                                    "run_code": t.run_code,
                                }
                                for t in s.tasks
                            ],
                        }
                        for s in pl.stages
                    ],
                }
                for pl in pipelines
            ],
        },
    }
    return _yaml_response(data)


# ── Environment export ──────────────────────────────────────────────────────


@yaml_bp.get("/environments/<env_id>/export")
def export_environment(env_id: str):
    env = db.get_or_404(Environment, env_id)
    data = {
        "apiVersion": "conduit/v1",
        "kind": "Environment",
        "metadata": {"name": env.name},
        "spec": {
            "env_type": env.env_type,
            "order": env.order,
            "description": env.description,
        },
    }
    return _yaml_response(data)


@yaml_bp.get("/environments/export")
def export_all_environments():
    envs = Environment.query.order_by(Environment.order).all()
    data = {
        "apiVersion": "conduit/v1",
        "kind": "EnvironmentList",
        "items": [
            {"name": e.name, "env_type": e.env_type, "order": e.order, "description": e.description}
            for e in envs
        ],
    }
    return _yaml_response(data)


# ── Pipeline export ─────────────────────────────────────────────────────────


@yaml_bp.get("/products/<product_id>/pipelines/<pipeline_id>/export")
def export_pipeline(product_id: str, pipeline_id: str):
    pipeline = Pipeline.query.filter_by(id=pipeline_id, product_id=product_id).first_or_404()
    data = {
        "apiVersion": "conduit/v1",
        "kind": "Pipeline",
        "metadata": {"name": pipeline.name},
        "spec": {
            "kind": pipeline.kind,
            "git_repo": pipeline.git_repo,
            "git_branch": pipeline.git_branch,
            "stages": [
                {
                    "name": s.name,
                    "order": s.order,
                    "tasks": [
                        {
                            "name": t.name,
                            "run_language": t.run_language,
                            "execution_mode": t.execution_mode,
                            "on_error": t.on_error,
                            "timeout": t.timeout,
                            "run_code": t.run_code,
                        }
                        for t in s.tasks
                    ],
                }
                for s in pipeline.stages
            ],
        },
    }
    return _yaml_response(data)


# ── Release export ──────────────────────────────────────────────────────────


@yaml_bp.get("/products/<product_id>/releases/<release_id>/export")
def export_release(product_id: str, release_id: str):
    release = Release.query.filter_by(id=release_id, product_id=product_id).first_or_404()
    data = {
        "apiVersion": "conduit/v1",
        "kind": "Release",
        "metadata": {"name": release.name},
        "spec": {
            "version": release.version,
            "description": release.description,
            "pipelines": [p.name for p in release.pipelines],
        },
    }
    return _yaml_response(data)


# ── Agent Pool export ───────────────────────────────────────────────────────


@yaml_bp.get("/agent-pools/export")
def export_agent_pools():
    pools = AgentPool.query.filter_by(pool_type="custom").all()
    data = {
        "apiVersion": "conduit/v1",
        "kind": "AgentPoolList",
        "items": [
            {
                "name": p.name,
                "description": p.description,
                "cpu_limit": p.cpu_limit,
                "memory_limit": p.memory_limit,
                "max_agents": p.max_agents,
            }
            for p in pools
        ],
    }
    return _yaml_response(data)


# ── Import endpoints ────────────────────────────────────────────────────────


def _parse_yaml_body() -> dict:
    """Parse YAML or JSON from request body."""
    ct = request.content_type or ""
    if "yaml" in ct or "yml" in ct:
        return yaml.safe_load(request.data.decode("utf-8")) or {}
    return request.get_json(silent=True) or {}


@yaml_bp.post("/environments/import")
def import_environments():
    """Import environments from YAML. Creates new ones; skips existing names."""
    data = _parse_yaml_body()
    items = data.get("items", [data.get("spec", {})] if data.get("kind") == "Environment" else [])
    created = []
    for item in items:
        name = (item.get("name") or item.get("metadata", {}).get("name") or "").strip()
        if not name or Environment.query.filter_by(name=name).first():
            continue
        env = Environment(
            id=resource_id("env"),
            name=name,
            env_type=item.get("env_type", "custom"),
            order=int(item.get("order", 0)),
            description=item.get("description"),
        )
        db.session.add(env)
        created.append(name)
    db.session.commit()
    return jsonify({"created": created, "count": len(created)}), 201


@yaml_bp.post("/products/<product_id>/pipelines/<pipeline_id>/import")
def import_pipeline(product_id: str, pipeline_id: str):
    """Replace a pipeline's stages + tasks from YAML (upsert by name).

    Accepts the same format produced by the export endpoint.
    Existing stages/tasks not present in the YAML are deleted.
    """
    pipeline = Pipeline.query.filter_by(id=pipeline_id, product_id=product_id).first_or_404()
    data = _parse_yaml_body()
    spec = data.get("spec", data)  # accept both wrapped and bare formats

    # Update top-level pipeline fields if present
    if "kind" in spec:
        pipeline.kind = spec["kind"]
    if "git_repo" in spec:
        pipeline.git_repo = spec["git_repo"] or None
    if "git_branch" in spec:
        pipeline.git_branch = spec["git_branch"] or None

    stage_specs = spec.get("stages", [])
    kept_stage_ids = []

    for s_spec in stage_specs:
        s_name = (s_spec.get("name") or "").strip()
        if not s_name:
            continue
        stage = Stage.query.filter_by(pipeline_id=pipeline_id, name=s_name).first()
        if not stage:
            stage = Stage(id=resource_id("stg"), pipeline_id=pipeline_id, name=s_name)
            db.session.add(stage)
        stage.order = int(s_spec.get("order", stage.order or 0))
        stage.run_language = s_spec.get("run_language", stage.run_language or "bash")
        stage.execution_mode = s_spec.get("execution_mode", stage.execution_mode or "sequential")
        db.session.flush()
        kept_stage_ids.append(stage.id)

        task_specs = s_spec.get("tasks", [])
        kept_task_ids = []
        for t_order, t_spec in enumerate(task_specs, start=1):
            t_name = (t_spec.get("name") or "").strip()
            if not t_name:
                continue
            task = Task.query.filter_by(stage_id=stage.id, name=t_name).first()
            if not task:
                task = Task(id=resource_id("task"), stage_id=stage.id, name=t_name)
                db.session.add(task)
            task.order = t_spec.get("order", t_order)
            task.run_language = t_spec.get("run_language", task.run_language or "bash")
            task.run_code = t_spec.get("run_code", task.run_code)
            task.on_error = t_spec.get("on_error", task.on_error or "fail")
            task.timeout = int(t_spec.get("timeout", task.timeout or 300))
            task.execution_mode = t_spec.get("execution_mode", task.execution_mode or "sequential")
            db.session.flush()
            kept_task_ids.append(task.id)

        # Remove tasks not in the YAML
        Task.query.filter(
            Task.stage_id == stage.id,
            Task.id.notin_(kept_task_ids),
        ).delete(synchronize_session=False)

    # Remove stages not in the YAML
    Stage.query.filter(
        Stage.pipeline_id == pipeline_id,
        Stage.id.notin_(kept_stage_ids),
    ).delete(synchronize_session=False)

    db.session.commit()
    updated = Pipeline.query.get(pipeline_id)
    return jsonify(updated.to_dict(include_stages=True))


@yaml_bp.post("/agent-pools/import")
def import_agent_pools():
    """Import custom agent pools from YAML."""
    data = _parse_yaml_body()
    items = data.get("items", [])
    created = []
    for item in items:
        name = (item.get("name") or "").strip()
        if not name or AgentPool.query.filter_by(name=name).first():
            continue
        pool = AgentPool(
            id=resource_id("pool"),
            name=name,
            description=item.get("description"),
            pool_type="custom",
            cpu_limit=item.get("cpu_limit", "500m"),
            memory_limit=item.get("memory_limit", "256Mi"),
            max_agents=int(item.get("max_agents", 5)),
        )
        db.session.add(pool)
        created.append(name)
    db.session.commit()
    return jsonify({"created": created, "count": len(created)}), 201


# ── Git sync endpoints ──────────────────────────────────────────────────────


@yaml_bp.post("/products/<product_id>/pipelines/<pipeline_id>/git/pull")
def git_pull_pipeline(product_id: str, pipeline_id: str):
    """Pull the pipeline definition from its configured git_repo and apply it.

    Clones the repo (shallow), reads ``conduit/<name>.yaml``,
    and upserts stages/tasks exactly like the import endpoint.
    Returns the updated pipeline dict and the commit SHA.
    """
    from app.services.git_service import sync_pipeline_from_git  # noqa: PLC0415

    pipeline = Pipeline.query.filter_by(id=pipeline_id, product_id=product_id).first_or_404()
    try:
        result = sync_pipeline_from_git(pipeline)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    spec = result["spec"]
    sha = result["sha"]

    spec_inner = spec.get("spec", spec)
    if "kind" in spec_inner:
        pipeline.kind = spec_inner["kind"]
    if "git_repo" in spec_inner:
        pipeline.git_repo = spec_inner["git_repo"] or None
    if "git_branch" in spec_inner:
        pipeline.git_branch = spec_inner["git_branch"] or None

    stage_specs = spec_inner.get("stages", [])
    kept_stage_ids = []
    for s_spec in stage_specs:
        s_name = (s_spec.get("name") or "").strip()
        if not s_name:
            continue
        stage = Stage.query.filter_by(pipeline_id=pipeline_id, name=s_name).first()
        if not stage:
            stage = Stage(id=resource_id("stg"), pipeline_id=pipeline_id, name=s_name)
            db.session.add(stage)
        stage.order = int(s_spec.get("order", stage.order or 0))
        stage.run_language = s_spec.get("run_language", stage.run_language or "bash")
        stage.execution_mode = s_spec.get("execution_mode", stage.execution_mode or "sequential")
        db.session.flush()
        kept_stage_ids.append(stage.id)
        kept_task_ids = []
        for t_order, t_spec in enumerate(s_spec.get("tasks", []), start=1):
            t_name = (t_spec.get("name") or "").strip()
            if not t_name:
                continue
            task = Task.query.filter_by(stage_id=stage.id, name=t_name).first()
            if not task:
                task = Task(id=resource_id("task"), stage_id=stage.id, name=t_name)
                db.session.add(task)
            task.order = t_spec.get("order", t_order)
            task.run_language = t_spec.get("run_language", task.run_language or "bash")
            task.run_code = t_spec.get("run_code", task.run_code)
            task.on_error = t_spec.get("on_error", task.on_error or "fail")
            task.timeout = int(t_spec.get("timeout", task.timeout or 300))
            task.execution_mode = t_spec.get("execution_mode", task.execution_mode or "sequential")
            db.session.flush()
            kept_task_ids.append(task.id)
        Task.query.filter(
            Task.stage_id == stage.id,
            Task.id.notin_(kept_task_ids),
        ).delete(synchronize_session=False)
    Stage.query.filter(
        Stage.pipeline_id == pipeline_id,
        Stage.id.notin_(kept_stage_ids),
    ).delete(synchronize_session=False)

    pipeline.definition_sha = sha
    db.session.commit()
    updated = db.session.get(Pipeline, pipeline_id)
    return jsonify({"sha": sha, "pipeline": updated.to_dict(include_stages=True)})


@yaml_bp.post("/products/<product_id>/pipelines/<pipeline_id>/git/push")
def git_push_pipeline(product_id: str, pipeline_id: str):
    """Export the pipeline definition to YAML and push it to its git_repo.

    Optional body: ``author_name``, ``author_email``
    Returns the new commit SHA.
    """
    from app.services.git_service import push_pipeline_to_git  # noqa: PLC0415

    pipeline = Pipeline.query.filter_by(id=pipeline_id, product_id=product_id).first_or_404()
    data = request.get_json(silent=True) or {}

    stages_data = [
        {
            "name": s.name,
            "order": s.order,
            "run_language": s.run_language,
            "execution_mode": s.execution_mode or "sequential",
            "tasks": [
                {
                    "name": t.name,
                    "run_language": t.run_language,
                    "execution_mode": t.execution_mode,
                    "on_error": t.on_error,
                    "timeout": t.timeout,
                    "run_code": t.run_code,
                }
                for t in s.tasks
            ],
        }
        for s in pipeline.stages
    ]
    definition = {
        "apiVersion": "conduit/v1",
        "kind": "Pipeline",
        "metadata": {"name": pipeline.name},
        "spec": {
            "kind": pipeline.kind,
            "git_repo": pipeline.git_repo,
            "git_branch": pipeline.git_branch,
            "stages": stages_data,
        },
    }
    yaml_text = yaml.dump(definition, allow_unicode=True, sort_keys=False)

    try:
        sha = push_pipeline_to_git(
            pipeline,
            yaml_text,
            author_name=data.get("author_name", "Conduit"),
            author_email=data.get("author_email", "rw@conduit.local"),
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    pipeline.definition_sha = sha
    db.session.commit()
    return jsonify({"sha": sha, "message": f"Pushed to {pipeline.git_repo}"})
