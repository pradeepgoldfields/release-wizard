"""Task domain model — a sandboxed script unit within a pipeline stage."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions import db


class Task(db.Model):
    """A discrete task within a Stage — runs a bash or python script in a sandbox."""

    __tablename__ = "tasks"

    id = db.Column(db.String(64), primary_key=True)
    stage_id = db.Column(db.String(64), db.ForeignKey("stages.id"), nullable=False)
    name = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)
    # Script execution
    run_language = db.Column(db.String(32), default="bash")  # bash | python
    run_code = db.Column(db.Text, default="")
    # Execution behaviour
    execution_mode = db.Column(db.String(32), default="sequential")  # sequential | parallel
    on_error = db.Column(db.String(32), default="fail")  # fail | warn | continue
    timeout = db.Column(db.Integer, default=300)
    is_required = db.Column(db.Boolean, default=True)
    # Explicit task type tags used for maturity scoring, comma-separated
    # e.g. "sast", "sca,custom-secret-scan", "build"
    task_type = db.Column(db.String(256))

    # ── Task kind ────────────────────────────────────────────────────────────
    # "script"   — default: runs run_code via bash/python (legacy behaviour)
    # "gate"     — runs gate_script; must exit 0 to pass; stage blocked if it fails
    # "approval" — pauses execution until all required approvers have approved
    kind = db.Column(db.String(32), default="script")

    # ── Gate task fields ──────────────────────────────────────────────────────
    gate_script = db.Column(db.Text, default="")       # script body
    gate_language = db.Column(db.String(32), default="bash")  # bash | python

    # ── Approval task fields ──────────────────────────────────────────────────
    # JSON list of approver specs: [{"type":"user","ref":"alice"},{"type":"role","ref":"product-admin"}]
    approval_approvers = db.Column(db.Text, default="[]")
    # How many approvals are required before the gate passes (0 = all listed)
    approval_required_count = db.Column(db.Integer, default=0)
    # Seconds to wait before timing out (0 = no timeout)
    approval_timeout = db.Column(db.Integer, default=0)

    # ── Run condition ─────────────────────────────────────────────────────────
    # "always" | "on_success" | "on_failure" | "on_warning"
    run_condition = db.Column(db.String(32), default="always")

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    stage = db.relationship("Stage", back_populates="tasks")
    runs = db.relationship("TaskRun", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Task id={self.id!r} name={self.name!r} kind={self.kind!r} order={self.order}>"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        import json as _json
        return {
            "id": self.id,
            "stage_id": self.stage_id,
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "run_language": self.run_language,
            "run_code": self.run_code,
            "execution_mode": self.execution_mode,
            "on_error": self.on_error,
            "timeout": self.timeout,
            "is_required": self.is_required,
            "task_type": self.task_type or "",
            "kind": self.kind or "script",
            "gate_script": self.gate_script or "",
            "gate_language": self.gate_language or "bash",
            "approval_approvers": _json.loads(self.approval_approvers or "[]"),
            "approval_required_count": self.approval_required_count or 0,
            "approval_timeout": self.approval_timeout or 0,
            "run_condition": self.run_condition or "always",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TaskRun(db.Model):
    """A single execution of a Task inside an agent sandbox."""

    __tablename__ = "task_runs"

    id = db.Column(db.String(64), primary_key=True)
    task_id = db.Column(db.String(64), db.ForeignKey("tasks.id"), nullable=False)
    stage_run_id = db.Column(db.String(64), db.ForeignKey("stage_runs.id"), nullable=True)
    status = db.Column(db.String(32), default="Pending")  # Pending|Running|Succeeded|Warning|Failed|AwaitingApproval|Skipped
    return_code = db.Column(db.Integer)
    logs = db.Column(db.Text, default="")
    output_json = db.Column(db.Text)  # JSON string captured from last stdout line
    user_input = db.Column(db.Text)  # JSON string — user-supplied input passed as taskRuntime.input
    context_env = db.Column(db.Text)  # JSON — CDT_* env vars injected at execution time
    agent_pool_id = db.Column(db.String(64), db.ForeignKey("agent_pools.id"), nullable=True)
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    finished_at = db.Column(db.DateTime)

    task = db.relationship("Task", back_populates="runs")
    stage_run = db.relationship("StageRun", back_populates="task_runs")
    approval_decisions = db.relationship(
        "ApprovalDecision", back_populates="task_run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TaskRun id={self.id!r} status={self.status!r}>"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        import json as _json

        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_name": self.task.name if self.task else None,
            "task_kind": self.task.kind if self.task else "script",
            "stage_run_id": self.stage_run_id,
            "status": self.status,
            "return_code": self.return_code,
            "logs": self.logs,
            "output_json": self.output_json,
            "context_env": _json.loads(self.context_env or "{}"),
            "agent_pool_id": self.agent_pool_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "approval_decisions": [d.to_dict() for d in (self.approval_decisions or [])],
        }


class ApprovalDecision(db.Model):
    """Records a single approver's vote on an approval task run."""

    __tablename__ = "approval_decisions"

    id = db.Column(db.String(64), primary_key=True)
    task_run_id = db.Column(db.String(64), db.ForeignKey("task_runs.id"), nullable=False)
    user_id = db.Column(db.String(64), db.ForeignKey("users.id"), nullable=False)
    decision = db.Column(db.String(16), nullable=False)  # "approved" | "rejected"
    comment = db.Column(db.Text)
    decided_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    task_run = db.relationship("TaskRun", back_populates="approval_decisions")
    user = db.relationship("User")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_run_id": self.task_run_id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "display_name": self.user.display_name if self.user else None,
            "decision": self.decision,
            "comment": self.comment,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
        }


class AgentPool(db.Model):
    """An execution environment pool for running task containers."""

    __tablename__ = "agent_pools"

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    pool_type = db.Column(db.String(32), default="custom")  # builtin | custom
    cpu_limit = db.Column(db.String(16), default="500m")
    memory_limit = db.Column(db.String(16), default="256Mi")
    max_agents = db.Column(db.Integer, default=5)
    sandbox_network = db.Column(db.Boolean, default=False)  # no cluster access
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"<AgentPool id={self.id!r} name={self.name!r} type={self.pool_type!r}>"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "pool_type": self.pool_type,
            "cpu_limit": self.cpu_limit,
            "memory_limit": self.memory_limit,
            "max_agents": self.max_agents,
            "sandbox_network": self.sandbox_network,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
