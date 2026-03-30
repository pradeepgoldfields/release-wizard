"""HTTP handlers for the Product and Application resources.

All business logic is delegated to :mod:`app.services.product_service`.
Route handlers are responsible only for request parsing, input validation,
and response serialisation.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.application import ApplicationArtifact
from app.models.product import Product
from app.services import cache_service
from app.services.product_service import create_application, create_product

products_bp = Blueprint("products", __name__, url_prefix="/api/v1/products")

_CACHE_KEY = "products:list"


@products_bp.get("")
def list_products():
    """Return all products ordered by name."""
    cached = cache_service.get(_CACHE_KEY)
    if cached is not None:
        return jsonify(cached)
    products = Product.query.order_by(Product.name).all()
    data = [p.to_dict() for p in products]
    cache_service.set(_CACHE_KEY, data, ttl=30)
    return jsonify(data)


@products_bp.post("")
def create_product_endpoint():
    """Create a new product.

    Required body: ``name``
    Optional: ``description``
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    product = create_product(name=name, description=data.get("description"))
    cache_service.invalidate(_CACHE_KEY)
    return jsonify(product.to_dict()), 201


@products_bp.get("/<product_id>")
def get_product(product_id: str):
    """Return a single product by ID."""
    product = db.get_or_404(Product, product_id)
    return jsonify(product.to_dict())


@products_bp.put("/<product_id>")
def update_product(product_id: str):
    """Update mutable product fields (name, description)."""
    product = db.get_or_404(Product, product_id)
    data = request.get_json(silent=True) or {}
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            return jsonify({"error": "name must not be blank"}), 400
        product.name = name
    if "description" in data:
        product.description = data["description"]
    db.session.commit()
    cache_service.invalidate(_CACHE_KEY)
    return jsonify(product.to_dict())


@products_bp.delete("/<product_id>")
def delete_product(product_id: str):
    """Permanently delete a product and all its child resources."""
    product = db.get_or_404(Product, product_id)
    db.session.delete(product)
    db.session.commit()
    cache_service.invalidate(_CACHE_KEY)
    return "", 204


# ── Applications ──────────────────────────────────────────────────────────────


@products_bp.get("/<product_id>/applications")
def list_applications(product_id: str):
    """Return all application artifacts registered under a product."""
    db.get_or_404(Product, product_id)
    apps = ApplicationArtifact.query.filter_by(product_id=product_id).all()
    return jsonify([a.to_dict() for a in apps])


@products_bp.post("/<product_id>/applications")
def create_application_endpoint(product_id: str):
    """Register an application artifact under a product.

    Required body: ``name``
    Optional: ``artifact_type``, ``repository_url``
    """
    db.get_or_404(Product, product_id)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    artifact = create_application(
        product_id=product_id,
        name=name,
        artifact_type=data.get("artifact_type", "container"),
        repository_url=data.get("repository_url"),
    )
    return jsonify(artifact.to_dict()), 201


@products_bp.put("/<product_id>/applications/<app_id>")
def update_application(product_id: str, app_id: str):
    """Update an application artifact's name, type, or repository URL."""
    db.get_or_404(Product, product_id)
    artifact = db.get_or_404(ApplicationArtifact, app_id)
    data = request.get_json(silent=True) or {}
    if "name" in data:
        artifact.name = (data["name"] or "").strip() or artifact.name
    if "artifact_type" in data:
        artifact.artifact_type = data["artifact_type"]
    if "repository_url" in data:
        artifact.repository_url = data["repository_url"] or None
    db.session.commit()
    return jsonify(artifact.to_dict())


@products_bp.delete("/<product_id>/applications/<app_id>")
def delete_application(product_id: str, app_id: str):
    """Delete an application artifact."""
    db.get_or_404(Product, product_id)
    artifact = db.get_or_404(ApplicationArtifact, app_id)
    db.session.delete(artifact)
    db.session.commit()
    return "", 204
