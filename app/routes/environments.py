"""HTTP handlers for top-level Environment resources and product attachment."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.environment import Environment
from app.models.product import Product
from app.services import cache_service
from app.services.id_service import resource_id

environments_bp = Blueprint("environments", __name__, url_prefix="/api/v1")

_CACHE_KEY = "environments:list"


# ── Top-level CRUD ────────────────────────────────────────────────────────────


@environments_bp.get("/environments")
def list_environments():
    """Return all environments ordered by order then name."""
    cached = cache_service.get(_CACHE_KEY)
    if cached is not None:
        return jsonify(cached)
    envs = Environment.query.order_by(Environment.order, Environment.name).all()
    data = [e.to_dict() for e in envs]
    cache_service.set(_CACHE_KEY, data, ttl=30)
    return jsonify(data)


@environments_bp.post("/environments")
def create_environment():
    """Create a new top-level environment.

    Required body: ``name``
    Optional: ``env_type``, ``order``, ``description``
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    env = Environment(
        id=resource_id("env"),
        name=name,
        env_type=data.get("env_type", "custom"),
        order=int(data.get("order", 0)),
        description=data.get("description"),
    )
    db.session.add(env)
    db.session.commit()
    cache_service.invalidate(_CACHE_KEY)
    return jsonify(env.to_dict()), 201


@environments_bp.get("/environments/<env_id>")
def get_environment(env_id: str):
    """Return a single environment by ID."""
    env = db.get_or_404(Environment, env_id)
    return jsonify(env.to_dict())


@environments_bp.put("/environments/<env_id>")
def update_environment(env_id: str):
    """Update an environment's name, type, order, or description."""
    env = db.get_or_404(Environment, env_id)
    data = request.get_json(silent=True) or {}
    if "name" in data:
        env.name = (data["name"] or "").strip() or env.name
    if "env_type" in data:
        env.env_type = data["env_type"]
    if "order" in data:
        env.order = int(data["order"])
    if "description" in data:
        env.description = data["description"] or None
    db.session.commit()
    cache_service.invalidate(_CACHE_KEY)
    return jsonify(env.to_dict())


@environments_bp.delete("/environments/<env_id>")
def delete_environment(env_id: str):
    """Delete an environment."""
    env = db.get_or_404(Environment, env_id)
    db.session.delete(env)
    db.session.commit()
    cache_service.invalidate(_CACHE_KEY)
    return "", 204


# ── Product ↔ Environment attachment ─────────────────────────────────────────


@environments_bp.get("/products/<product_id>/environments")
def list_product_environments(product_id: str):
    """Return all environments attached to a product."""
    product = db.get_or_404(Product, product_id)
    envs = sorted(product.environments, key=lambda e: (e.order, e.name))
    return jsonify([e.to_dict() for e in envs])


@environments_bp.post("/products/<product_id>/environments")
def attach_environment(product_id: str):
    """Attach an existing environment to a product.

    Required body: ``environment_id``
    """
    product = db.get_or_404(Product, product_id)
    data = request.get_json(silent=True) or {}
    env_id = (data.get("environment_id") or "").strip()
    if not env_id:
        return jsonify({"error": "environment_id is required"}), 400
    env = db.get_or_404(Environment, env_id)
    if env not in product.environments:
        product.environments.append(env)
        db.session.commit()
    return jsonify({"product_id": product_id, "environment_id": env_id, "status": "attached"}), 200


@environments_bp.delete("/products/<product_id>/environments/<env_id>")
def detach_environment(product_id: str, env_id: str):
    """Detach an environment from a product (does not delete the environment)."""
    product = db.get_or_404(Product, product_id)
    env = db.get_or_404(Environment, env_id)
    if env in product.environments:
        product.environments.remove(env)
        db.session.commit()
    return "", 204
