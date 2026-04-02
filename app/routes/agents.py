"""HTTP handlers for AgentPool and TaskRun resources."""

from __future__ import annotations

import json

from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.models.pipeline import Stage
from app.models.task import AgentPool, Task, TaskRun
from app.services import cache_service
from app.services.execution_service import create_and_run_task, ensure_sandbox_image
from app.services.id_service import resource_id

_POOLS_CACHE_KEY = "agent_pools:list"

agents_bp = Blueprint("agents", __name__, url_prefix="/api/v1")

# ── Built-in pool seeds ───────────────────────────────────────────────────────

BUILTIN_POOLS = [
    # ── Language sandboxes ────────────────────────────────────────────────────
    {
        "name": "bash-default",
        "description": "Built-in bash execution sandbox (no network access)",
        "pool_type": "builtin",
        "agent_role": "general",
        "skills": json.dumps(["bash", "shell", "git"]),
        "mcp_config": json.dumps(
            {"transport": "stdio", "command": ["conduit-mcp", "--role", "general"]}
        ),
        "cpu_limit": "500m",
        "memory_limit": "256Mi",
        "max_agents": 10,
        "sandbox_network": False,
    },
    {
        "name": "python-default",
        "description": "Built-in python3 execution sandbox (no network access)",
        "pool_type": "builtin",
        "agent_role": "general",
        "skills": json.dumps(["python", "pip", "pytest", "git"]),
        "mcp_config": json.dumps(
            {"transport": "stdio", "command": ["conduit-mcp", "--role", "general"]}
        ),
        "cpu_limit": "500m",
        "memory_limit": "512Mi",
        "max_agents": 10,
        "sandbox_network": False,
    },
    # ── Role-specific built-in stubs (connect MCP server when available) ──────
    {
        "name": "developer",
        "description": "Code generation, refactoring, lint, and dependency management agent",
        "pool_type": "builtin",
        "agent_role": "developer",
        "skills": json.dumps(
            [
                "python",
                "javascript",
                "typescript",
                "bash",
                "unit-test",
                "code-gen",
                "refactor",
                "lint",
                "dependency-update",
                "dockerfile",
            ]
        ),
        "mcp_config": json.dumps(
            {
                "transport": "sse",
                "url": "http://conduit-mcp-developer:8080/sse",
                "env": {"ROLE": "developer", "TOOLS": "fs,git,code,lint"},
            }
        ),
        "cpu_limit": "1000m",
        "memory_limit": "2Gi",
        "max_agents": 5,
        "sandbox_network": True,
    },
    {
        "name": "tester",
        "description": "Test generation and execution — unit, integration, e2e, coverage",
        "pool_type": "builtin",
        "agent_role": "tester",
        "skills": json.dumps(
            [
                "pytest",
                "jest",
                "selenium",
                "playwright",
                "unit-test",
                "integration-test",
                "e2e-test",
                "code-coverage",
                "test-gen",
            ]
        ),
        "mcp_config": json.dumps(
            {
                "transport": "sse",
                "url": "http://conduit-mcp-tester:8080/sse",
                "env": {"ROLE": "tester", "TOOLS": "fs,git,test-runner,coverage"},
            }
        ),
        "cpu_limit": "1000m",
        "memory_limit": "2Gi",
        "max_agents": 5,
        "sandbox_network": True,
    },
    {
        "name": "business-analyst",
        "description": "Requirements analysis, acceptance criteria, user stories, and BDD scenarios",
        "pool_type": "builtin",
        "agent_role": "business-analyst",
        "skills": json.dumps(
            [
                "requirements-analysis",
                "acceptance-criteria",
                "user-story",
                "bdd",
                "gherkin",
                "stakeholder-report",
                "gap-analysis",
                "process-mapping",
            ]
        ),
        "mcp_config": json.dumps(
            {
                "transport": "sse",
                "url": "http://conduit-mcp-ba:8080/sse",
                "env": {"ROLE": "business-analyst", "TOOLS": "docs,jira,confluence,slack"},
            }
        ),
        "cpu_limit": "500m",
        "memory_limit": "1Gi",
        "max_agents": 3,
        "sandbox_network": True,
    },
    {
        "name": "orchestrator",
        "description": "Pipeline coordination, gate evaluation, approval routing, and workflow decisions",
        "pool_type": "builtin",
        "agent_role": "orchestrator",
        "skills": json.dumps(
            [
                "pipeline-coordination",
                "dependency-resolution",
                "workflow-decision",
                "gate-evaluation",
                "approval-routing",
                "stage-scheduling",
                "notify",
            ]
        ),
        "mcp_config": json.dumps(
            {
                "transport": "sse",
                "url": "http://conduit-mcp-orchestrator:8080/sse",
                "env": {"ROLE": "orchestrator", "TOOLS": "conduit-api,slack,pagerduty,jira"},
            }
        ),
        "cpu_limit": "500m",
        "memory_limit": "1Gi",
        "max_agents": 2,
        "sandbox_network": True,
    },
    {
        "name": "deployer",
        "description": "Container builds, Helm deployments, kubectl operations, and rollbacks",
        "pool_type": "builtin",
        "agent_role": "deployer",
        "skills": json.dumps(
            [
                "docker-build",
                "helm-deploy",
                "kubectl",
                "canary",
                "blue-green",
                "rollback",
                "terraform",
                "ansible",
                "argocd",
            ]
        ),
        "mcp_config": json.dumps(
            {
                "transport": "sse",
                "url": "http://conduit-mcp-deployer:8080/sse",
                "env": {"ROLE": "deployer", "TOOLS": "kubectl,helm,terraform,vault"},
            }
        ),
        "cpu_limit": "2000m",
        "memory_limit": "4Gi",
        "max_agents": 4,
        "sandbox_network": True,
    },
    {
        "name": "sca-scanner",
        "description": "Software composition analysis — dependency CVEs, SBOM generation, licence checks",
        "pool_type": "builtin",
        "agent_role": "sca-scanner",
        "skills": json.dumps(
            [
                "sca",
                "dependency-check",
                "trivy",
                "grype",
                "license-check",
                "sbom",
                "cve-triage",
            ]
        ),
        "mcp_config": json.dumps(
            {
                "transport": "stdio",
                "command": ["conduit-mcp", "--role", "sca-scanner"],
                "env": {"SCANNERS": "trivy,grype,cyclonedx", "NETWORK": "false"},
            }
        ),
        "cpu_limit": "1000m",
        "memory_limit": "2Gi",
        "max_agents": 3,
        "sandbox_network": False,
    },
    {
        "name": "dast-scanner",
        "description": "Dynamic application security testing against live or staging environments",
        "pool_type": "builtin",
        "agent_role": "dast-scanner",
        "skills": json.dumps(
            [
                "dast",
                "zap",
                "nikto",
                "nuclei",
                "api-fuzzing",
                "auth-testing",
                "owasp-top10",
            ]
        ),
        "mcp_config": json.dumps(
            {
                "transport": "sse",
                "url": "http://conduit-mcp-dast:8080/sse",
                "env": {"ROLE": "dast-scanner", "TOOLS": "zap,nuclei,burp-rest"},
            }
        ),
        "cpu_limit": "1000m",
        "memory_limit": "2Gi",
        "max_agents": 2,
        "sandbox_network": True,
    },
    {
        "name": "sast-scanner",
        "description": "Static application security testing — source code, secrets, and IaC scanning",
        "pool_type": "builtin",
        "agent_role": "sast-scanner",
        "skills": json.dumps(
            [
                "sast",
                "semgrep",
                "bandit",
                "sonarqube",
                "codeql",
                "secret-scan",
                "iac-scan",
            ]
        ),
        "mcp_config": json.dumps(
            {
                "transport": "stdio",
                "command": ["conduit-mcp", "--role", "sast-scanner"],
                "env": {"SCANNERS": "semgrep,bandit,gitleaks", "NETWORK": "false"},
            }
        ),
        "cpu_limit": "1000m",
        "memory_limit": "2Gi",
        "max_agents": 3,
        "sandbox_network": False,
    },
    {
        "name": "code-reviewer",
        "description": "Automated code review — style, logic, security patterns, complexity, and PR comments",
        "pool_type": "builtin",
        "agent_role": "code-reviewer",
        "skills": json.dumps(
            [
                "code-review",
                "diff-analysis",
                "style-check",
                "complexity-analysis",
                "security-pattern-review",
                "pr-comment",
                "change-summary",
            ]
        ),
        "mcp_config": json.dumps(
            {
                "transport": "sse",
                "url": "http://conduit-mcp-reviewer:8080/sse",
                "env": {"ROLE": "code-reviewer", "TOOLS": "github,gitlab,fs,git"},
            }
        ),
        "cpu_limit": "500m",
        "memory_limit": "1Gi",
        "max_agents": 4,
        "sandbox_network": True,
    },
    {
        "name": "git-committer",
        "description": "Commit reviewed changes, push to remote Git, manage tags, and generate changelogs",
        "pool_type": "builtin",
        "agent_role": "git-committer",
        "skills": json.dumps(
            [
                "git-commit",
                "git-push",
                "git-tag",
                "branch-management",
                "changelog-gen",
                "conventional-commits",
                "release-cut",
            ]
        ),
        "mcp_config": json.dumps(
            {
                "transport": "sse",
                "url": "http://conduit-mcp-git:8080/sse",
                "env": {"ROLE": "git-committer", "TOOLS": "git,github,gitlab,ssh-key-vault"},
            }
        ),
        "cpu_limit": "500m",
        "memory_limit": "512Mi",
        "max_agents": 3,
        "sandbox_network": True,
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


@agents_bp.patch("/agent-pools/<pool_id>")
def update_agent_pool(pool_id: str):
    """Update a custom agent pool's metadata."""
    pool = db.get_or_404(AgentPool, pool_id)
    if pool.pool_type == "builtin":
        return jsonify({"error": "Cannot modify built-in agent pools"}), 400
    data = request.get_json(silent=True) or {}
    for field in ("name", "description", "cpu_limit", "memory_limit"):
        if field in data:
            setattr(pool, field, data[field])
    if "max_agents" in data:
        pool.max_agents = int(data["max_agents"])
    if "is_active" in data:
        pool.is_active = bool(data["is_active"])
    db.session.commit()
    cache_service.invalidate(_POOLS_CACHE_KEY)
    return jsonify(pool.to_dict())


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


# ── Scratch script execution ──────────────────────────────────────────────────


_VALID_LANGUAGES: frozenset[str] = frozenset({"bash", "python"})
_MAX_SCRATCH_TIMEOUT: int = 60  # seconds — cap scratch runs to avoid abuse


@agents_bp.post("/script-run")
def scratch_script_run():
    """Run an arbitrary script without a saved task — for in-editor testing.

    Body (JSON):
      language   "bash" | "python"  (default: "bash")
      code       Script text to execute
      timeout    Max seconds (capped at 60, default: 30)
      env        Optional {name: value} mapping injected as extra env vars
      task_id    Optional task UUID — if supplied, env vars from its resolved
                 properties are also injected (same as a real run)

    Returns 202 with a TaskRun dict; poll GET /task-runs/<id> for results.
    """
    data = request.get_json(silent=True) or {}
    language = str(data.get("language") or "bash").strip()
    code = str(data.get("code") or "").strip()
    timeout = min(int(data.get("timeout") or 30), _MAX_SCRATCH_TIMEOUT)
    extra_env: dict[str, str] = {str(k): str(v) for k, v in (data.get("env") or {}).items()}

    if language not in _VALID_LANGUAGES:
        return jsonify(
            {"error": f"language must be one of: {', '.join(sorted(_VALID_LANGUAGES))}"}
        ), 400
    if not code:
        return jsonify({"error": "code is required"}), 400

    # Ensure the sandbox image exists before queuing the run
    ok, msg = ensure_sandbox_image()
    if not ok:
        return jsonify({"error": f"Sandbox unavailable: {msg}"}), 503

    task_run = create_and_run_task(
        task_id=None,  # scratch — no task record
        language=language,
        code=code,
        timeout=timeout,
        on_error="fail",
        agent_pool_id=data.get("agent_pool_id"),
        stage_run_id=None,
        extra_env=extra_env,
        app=current_app._get_current_object(),  # noqa: SLF001
    )
    return jsonify(task_run.to_dict()), 202


@agents_bp.get("/script-run/sandbox-status")
def sandbox_status():
    """Return whether the sandbox container image is built and ready."""
    from app.services.execution_service import SANDBOX_IMAGE, _container_runtime  # noqa: PLC0415

    rt = _container_runtime()
    if not rt:
        return jsonify({"ready": False, "reason": "No container runtime (docker/podman) on PATH"})

    check = __import__("subprocess").run(
        [rt, "image", "inspect", SANDBOX_IMAGE],
        capture_output=True,
        timeout=10,
    )
    ready = check.returncode == 0
    return jsonify(
        {
            "ready": ready,
            "image": SANDBOX_IMAGE,
            "runtime": rt,
            "reason": None
            if ready
            else "Image not built yet — first run will build it automatically",
        }
    )
