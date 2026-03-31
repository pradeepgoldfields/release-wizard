"""Platform settings — key/value store for runtime-configurable settings."""

from __future__ import annotations

from datetime import UTC, datetime

from app.extensions import db


class PlatformSetting(db.Model):
    """A single runtime-configurable platform setting."""

    __tablename__ = "platform_settings"

    key = db.Column(db.String(128), primary_key=True)
    value = db.Column(db.Text, nullable=True)
    is_secret = db.Column(db.Boolean, default=False)
    updated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    def to_dict(self, reveal: bool = False) -> dict:
        return {
            "key": self.key,
            "value": ("***" if self.is_secret and not reveal else self.value),
            "is_secret": self.is_secret,
            "is_set": bool(self.value),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
