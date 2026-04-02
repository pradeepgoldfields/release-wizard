"""Shared authorization helpers for route handlers.

Usage in a route::

    from app.routes._authz import current_user_id, get_visible_products, require_product_access

    @bp.get("")
    def list_products():
        uid = current_user_id()
        if uid is None:
            return jsonify({"error": "Authentication required"}), 401
        visible = get_visible_products(uid)
        # visible is None → all products; set → only those IDs

    @bp.get("/<product_id>/something")
    def get_something(product_id):
        uid = current_user_id()
        err = require_product_access(uid, product_id, "products:view")
        if err:
            return err
        ...
"""

from __future__ import annotations

from flask import g, jsonify

from app.services.authz_service import (
    get_visible_product_ids,
    has_product_permission,
)


def current_user_id() -> str | None:
    """Return the authenticated user's ID from request context, or None."""
    user = getattr(g, "current_user", None)
    return user.id if user else None


def get_visible_products(user_id: str) -> set[str] | None:
    """Return visible product IDs for the user, or None meaning all."""
    return get_visible_product_ids(user_id)


def require_product_access(user_id: str | None, product_id: str, permission: str = "products:view"):
    """Return a 401/403 JSON response if the user lacks access, else None.

    ``permission`` is checked at both org scope and product scope.
    """
    if user_id is None:
        return jsonify({"error": "Authentication required", "code": "UNAUTHENTICATED"}), 401

    visible = get_visible_product_ids(user_id)
    if visible is None:
        # Org-wide binding — always allowed
        return None
    if product_id not in visible:
        return jsonify({"error": "Access denied", "code": "FORBIDDEN"}), 403

    if not has_product_permission(user_id, product_id, permission):
        return jsonify({"error": "Access denied", "code": "FORBIDDEN"}), 403

    return None


def require_admin(user_id: str | None):
    """Return a 401/403 JSON response if the user is not an admin, else None."""
    if user_id is None:
        return jsonify({"error": "Authentication required", "code": "UNAUTHENTICATED"}), 401
    from app.models.auth import User  # noqa: PLC0415

    user = User.query.get(user_id)
    if not user or not user.is_admin:
        return jsonify({"error": "Admin access required", "code": "FORBIDDEN"}), 403
    return None
