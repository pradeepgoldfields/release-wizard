"""Plugin domain models — extensible CI/CD integrations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions import db


class Plugin(db.Model):
    """A registered plugin (builtin or uploaded by user)."""

    __tablename__ = "plugins"

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    display_name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    version = db.Column(db.String(32), default="0.1.0")
    plugin_type = db.Column(db.String(32), default="integration")  # integration | custom
    category = db.Column(db.String(64))  # ci | cd | scm | notification
    icon = db.Column(db.String(8), default="🔌")  # emoji icon
    is_builtin = db.Column(db.Boolean, default=False)
    is_enabled = db.Column(db.Boolean, default=True)
    author = db.Column(db.String(128))
    homepage = db.Column(db.String(512))
    # JSON schema for the plugin's config fields
    config_schema = db.Column(db.Text, default="{}")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    configs = db.relationship("PluginConfig", back_populates="plugin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Plugin id={self.id!r} name={self.name!r}>"

    def to_dict(self, include_configs: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "plugin_type": self.plugin_type,
            "category": self.category,
            "icon": self.icon,
            "is_builtin": self.is_builtin,
            "is_enabled": self.is_enabled,
            "author": self.author,
            "homepage": self.homepage,
            "config_count": len(self.configs),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_configs:
            data["configs"] = [c.to_dict() for c in self.configs]
        return data


class PluginConfig(db.Model):
    """A named configuration instance for a plugin (e.g. 'prod-jenkins')."""

    __tablename__ = "plugin_configs"

    id = db.Column(db.String(64), primary_key=True)
    plugin_id = db.Column(db.String(64), db.ForeignKey("plugins.id"), nullable=False)
    config_name = db.Column(db.String(128), nullable=False)
    tool_url = db.Column(db.String(512))
    # Encrypted / hashed credentials stored as JSON string
    credentials = db.Column(db.Text, default="{}")
    extra_config = db.Column(db.Text, default="{}")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    plugin = db.relationship("Plugin", back_populates="configs")

    def __repr__(self) -> str:
        return f"<PluginConfig id={self.id!r} name={self.config_name!r}>"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "plugin_id": self.plugin_id,
            "config_name": self.config_name,
            "tool_url": self.tool_url,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
