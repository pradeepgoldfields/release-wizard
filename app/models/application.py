"""ApplicationArtifact domain model — a deployable software artifact within a product."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.enums import ArtifactType
from app.extensions import db


class ApplicationArtifact(db.Model):
    """A deployable application artifact (container image, library, or package).

    An artifact represents a named application component within a product.
    Multiple build versions of the same artifact are tracked via the
    ``build_version`` field, making each (name, build_version) pair a unique
    entry in the application dictionary.
    """

    __tablename__ = "application_artifacts"

    id = db.Column(db.String(64), primary_key=True)
    product_id = db.Column(db.String(64), db.ForeignKey("products.id"), nullable=False)
    name = db.Column(db.String(256), nullable=False)
    artifact_type = db.Column(db.String(64), default=ArtifactType.CONTAINER)
    repository_url = db.Column(db.String(512))
    # Application dictionary fields
    build_version = db.Column(db.String(128))  # e.g. "1.4.2", "main-abc123"
    compliance_rating = db.Column(db.String(32))  # Non-Compliant, Bronze, Silver, Gold, Platinum
    description = db.Column(db.Text)
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
            "build_version": self.build_version,
            "compliance_rating": self.compliance_rating or "Non-Compliant",
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
