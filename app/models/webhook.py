"""Webhook model — inbound trigger endpoints for pipeline runs."""

from __future__ import annotations

from datetime import UTC, datetime

from app.extensions import db


class Webhook(db.Model):
    __tablename__ = "webhooks"

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    pipeline_id = db.Column(
        db.String(64), db.ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    # secret token used to authenticate inbound requests (plain text, user-supplied)
    token = db.Column(db.String(256), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_by = db.Column(db.String(128), nullable=False, default="system")
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    pipeline = db.relationship("Pipeline", backref=db.backref("webhooks", lazy="dynamic"))
    deliveries = db.relationship(
        "WebhookDelivery", backref="webhook", lazy="dynamic", cascade="all,delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "pipeline_id": self.pipeline_id,
            "description": self.description,
            "is_active": self.is_active,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WebhookDelivery(db.Model):
    """Records each inbound webhook call and the pipeline run it triggered."""

    __tablename__ = "webhook_deliveries"

    id = db.Column(db.String(64), primary_key=True)
    webhook_id = db.Column(
        db.String(64), db.ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_run_id = db.Column(
        db.String(64), db.ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True
    )
    # JSON-encoded inbound payload
    payload = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="triggered")
    triggered_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "webhook_id": self.webhook_id,
            "pipeline_run_id": self.pipeline_run_id,
            "payload": self.payload,
            "status": self.status,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
        }
