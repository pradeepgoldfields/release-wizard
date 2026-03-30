"""Product domain model — top-level grouping for releases, pipelines, and applications."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions import db


class Product(db.Model):
    """A software product that owns releases, pipelines, and applications."""

    __tablename__ = "products"

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    releases = db.relationship("Release", back_populates="product", cascade="all, delete-orphan")
    pipelines = db.relationship("Pipeline", back_populates="product", cascade="all, delete-orphan")
    environments = db.relationship(
        "Environment",
        secondary="product_environments",
        back_populates="products",
    )
    applications = db.relationship(
        "ApplicationArtifact", back_populates="product", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id!r} name={self.name!r}>"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
