"""Pipeline Template — reusable pipeline definitions not tied to a product."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.extensions import db


class PipelineTemplate(db.Model):
    __tablename__ = "pipeline_templates"

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    kind = db.Column(db.String(16), default="ci")  # ci | cd
    category = db.Column(db.String(64))  # e.g. "Security", "Deploy", "Full Stack"
    tags = db.Column(db.String(512))  # comma-separated tags
    # Serialised pipeline structure: list of stage dicts (stages → tasks)
    definition_json = db.Column(db.Text, default="[]")
    created_by = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def to_dict(self, include_definition: bool = True) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "kind": self.kind,
            "category": self.category,
            "tags": [t.strip() for t in (self.tags or "").split(",") if t.strip()],
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_definition:
            try:
                d["stages"] = json.loads(self.definition_json or "[]")
            except Exception:
                d["stages"] = []
            d["stage_count"] = len(d["stages"])
            d["task_count"] = sum(len(s.get("tasks", [])) for s in d["stages"])
        else:
            try:
                stages = json.loads(self.definition_json or "[]")
            except Exception:
                stages = []
            d["stage_count"] = len(stages)
            d["task_count"] = sum(len(s.get("tasks", [])) for s in stages)
        return d
