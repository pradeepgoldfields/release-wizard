"""Release domain model — a versioned collection of pipelines ready for deployment."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions import db

# Association: a release has many pipelines
release_pipelines = db.Table(
    "release_pipelines",
    db.Column("release_id", db.String(64), db.ForeignKey("releases.id"), primary_key=True),
    db.Column("pipeline_id", db.String(64), db.ForeignKey("pipelines.id"), primary_key=True),
    db.Column("admission_status", db.String(16), default="pending"),  # passed, blocked
    db.Column("added_at", db.DateTime, default=lambda: datetime.now(UTC)),
)


class Release(db.Model):
    """A named, versioned release grouping pipelines for coordinated deployment."""

    __tablename__ = "releases"

    id = db.Column(db.String(64), primary_key=True)
    product_id = db.Column(db.String(64), db.ForeignKey("products.id"), nullable=False)
    name = db.Column(db.String(256), nullable=False)
    version = db.Column(db.String(64))
    description = db.Column(db.Text)
    definition_sha = db.Column(db.String(64))
    protected_segment_version = db.Column(db.Integer, default=0)
    created_by = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    product = db.relationship("Product", back_populates="releases")
    pipelines = db.relationship("Pipeline", secondary=release_pipelines, backref="releases")
    runs = db.relationship("ReleaseRun", back_populates="release", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Release id={self.id!r} name={self.name!r} version={self.version!r}>"

    def to_dict(self, include_pipelines: bool = False) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        data: dict[str, Any] = {
            "id": self.id,
            "product_id": self.product_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "definition_sha": self.definition_sha,
            "protected_segment_version": self.protected_segment_version,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_pipelines:
            data["pipelines"] = [p.to_dict() for p in self.pipelines]
        return data
