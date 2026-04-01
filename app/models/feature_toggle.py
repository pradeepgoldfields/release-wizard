"""FeatureToggle model — platform-wide feature flags."""

from __future__ import annotations

from datetime import UTC, datetime

from app.extensions import db


class FeatureToggle(db.Model):
    """A named boolean feature flag that can be turned on or off at runtime."""

    __tablename__ = "feature_toggles"

    id = db.Column(db.String(64), primary_key=True)
    key = db.Column(db.String(128), unique=True, nullable=False)
    label = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(64), default="general")
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "category": self.category,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
