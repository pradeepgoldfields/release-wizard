"""ApplicationArtifact domain model — a deployable software artifact within a product."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.enums import ArtifactType
from app.extensions import db


class ApplicationArtifact(db.Model):
    """A deployable application artifact (container image, library, or package)."""

    __tablename__ = "application_artifacts"

    id = db.Column(db.String(64), primary_key=True)
    product_id = db.Column(db.String(64), db.ForeignKey("products.id"), nullable=False)
    name = db.Column(db.String(256), nullable=False)
    artifact_type = db.Column(db.String(64), default=ArtifactType.CONTAINER)
    repository_url = db.Column(db.String(512))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    product = db.relationship("Product", back_populates="applications")
    pipelines = db.relationship("Pipeline", back_populates="application")

    def __repr__(self) -> str:
        return (
            f"<ApplicationArtifact id={self.id!r} name={self.name!r} type={self.artifact_type!r}>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "name": self.name,
            "artifact_type": self.artifact_type,
            "repository_url": self.repository_url,
        }
