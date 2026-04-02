from __future__ import annotations

import json as _json
from datetime import UTC, datetime
from typing import Any

from app.extensions import db


class BacklogItem(db.Model):
    __tablename__ = "backlog_items"

    id = db.Column(db.String(64), primary_key=True)
    product_id = db.Column(db.String(64), db.ForeignKey("products.id"), nullable=False)

    title = db.Column(db.String(512), nullable=False)
    description = db.Column(db.Text, default="")
    item_type = db.Column(db.String(32), default="feature")
    status = db.Column(db.String(32), default="open")
    priority = db.Column(db.String(16), default="medium")
    effort = db.Column(db.Integer, default=0)

    assigned_to = db.Column(db.String(64), db.ForeignKey("users.id"), nullable=True)
    release_id = db.Column(db.String(64), db.ForeignKey("releases.id"), nullable=True)
    pipeline_id = db.Column(db.String(64), db.ForeignKey("pipelines.id"), nullable=True)

    labels = db.Column(db.Text, default="[]")
    acceptance_criteria = db.Column(db.Text, default="")
    notes = db.Column(db.Text, default="")

    created_by = db.Column(db.String(64), db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    product = db.relationship(
        "Product",
        foreign_keys=[product_id],
        backref=db.backref("backlog_items", lazy="dynamic"),
    )
    assignee = db.relationship("User", foreign_keys=[assigned_to])
    creator = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "title": self.title,
            "description": self.description or "",
            "item_type": self.item_type or "feature",
            "status": self.status or "open",
            "priority": self.priority or "medium",
            "effort": self.effort or 0,
            "assigned_to": self.assigned_to,
            "assignee_name": self.assignee.display_name if self.assignee else None,
            "release_id": self.release_id,
            "pipeline_id": self.pipeline_id,
            "labels": _json.loads(self.labels or "[]"),
            "acceptance_criteria": self.acceptance_criteria or "",
            "notes": self.notes or "",
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
