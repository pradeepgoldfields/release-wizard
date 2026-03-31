"""Business logic for the Product domain — creation, retrieval, and deletion.

Route handlers must not construct model objects directly; they delegate here
so business rules are testable in isolation.
"""

from __future__ import annotations

from app.extensions import db
from app.models.application import ApplicationArtifact
from app.models.product import Product
from app.services.id_service import resource_id


def create_product(name: str, description: str | None = None) -> Product:
    """Create and persist a new Product.

    Args:
        name: Human-readable product name (must be unique within the platform).
        description: Optional free-text description.

    Returns:
        The newly created and committed Product instance.
    """
    product = Product(id=resource_id("prod"), name=name, description=description)
    db.session.add(product)
    db.session.commit()
    return product


def create_application(
    product_id: str,
    name: str,
    artifact_type: str = "container",
    repository_url: str | None = None,
    build_version: str | None = None,
    compliance_rating: str | None = None,
    description: str | None = None,
) -> ApplicationArtifact:
    """Create an ApplicationArtifact under a Product."""
    artifact = ApplicationArtifact(
        id=resource_id("app"),
        product_id=product_id,
        name=name,
        artifact_type=artifact_type,
        repository_url=repository_url,
        build_version=build_version,
        compliance_rating=compliance_rating,
        description=description,
    )
    db.session.add(artifact)
    db.session.commit()
    return artifact
