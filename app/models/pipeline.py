"""Pipeline and Stage domain models — CI/CD pipeline definitions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import ComplianceRating, PipelineKind
from app.extensions import db


class Stage(db.Model):
    """A single step within a pipeline — runs a container image or inline script."""

    __tablename__ = "stages"

    id = db.Column(db.String(64), primary_key=True)
    pipeline_id = db.Column(db.String(64), db.ForeignKey("pipelines.id"), nullable=False)
    name = db.Column(db.String(256), nullable=False)
    order = db.Column(db.Integer, default=0)
    container_image = db.Column(db.String(512))
    # inline custom code support
    run_language = db.Column(db.String(32))  # python, node, bash
    run_code = db.Column(db.Text)
    run_file = db.Column(db.String(512))
    # sandbox limits
    sandbox_cpu = db.Column(db.String(16), default="500m")
    sandbox_memory = db.Column(db.String(16), default="256Mi")
    sandbox_timeout = db.Column(db.Integer, default=60)
    sandbox_network = db.Column(db.Boolean, default=False)
    # JSON schemas stored as text
    input_schema = db.Column(db.Text, default="{}")
    output_schema = db.Column(db.Text, default="{}")
    is_protected = db.Column(db.Boolean, default=False)  # org-managed stage
    accent_color = db.Column(db.String(64))  # user-chosen hex or gradient stop, e.g. "#3b82f6"
    execution_mode = db.Column(db.String(16), default="sequential")  # sequential | parallel

    # ── Gates ─────────────────────────────────────────────────────────────────
    # JSON: {"enabled": true, "language": "bash", "script": "...", "timeout": 60}
    entry_gate = db.Column(db.Text, default="{}")
    exit_gate = db.Column(db.Text, default="{}")

    # ── Run condition ─────────────────────────────────────────────────────────
    # "always" | "on_success" | "on_failure" | "on_warning"
    run_condition = db.Column(db.String(32), default="always")

    pipeline = db.relationship("Pipeline", back_populates="stages")
    tasks = db.relationship(
        "Task", back_populates="stage", cascade="all, delete-orphan", order_by="Task.order"
    )

    def __repr__(self) -> str:
        return f"<Stage id={self.id!r} name={self.name!r} order={self.order}>"

    def to_dict(self, include_tasks: bool = True) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        data: dict[str, Any] = {
            "id": self.id,
            "pipeline_id": self.pipeline_id,
            "name": self.name,
            "order": self.order,
            "container_image": self.container_image,
            "run_language": self.run_language,
            "run_file": self.run_file,
            "sandbox": {
                "cpu": self.sandbox_cpu,
                "memory": self.sandbox_memory,
                "timeout": self.sandbox_timeout,
                "network": self.sandbox_network,
            },
            "input_schema": json.loads(self.input_schema or "{}"),
            "output_schema": json.loads(self.output_schema or "{}"),
            "is_protected": self.is_protected,
            "accent_color": self.accent_color or None,
            "execution_mode": self.execution_mode or "sequential",
            "entry_gate": json.loads(self.entry_gate or "{}"),
            "exit_gate": json.loads(self.exit_gate or "{}"),
            "run_condition": self.run_condition or "always",
        }
        if include_tasks:
            data["tasks"] = [t.to_dict() for t in self.tasks]
        return data


class Pipeline(db.Model):
    """A CI or CD pipeline definition belonging to a product."""

    __tablename__ = "pipelines"

    id = db.Column(db.String(64), primary_key=True)
    product_id = db.Column(db.String(64), db.ForeignKey("products.id"), nullable=False)
    application_id = db.Column(
        db.String(64), db.ForeignKey("application_artifacts.id"), nullable=True
    )
    name = db.Column(db.String(256), nullable=False)
    kind = db.Column(db.String(16), default=PipelineKind.CI)
    git_repo = db.Column(db.String(512))
    git_branch = db.Column(db.String(128), default="main")
    definition_sha = db.Column(db.String(64))  # last synced Git commit
    accent_color = db.Column(
        db.String(64)
    )  # user-chosen hex for the pipeline container, e.g. "#3b82f6"
    protected_segment_version = db.Column(db.Integer, default=0)
    compliance_score = db.Column(db.Float, default=0.0)
    compliance_rating = db.Column(db.String(32), default=ComplianceRating.NON_COMPLIANT)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    product = db.relationship("Product", back_populates="pipelines")
    application = db.relationship("ApplicationArtifact", back_populates="pipelines")
    stages = db.relationship(
        "Stage", back_populates="pipeline", cascade="all, delete-orphan", order_by=Stage.order
    )
    runs = db.relationship("PipelineRun", back_populates="pipeline", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Pipeline id={self.id!r} name={self.name!r} kind={self.kind!r}>"

    def to_dict(self, include_stages: bool = False) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        data: dict[str, Any] = {
            "id": self.id,
            "product_id": self.product_id,
            "application_id": self.application_id,
            "name": self.name,
            "kind": self.kind,
            "git_repo": self.git_repo,
            "git_branch": self.git_branch,
            "definition_sha": self.definition_sha,
            "accent_color": self.accent_color or None,
            "protected_segment_version": self.protected_segment_version,
            "compliance_score": self.compliance_score,
            "compliance_rating": self.compliance_rating,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_stages:
            data["stages"] = [s.to_dict() for s in self.stages]
        return data
