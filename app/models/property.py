"""Property and ParameterValue domain models.

Design-time properties live on definition objects (Product, Pipeline, Stage, Task).
Runtime overrides live on execution objects (PipelineRun, StageRun, TaskRun).
Hierarchical resolution is handled by property_service.resolve().
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions import db


class Property(db.Model):
    """A named value attached to a definition object at design time.

    owner_type  one of: "product" | "pipeline" | "stage" | "task"
    owner_id    FK-like reference to the owning object (not a DB FK so the
                table stays generic and migration-free as new owner types are
                added).
    value_type  Controls how the value is coerced on read:
                "string" | "number" | "boolean" | "secret" | "json"
    """

    __tablename__ = "properties"

    id = db.Column(db.String(64), primary_key=True)
    owner_type = db.Column(db.String(32), nullable=False, index=True)
    owner_id = db.Column(db.String(64), nullable=False, index=True)
    name = db.Column(db.String(256), nullable=False)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(16), default="string")  # string|number|boolean|secret|json
    description = db.Column(db.Text)
    is_required = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        db.UniqueConstraint("owner_type", "owner_id", "name", name="uq_property_owner_name"),
    )

    def __repr__(self) -> str:
        return f"<Property {self.owner_type}/{self.owner_id} {self.name!r}={self.value!r}>"

    def coerced_value(self) -> Any:
        """Return value coerced to the declared type."""
        import json as _json

        if self.value is None:
            return None
        if self.value_type == "number":
            try:
                return float(self.value) if "." in self.value else int(self.value)
            except (ValueError, TypeError):
                return self.value
        if self.value_type == "boolean":
            return self.value.lower() in ("true", "1", "yes")
        if self.value_type == "json":
            try:
                return _json.loads(self.value)
            except (ValueError, TypeError):
                return self.value
        return self.value  # string or secret — returned as-is

    def to_dict(self, reveal_secret: bool = False) -> dict[str, Any]:
        v = "***" if self.value_type == "secret" and not reveal_secret else self.value
        return {
            "id": self.id,
            "owner_type": self.owner_type,
            "owner_id": self.owner_id,
            "name": self.name,
            "value": v,
            "value_type": self.value_type,
            "description": self.description,
            "is_required": self.is_required,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ParameterValue(db.Model):
    """A runtime override for a named property on an execution object.

    run_type  one of: "pipeline_run" | "stage_run" | "task_run"
    run_id    ID of the owning run record.

    These are set when a run is created (e.g. via the trigger API) and are
    resolved *in preference to* any design-time property of the same name.
    """

    __tablename__ = "parameter_values"

    id = db.Column(db.String(64), primary_key=True)
    run_type = db.Column(db.String(32), nullable=False, index=True)
    run_id = db.Column(db.String(64), nullable=False, index=True)
    name = db.Column(db.String(256), nullable=False)
    value = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (db.UniqueConstraint("run_type", "run_id", "name", name="uq_param_run_name"),)

    def __repr__(self) -> str:
        return f"<ParameterValue {self.run_type}/{self.run_id} {self.name!r}>"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "run_type": self.run_type,
            "run_id": self.run_id,
            "name": self.name,
            "value": self.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
