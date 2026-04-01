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
from app.routes._authz import current_user_id, get_visible_products, require_product_access
from app.services import cache_service
from app.services.product_service import create_application, create_product
from app.utils import paginate

products_bp = Blueprint("products", __name__, url_prefix="/api/v1/products")

_CACHE_KEY = "products:list"


@products_bp.get("")
def list_products():
    """Return products visible to the current user, ordered by name."""
    uid = current_user_id()
    visible = get_visible_products(uid) if uid else set()

    query = Product.query.order_by(Product.name)
    if visible is not None:
        # Restrict to explicitly granted product IDs
        if not visible:
            return jsonify({"items": [], "meta": {"total": 0, "limit": 50, "offset": 0}})
        query = query.filter(Product.id.in_(visible))

    items, meta = paginate(query)
    data = [p.to_dict() for p in items]
    return jsonify({"items": data, "meta": meta})


@products_bp.post("")
def create_product_endpoint():
    """Create a new product. Requires products:create at org scope."""
    uid = current_user_id()
    if uid is None:
        return jsonify({"error": "Authentication required"}), 401
    from app.services.authz_service import get_permissions_for_user  # noqa: PLC0415
    perms = get_permissions_for_user(uid, "organization")
    if "products:create" not in perms:
        return jsonify({"error": "Access denied", "code": "FORBIDDEN"}), 403

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
    uid = current_user_id()
    err = require_product_access(uid, product_id, "products:view")
    if err:
        return err
    product = db.get_or_404(Product, product_id)
    return jsonify(product.to_dict())


@products_bp.put("/<product_id>")
def update_product(product_id: str):
    """Update mutable product fields. Requires products:edit."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "products:edit")
    if err:
        return err
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
    """Permanently delete a product. Requires products:delete."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "products:delete")
    if err:
        return err
    product = db.get_or_404(Product, product_id)
    db.session.delete(product)
    db.session.commit()
    cache_service.invalidate(_CACHE_KEY)
    return "", 204


# ── Applications ──────────────────────────────────────────────────────────────


@products_bp.get("/<product_id>/applications")
def list_applications(product_id: str):
    """Return applications under a product. Requires applications:view."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "applications:view")
    if err:
        return err
    apps = ApplicationArtifact.query.filter_by(product_id=product_id).all()
    return jsonify([a.to_dict() for a in apps])


@products_bp.post("/<product_id>/applications")
def create_application_endpoint(product_id: str):
    """Register an application. Requires applications:create."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "applications:create")
    if err:
        return err
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    artifact = create_application(
        product_id=product_id,
        name=name,
        artifact_type=data.get("artifact_type", "container"),
        repository_url=data.get("repository_url"),
        build_version=data.get("build_version"),
        compliance_rating=data.get("compliance_rating"),
        description=data.get("description"),
    )
    return jsonify(artifact.to_dict()), 201


@products_bp.get("/<product_id>/applications/<app_id>")
def get_application(product_id: str, app_id: str):
    """Return a single application. Requires applications:view."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "applications:view")
    if err:
        return err
    artifact = db.get_or_404(ApplicationArtifact, app_id)
    return jsonify(artifact.to_dict())


@products_bp.put("/<product_id>/applications/<app_id>")
def update_application(product_id: str, app_id: str):
    """Update an application. Requires applications:edit."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "applications:edit")
    if err:
        return err
    artifact = db.get_or_404(ApplicationArtifact, app_id)
    data = request.get_json(silent=True) or {}
    for field in (
        "name",
        "artifact_type",
        "repository_url",
        "build_version",
        "compliance_rating",
        "description",
    ):
        if field in data:
            setattr(
                artifact,
                field,
                data[field] or None if field != "name" else (data[field] or artifact.name),
            )
    db.session.commit()
    return jsonify(artifact.to_dict())


@products_bp.delete("/<product_id>/applications/<app_id>")
def delete_application(product_id: str, app_id: str):
    """Delete an application. Requires applications:delete."""
    uid = current_user_id()
    err = require_product_access(uid, product_id, "applications:delete")
    if err:
        return err
    artifact = db.get_or_404(ApplicationArtifact, app_id)
    db.session.delete(artifact)
    db.session.commit()
    return "", 204
