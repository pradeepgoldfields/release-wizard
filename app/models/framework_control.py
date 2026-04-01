"""Framework control configuration — enables per-framework control customisation.

Each row represents one control (ISAE/ACF) with an enabled flag and optional
overrides. Custom controls (is_builtin=False) are user-added.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.extensions import db


class FrameworkControl(db.Model):
    __tablename__ = "framework_controls"

    id = db.Column(db.String(64), primary_key=True)  # e.g. "CC1.1" or "ACF-GOV-1"
    framework = db.Column(db.String(16), nullable=False)  # "isae" or "acf"
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    is_builtin = db.Column(db.Boolean, default=True, nullable=False)

    # Overrideable fields (null = use built-in default)
    title = db.Column(db.String(256), nullable=True)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(64), nullable=True)  # CC1 / Governance / etc.
    category_label = db.Column(db.String(128), nullable=True)
    task_types_json = db.Column(db.Text, nullable=True)  # JSON list
    dimension_keys_json = db.Column(db.Text, nullable=True)  # JSON list
    evidence_keywords_json = db.Column(db.Text, nullable=True)  # JSON list
    weight = db.Column(db.Integer, nullable=True)

    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    updated_by = db.Column(db.String(128), nullable=True)

    def to_dict(self) -> dict:
        import json

        return {
            "id": self.id,
            "framework": self.framework,
            "enabled": self.enabled,
            "is_builtin": self.is_builtin,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "category_label": self.category_label,
            "task_types": json.loads(self.task_types_json) if self.task_types_json else None,
            "dimension_keys": json.loads(self.dimension_keys_json)
            if self.dimension_keys_json
            else None,
            "evidence_keywords": json.loads(self.evidence_keywords_json)
            if self.evidence_keywords_json
            else None,
            "weight": self.weight,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": self.updated_by,
        }
