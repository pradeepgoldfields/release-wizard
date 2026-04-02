"""YAML export / import for all major resources."""

from __future__ import annotations

import json as _json

import yaml
from flask import Blueprint, Response, jsonify, request

from app.extensions import db
from app.models.environment import Environment
from app.models.pipeline import Pipeline, Stage
from app.models.product import Product
from app.models.property import Property
from app.models.release import Release
from app.models.task import AgentPool, Task
from app.services.id_service import resource_id

yaml_bp = Blueprint("yaml_io", __name__, url_prefix="/api/v1")


def _yaml_response(data: dict) -> Response:
    return Response(yaml.dump(data, allow_unicode=True, sort_keys=False), mimetype="text/yaml")


def _props_for(owner_type: str, owner_id: str) -> list[dict]:
    """Return a list of property dicts for the given owner, or [] if none."""
    props = Property.query.filter_by(owner_type=owner_type, owner_id=owner_id).all()
    return [
        {
            "name": p.name,
            "type": p.value_type,
            "value": p.value,
            "description": p.description or "",
            "required": bool(p.is_required),
        }
        for p in props
    ]


def _apply_properties(owner_type: str, owner_id: str, prop_specs: list[dict]) -> None:
    """Upsert properties from a YAML spec list onto the given owner (no commit)."""
    for spec in prop_specs:
        name = (spec.get("name") or "").strip()
        if not name:
            continue
        prop = Property.query.filter_by(owner_type=owner_type, owner_id=owner_id, name=name).first()
        if not prop:
            prop = Property(
                id=resource_id("prop"), owner_type=owner_type, owner_id=owner_id, name=name
            )
            db.session.add(prop)
        prop.value_type = spec.get("type", prop.value_type or "string")
        prop.value = spec.get("value", prop.value)
        prop.description = spec.get("description", prop.description) or None
        prop.is_required = bool(spec.get("required", prop.is_required or False))


def _task_dict(t: Task) -> dict:
    """Serialize a Task to a full YAML-friendly dict."""
    base: dict = {
        "name": t.name,
        "description": t.description or "",
        "order": t.order,
        "kind": t.kind or "script",
        "task_type": t.task_type or "",
        "run_language": t.run_language or "bash",
        "execution_mode": t.execution_mode or "sequential",
        "on_error": t.on_error or "fail",
        "timeout": t.timeout or 300,
        "is_required": bool(t.is_required),
        "run_condition": t.run_condition or "always",
        "run_code": t.run_code or "",
    }
    if t.kind == "gate":
        base["gate_language"] = t.gate_language or "bash"
        base["gate_script"] = t.gate_script or ""
    elif t.kind == "approval":
        base["approval_approvers"] = _json.loads(t.approval_approvers or "[]")
        base["approval_required_count"] = t.approval_required_count or 0
        base["approval_timeout"] = t.approval_timeout or 0
    props = _props_for("task", t.id)
    if props:
        base["properties"] = props
    return base


def _stage_dict(s: Stage) -> dict:
    """Serialize a Stage to a full YAML-friendly dict."""
    return {
        "name": s.name,
        "order": s.order,
        "run_language": s.run_language or "bash",
        "container_image": s.container_image or "",
        "execution_mode": s.execution_mode or "sequential",
        "run_condition": s.run_condition or "always",
        "is_protected": bool(s.is_protected),
        "accent_color": s.accent_color or "",
        "sandbox": {
            "cpu": s.sandbox_cpu or "500m",
            "memory": s.sandbox_memory or "256Mi",
            "timeout": s.sandbox_timeout or 60,
            "network": bool(s.sandbox_network),
        },
        "entry_gate": _json.loads(s.entry_gate or "{}"),
        "exit_gate": _json.loads(s.exit_gate or "{}"),
        "properties": _props_for("stage", s.id),
        "tasks": [_task_dict(t) for t in s.tasks],
    }


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
                    "properties": _props_for("pipeline", pl.id),
                    "stages": [_stage_dict(s) for s in pl.stages],
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
            "properties": _props_for("pipeline", pipeline.id),
            "stages": [_stage_dict(s) for s in pipeline.stages],
        },
    }
    return _yaml_response(data)


_VALID_TASK_KINDS = {"script", "gate", "approval", "notification"}
_VALID_LANGUAGES = {"bash", "python", "sh", "powershell", "javascript", "ruby"}
_VALID_EXEC_MODES = {"sequential", "parallel"}
_VALID_ON_ERROR = {"fail", "continue", "skip", "warn"}
_VALID_CONDITIONS = {"always", "on_success", "on_failure", "on_warning"}


@yaml_bp.post("/products/<product_id>/pipelines/<pipeline_id>/validate")
def validate_pipeline_yaml(product_id: str, pipeline_id: str):
    """Dry-run validate a pipeline YAML body — no DB writes.

    Returns {"valid": true, "errors": [], "warnings": [], "summary": {...}}
    """
    Pipeline.query.filter_by(id=pipeline_id, product_id=product_id).first_or_404()

    errors: list[str] = []
    warnings: list[str] = []

    # Parse YAML
    try:
        data = _parse_yaml_body()
    except Exception as exc:
        return jsonify(
            {"valid": False, "errors": [f"YAML parse error: {exc}"], "warnings": [], "summary": {}}
        ), 200

    if not isinstance(data, dict):
        return jsonify(
            {
                "valid": False,
                "errors": ["Document must be a YAML mapping"],
                "warnings": [],
                "summary": {},
            }
        ), 200

    spec = data.get("spec", data)
    stage_specs = spec.get("stages", [])

    if not isinstance(stage_specs, list):
        errors.append("`stages` must be a list")
        stage_specs = []

    if not stage_specs:
        warnings.append("No stages defined — pipeline will not execute")

    stage_names: set[str] = set()
    total_tasks = 0

    for s_idx, s_spec in enumerate(stage_specs):
        loc = f"Stage[{s_idx + 1}]"
        if not isinstance(s_spec, dict):
            errors.append(f"{loc}: must be a mapping")
            continue

        s_name = (s_spec.get("name") or "").strip()
        if not s_name:
            errors.append(f"{loc}: missing `name`")
        elif s_name in stage_names:
            errors.append(f"{loc}: duplicate stage name '{s_name}'")
        else:
            stage_names.add(s_name)
            loc = f"Stage '{s_name}'"

        exec_mode = s_spec.get("execution_mode", "sequential")
        if exec_mode not in _VALID_EXEC_MODES:
            errors.append(
                f"{loc}: invalid execution_mode '{exec_mode}' — must be one of {sorted(_VALID_EXEC_MODES)}"
            )

        run_cond = s_spec.get("run_condition", "always")
        if run_cond not in _VALID_CONDITIONS:
            errors.append(f"{loc}: invalid run_condition '{run_cond}'")

        sandbox = s_spec.get("sandbox")
        if sandbox is not None and not isinstance(sandbox, dict):
            errors.append(f"{loc}: `sandbox` must be a mapping")

        for gate_key in ("entry_gate", "exit_gate"):
            gate = s_spec.get(gate_key)
            if gate is not None and not isinstance(gate, dict):
                errors.append(f"{loc}: `{gate_key}` must be a mapping")
            elif isinstance(gate, dict) and gate.get("enabled"):
                if not gate.get("script"):
                    warnings.append(f"{loc}: `{gate_key}` is enabled but has no `script`")

        stage_props = s_spec.get("properties")
        if stage_props is not None and not isinstance(stage_props, list | dict):
            errors.append(f"{loc}: `properties` must be a list or mapping")

        task_specs = s_spec.get("tasks", [])
        if not isinstance(task_specs, list):
            errors.append(f"{loc}: `tasks` must be a list")
            task_specs = []

        if not task_specs:
            warnings.append(f"{loc}: has no tasks")

        task_names: set[str] = set()
        for t_idx, t_spec in enumerate(task_specs):
            t_loc = f"{loc} > Task[{t_idx + 1}]"
            if not isinstance(t_spec, dict):
                errors.append(f"{t_loc}: must be a mapping")
                continue

            t_name = (t_spec.get("name") or "").strip()
            if not t_name:
                errors.append(f"{t_loc}: missing `name`")
            elif t_name in task_names:
                errors.append(f"{t_loc}: duplicate task name '{t_name}'")
            else:
                task_names.add(t_name)
                t_loc = f"{loc} > Task '{t_name}'"

            kind = t_spec.get("kind", "script")
            if kind not in _VALID_TASK_KINDS:
                errors.append(
                    f"{t_loc}: invalid kind '{kind}' — must be one of {sorted(_VALID_TASK_KINDS)}"
                )

            lang = t_spec.get("run_language", "bash")
            if lang not in _VALID_LANGUAGES:
                warnings.append(f"{t_loc}: unrecognised run_language '{lang}'")

            on_err = t_spec.get("on_error", "fail")
            if on_err not in _VALID_ON_ERROR:
                errors.append(
                    f"{t_loc}: invalid on_error '{on_err}' — must be one of {sorted(_VALID_ON_ERROR)}"
                )

            t_cond = t_spec.get("run_condition", "always")
            if t_cond not in _VALID_CONDITIONS:
                errors.append(f"{t_loc}: invalid run_condition '{t_cond}'")

            timeout = t_spec.get("timeout", 300)
            if not isinstance(timeout, int | float) or int(timeout) <= 0:
                errors.append(f"{t_loc}: `timeout` must be a positive number")

            if kind == "gate":
                gate_script = t_spec.get("gate_script", "")
                if not gate_script:
                    warnings.append(
                        f"{t_loc}: gate task has no `gate_script` — it will always pass"
                    )
                gate_lang = t_spec.get("gate_language", "bash")
                if gate_lang not in _VALID_LANGUAGES:
                    warnings.append(f"{t_loc}: unrecognised gate_language '{gate_lang}'")

            if kind == "approval":
                approvers = t_spec.get("approval_approvers", [])
                if not isinstance(approvers, list):
                    errors.append(f"{t_loc}: `approval_approvers` must be a list")
                else:
                    for a in approvers:
                        if not isinstance(a, dict) or "type" not in a or "ref" not in a:
                            warnings.append(
                                f"{t_loc}: each approver should have 'type' and 'ref' keys"
                            )
                            break
                req = t_spec.get("approval_required_count", 0)
                if not isinstance(req, int) or req < 0:
                    errors.append(
                        f"{t_loc}: `approval_required_count` must be a non-negative integer"
                    )
                at = t_spec.get("approval_timeout", 0)
                if not isinstance(at, int | float) or at < 0:
                    errors.append(f"{t_loc}: `approval_timeout` must be a non-negative number")

            # Validate properties block if present
            props = t_spec.get("properties")
            if props is not None and not isinstance(props, list | dict):
                errors.append(f"{t_loc}: `properties` must be a list or mapping")

            total_tasks += 1

    summary = {
        "stages": len(stage_specs),
        "tasks": total_tasks,
        "errors": len(errors),
        "warnings": len(warnings),
    }

    return jsonify(
        {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "summary": summary,
        }
    )


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


def _apply_task_spec(task: Task, t_spec: dict, fallback_order: int) -> None:
    """Apply a parsed task YAML spec onto a Task ORM object (does not flush/commit)."""
    task.order = t_spec.get("order", fallback_order)
    task.description = t_spec.get("description", task.description) or None
    task.kind = t_spec.get("kind", task.kind or "script")
    task.task_type = t_spec.get("task_type", task.task_type) or None
    task.run_language = t_spec.get("run_language", task.run_language or "bash")
    task.run_code = t_spec.get("run_code", task.run_code) or ""
    task.execution_mode = t_spec.get("execution_mode", task.execution_mode or "sequential")
    task.on_error = t_spec.get("on_error", task.on_error or "fail")
    task.timeout = int(t_spec.get("timeout", task.timeout or 300))
    task.is_required = bool(
        t_spec.get("is_required", task.is_required if task.is_required is not None else True)
    )
    task.run_condition = t_spec.get("run_condition", task.run_condition or "always")
    # Gate fields
    task.gate_language = t_spec.get("gate_language", task.gate_language or "bash")
    task.gate_script = t_spec.get("gate_script", task.gate_script) or ""
    # Approval fields
    if "approval_approvers" in t_spec:
        raw = t_spec["approval_approvers"]
        task.approval_approvers = _json.dumps(raw) if isinstance(raw, list) else (raw or "[]")
    task.approval_required_count = int(
        t_spec.get("approval_required_count", task.approval_required_count or 0)
    )
    task.approval_timeout = int(t_spec.get("approval_timeout", task.approval_timeout or 0))


def _apply_stage_spec(stage: Stage, s_spec: dict) -> None:
    """Apply a parsed stage YAML spec onto a Stage ORM object (does not flush/commit)."""
    stage.order = int(s_spec.get("order", stage.order or 0))
    stage.run_language = s_spec.get("run_language", stage.run_language or "bash")
    stage.container_image = s_spec.get("container_image", stage.container_image) or None
    stage.execution_mode = s_spec.get("execution_mode", stage.execution_mode or "sequential")
    stage.run_condition = s_spec.get("run_condition", stage.run_condition or "always")
    if "is_protected" in s_spec:
        stage.is_protected = bool(s_spec["is_protected"])
    if "accent_color" in s_spec:
        stage.accent_color = s_spec["accent_color"] or None
    # Sandbox sub-object
    sandbox = s_spec.get("sandbox")
    if isinstance(sandbox, dict):
        stage.sandbox_cpu = sandbox.get("cpu", stage.sandbox_cpu or "500m")
        stage.sandbox_memory = sandbox.get("memory", stage.sandbox_memory or "256Mi")
        stage.sandbox_timeout = int(sandbox.get("timeout", stage.sandbox_timeout or 60))
        stage.sandbox_network = bool(sandbox.get("network", stage.sandbox_network or False))
    # Gates
    if "entry_gate" in s_spec:
        raw = s_spec["entry_gate"]
        stage.entry_gate = _json.dumps(raw) if isinstance(raw, dict) else (raw or "{}")
    if "exit_gate" in s_spec:
        raw = s_spec["exit_gate"]
        stage.exit_gate = _json.dumps(raw) if isinstance(raw, dict) else (raw or "{}")


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

    # Pipeline-level properties
    if "properties" in spec:
        _apply_properties("pipeline", pipeline_id, spec["properties"])

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
        _apply_stage_spec(stage, s_spec)
        db.session.flush()
        kept_stage_ids.append(stage.id)

        if "properties" in s_spec:
            _apply_properties("stage", stage.id, s_spec["properties"])

        kept_task_ids = []
        for t_order, t_spec in enumerate(s_spec.get("tasks", []), start=1):
            t_name = (t_spec.get("name") or "").strip()
            if not t_name:
                continue
            task = Task.query.filter_by(stage_id=stage.id, name=t_name).first()
            if not task:
                task = Task(id=resource_id("task"), stage_id=stage.id, name=t_name)
                db.session.add(task)
            _apply_task_spec(task, t_spec, t_order)
            db.session.flush()
            kept_task_ids.append(task.id)

            if "properties" in t_spec:
                _apply_properties("task", task.id, t_spec["properties"])

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
    updated = db.session.get(Pipeline, pipeline_id)
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

    if "properties" in spec_inner:
        _apply_properties("pipeline", pipeline_id, spec_inner["properties"])

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
        _apply_stage_spec(stage, s_spec)
        db.session.flush()
        kept_stage_ids.append(stage.id)
        if "properties" in s_spec:
            _apply_properties("stage", stage.id, s_spec["properties"])
        kept_task_ids = []
        for t_order, t_spec in enumerate(s_spec.get("tasks", []), start=1):
            t_name = (t_spec.get("name") or "").strip()
            if not t_name:
                continue
            task = Task.query.filter_by(stage_id=stage.id, name=t_name).first()
            if not task:
                task = Task(id=resource_id("task"), stage_id=stage.id, name=t_name)
                db.session.add(task)
            _apply_task_spec(task, t_spec, t_order)
            db.session.flush()
            kept_task_ids.append(task.id)
            if "properties" in t_spec:
                _apply_properties("task", task.id, t_spec["properties"])
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

    definition = {
        "apiVersion": "conduit/v1",
        "kind": "Pipeline",
        "metadata": {"name": pipeline.name},
        "spec": {
            "kind": pipeline.kind,
            "git_repo": pipeline.git_repo,
            "git_branch": pipeline.git_branch,
            "properties": _props_for("pipeline", pipeline.id),
            "stages": [_stage_dict(s) for s in pipeline.stages],
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
