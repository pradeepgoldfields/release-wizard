"""Run domain models — execution records for pipeline and release runs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.enums import RunStatus
from app.extensions import db


class StageRun(db.Model):
    """A single stage execution within a PipelineRun."""

    __tablename__ = "stage_runs"

    id = db.Column(db.String(64), primary_key=True)
    pipeline_run_id = db.Column(db.String(64), db.ForeignKey("pipeline_runs.id"), nullable=False)
    stage_id = db.Column(db.String(64), db.ForeignKey("stages.id"), nullable=False)
    status = db.Column(db.String(32), default=RunStatus.PENDING)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    logs_ref = db.Column(db.String(512))
    exit_code = db.Column(db.Integer)
    runtime_properties = db.Column(db.Text, default="{}")  # JSON — stage-level properties

    pipeline_run = db.relationship("PipelineRun", back_populates="stage_runs")
    stage = db.relationship("Stage", foreign_keys=[stage_id], lazy="joined")
    task_runs = db.relationship(
        "TaskRun",
        back_populates="stage_run",
        cascade="all, delete-orphan",
        order_by="TaskRun.started_at",
    )

    def __repr__(self) -> str:
        return f"<StageRun id={self.id!r} status={self.status!r}>"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        import json as _json

        return {
            "id": self.id,
            "pipeline_run_id": self.pipeline_run_id,
            "stage_id": self.stage_id,
            "stage_name": self.stage.name if self.stage else None,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "logs_ref": self.logs_ref,
            "exit_code": self.exit_code,
            "runtime_properties": _json.loads(self.runtime_properties or "{}"),
            "task_runs": [
                {
                    "id": tr.id,
                    "task_id": tr.task_id,
                    "task_name": tr.task.name if tr.task else None,
                    "status": tr.status,
                    "return_code": tr.return_code,
                    "logs": tr.logs,
                    "output_json": tr.output_json,
                    "started_at": tr.started_at.isoformat() if tr.started_at else None,
                    "finished_at": tr.finished_at.isoformat() if tr.finished_at else None,
                }
                for tr in self.task_runs
            ],
        }


class PipelineRun(db.Model):
    """A single execution of a pipeline — identified by plrun_<ulid>."""

    __tablename__ = "pipeline_runs"

    id = db.Column(db.String(64), primary_key=True)  # plrun_<ULID>
    pipeline_id = db.Column(db.String(64), db.ForeignKey("pipelines.id"), nullable=False)
    release_run_id = db.Column(db.String(64), db.ForeignKey("release_runs.id"), nullable=True)
    status = db.Column(db.String(32), default=RunStatus.PENDING)
    commit_sha = db.Column(db.String(64))
    artifact_id = db.Column(db.String(128))
    compliance_rating = db.Column(db.String(32))
    compliance_score = db.Column(db.Float)
    triggered_by = db.Column(db.String(128))
    runtime_properties = db.Column(db.Text, default="{}")  # JSON — pipeline-level properties
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    finished_at = db.Column(db.DateTime)

    pipeline = db.relationship("Pipeline", back_populates="runs")
    release_run = db.relationship("ReleaseRun", back_populates="pipeline_runs")
    stage_runs = db.relationship(
        "StageRun", back_populates="pipeline_run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PipelineRun id={self.id!r} status={self.status!r}>"

    def to_dict(self, include_stages: bool = False) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        import json as _json

        data: dict[str, Any] = {
            "id": self.id,
            "pipeline_id": self.pipeline_id,
            "product_id": self.pipeline.product_id if self.pipeline else None,
            "release_run_id": self.release_run_id,
            "status": self.status,
            "commit_sha": self.commit_sha,
            "artifact_id": self.artifact_id,
            "compliance_rating": self.compliance_rating,
            "compliance_score": self.compliance_score,
            "triggered_by": self.triggered_by,
            "runtime_properties": _json.loads(self.runtime_properties or "{}"),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }
        if include_stages:
            data["stage_runs"] = [sr.to_dict() for sr in self.stage_runs]
        return data


class ReleaseRun(db.Model):
    """A full release execution across environments — identified by rrun_<ulid>."""

    __tablename__ = "release_runs"

    id = db.Column(db.String(64), primary_key=True)  # rrun_<ULID>
    release_id = db.Column(db.String(64), db.ForeignKey("releases.id"), nullable=False)
    status = db.Column(db.String(32), default=RunStatus.PENDING)
    compliance_rating = db.Column(db.String(32))
    compliance_score = db.Column(db.Float)
    triggered_by = db.Column(db.String(128))
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    finished_at = db.Column(db.DateTime)

    release = db.relationship("Release", back_populates="runs")
    pipeline_runs = db.relationship("PipelineRun", back_populates="release_run")

    def __repr__(self) -> str:
        return f"<ReleaseRun id={self.id!r} status={self.status!r}>"

    def to_dict(self, include_pipeline_runs: bool = False) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        data: dict[str, Any] = {
            "id": self.id,
            "release_id": self.release_id,
            "status": self.status,
            "compliance_rating": self.compliance_rating,
            "compliance_score": self.compliance_score,
            "triggered_by": self.triggered_by,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }
        if include_pipeline_runs:
            data["pipeline_runs"] = [pr.to_dict() for pr in self.pipeline_runs]
        return data
