"""Compliance domain models — admission rules and the immutable audit event log."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import AuditDecision
from app.extensions import db


class ComplianceRule(db.Model):
    """Release admission rule: minimum rating required for a pipeline to join a release."""

    __tablename__ = "compliance_rules"

    id = db.Column(db.String(64), primary_key=True)
    description = db.Column(db.Text)
    scope = db.Column(db.String(256), nullable=False)  # environment:prod, product:api-service
    min_rating = db.Column(db.String(32), nullable=False)  # Platinum, Gold, Silver, Bronze
    is_active = db.Column(db.Boolean, default=True)
    git_sha = db.Column(db.String(64))  # SHA of the compliance-policies repo commit
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return (
            f"<ComplianceRule id={self.id!r} scope={self.scope!r} min_rating={self.min_rating!r}>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "scope": self.scope,
            "min_rating": self.min_rating,
            "is_active": self.is_active,
            "git_sha": self.git_sha,
        }


class AuditEvent(db.Model):
    """Immutable audit log entry — append-only, never updated."""

    __tablename__ = "audit_events"

    id = db.Column(db.String(64), primary_key=True)
    event_type = db.Column(db.String(128), nullable=False)  # release.created, gate.approved …
    actor = db.Column(db.String(128))  # username
    resource_type = db.Column(db.String(64))  # release, pipeline, environment …
    resource_id = db.Column(db.String(64))
    action = db.Column(db.String(128))
    decision = db.Column(db.String(16), default=AuditDecision.ALLOW)
    detail = db.Column(db.Text)  # JSON blob with extra context
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"<AuditEvent id={self.id!r} event_type={self.event_type!r} actor={self.actor!r}>"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "actor": self.actor,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "decision": self.decision,
            "detail": json.loads(self.detail) if self.detail else {},
            "timestamp": self.timestamp.isoformat(),
        }
