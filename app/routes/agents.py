"""HTTP handlers for AgentPool and TaskRun resources."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.models.pipeline import Stage
from app.models.task import AgentPool, Task, TaskRun
from app.services import cache_service
from app.services.execution_service import create_and_run_task
from app.services.id_service import resource_id

_POOLS_CACHE_KEY = "agent_pools:list"

agents_bp = Blueprint("agents", __name__, url_prefix="/api/v1")

# ── Built-in pool seeds ───────────────────────────────────────────────────────

BUILTIN_POOLS = [
    {
        "name": "bash-default",
        "description": "Built-in bash execution sandbox (no network access)",
        "pool_type": "builtin",
        "cpu_limit": "500m",
        "memory_limit": "256Mi",
        "max_agents": 10,
        "sandbox_network": False,
    },
    {
        "name": "python-default",
        "description": "Built-in python3 execution sandbox (no network access)",
        "pool_type": "builtin",
        "cpu_limit": "500m",
        "memory_limit": "512Mi",
        "max_agents": 10,
        "sandbox_network": False,
    },
]


def ensure_builtin_pools() -> None:
    """Seed built-in agent pools if they don't exist yet."""
    for spec in BUILTIN_POOLS:
        if not AgentPool.query.filter_by(name=spec["name"]).first():
            pool = AgentPool(id=resource_id("pool"), **spec)
            db.session.add(pool)
    db.session.commit()


# ── Agent Pool CRUD ───────────────────────────────────────────────────────────


@agents_bp.get("/agent-pools")
def list_agent_pools():
    """Return all agent pools (builtin + custom), seeding builtins first."""
    cached = cache_service.get(_POOLS_CACHE_KEY)
    if cached is not None:
        return jsonify(cached)
    ensure_builtin_pools()
    pools = AgentPool.query.order_by(AgentPool.pool_type, AgentPool.name).all()
    data = [p.to_dict() for p in pools]
    cache_service.set(_POOLS_CACHE_KEY, data, ttl=30)
    return jsonify(data)


@agents_bp.post("/agent-pools")
def create_agent_pool():
    """Create a custom agent pool."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    pool = AgentPool(
        id=resource_id("pool"),
        name=name,
        description=data.get("description"),
        pool_type="custom",
        cpu_limit=data.get("cpu_limit", "500m"),
        memory_limit=data.get("memory_limit", "256Mi"),
        max_agents=int(data.get("max_agents", 5)),
        sandbox_network=False,
    )
    db.session.add(pool)
    db.session.commit()
    cache_service.invalidate(_POOLS_CACHE_KEY)
    return jsonify(pool.to_dict()), 201


@agents_bp.delete("/agent-pools/<pool_id>")
def delete_agent_pool(pool_id: str):
    """Delete a custom agent pool."""
    pool = db.get_or_404(AgentPool, pool_id)
    if pool.pool_type == "builtin":
        return jsonify({"error": "Cannot delete built-in agent pools"}), 400
    db.session.delete(pool)
    db.session.commit()
    cache_service.invalidate(_POOLS_CACHE_KEY)
    return "", 204


# ── Task execution ────────────────────────────────────────────────────────────


@agents_bp.post(
    "/products/<product_id>/pipelines/<pipeline_id>/stages/<stage_id>/tasks/<task_id>/run"
)
def run_task(product_id: str, pipeline_id: str, stage_id: str, task_id: str):
    """Execute a task's script in a sandbox and return the TaskRun record.

    The execution is asynchronous — poll GET …/runs/:id for status.
    Optional body: ``agent_pool_id``, ``stage_run_id``
    """
    Stage.query.filter_by(id=stage_id, pipeline_id=pipeline_id).first_or_404()
    task = Task.query.filter_by(id=task_id, stage_id=stage_id).first_or_404()
    data = request.get_json(silent=True) or {}

    if not task.run_code or not task.run_code.strip():
        return jsonify({"error": "Task has no script to run"}), 400

    task_run = create_and_run_task(
        task_id=task.id,
        language=task.run_language or "bash",
        code=task.run_code,
        timeout=task.timeout or 300,
        on_error=task.on_error or "fail",
        agent_pool_id=data.get("agent_pool_id"),
        stage_run_id=data.get("stage_run_id"),
        app=current_app._get_current_object(),  # noqa: SLF001
    )
    return jsonify(task_run.to_dict()), 202


@agents_bp.get(
    "/products/<product_id>/pipelines/<pipeline_id>/stages/<stage_id>/tasks/<task_id>/runs"
)
def list_task_runs(product_id: str, pipeline_id: str, stage_id: str, task_id: str):
    """Return all runs for a task, newest first."""
    runs = (
        TaskRun.query.filter_by(task_id=task_id).order_by(TaskRun.started_at.desc()).limit(50).all()
    )
    return jsonify([r.to_dict() for r in runs])


@agents_bp.get("/task-runs/<run_id>")
def get_task_run(run_id: str):
    """Return a single TaskRun by ID (poll for status)."""
    run = db.get_or_404(TaskRun, run_id)
    return jsonify(run.to_dict())
