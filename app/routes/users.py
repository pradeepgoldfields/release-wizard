"""User and Group management endpoints.

Provides CRUD for Users (with persona assignment) and their role bindings.
All routes are under ``/api/v1/users`` and ``/api/v1/groups``.
"""

from __future__ import annotations

import csv
import io
import json

import bcrypt
from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.auth import Group, Role, RoleBinding, User
from app.services.id_service import resource_id
from app.services.user_service import (
    add_scoped_role,
    create_user,
    get_effective_permissions,
    update_user_persona,
)

users_bp = Blueprint("users", __name__)


# ── Users ─────────────────────────────────────────────────────────────────────


@users_bp.get("/api/v1/users")
def list_users():
    """Return all platform users."""
    users = User.query.order_by(User.username).all()
    return jsonify([u.to_dict() for u in users])


@users_bp.post("/api/v1/users")
def create_user_endpoint():
    """Create a new user with a persona.

    Required body fields: ``username``
    Optional: ``email``, ``display_name``, ``persona``, ``ldap_dn``
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"error": "username is required"}), 400

    existing = User.query.filter_by(username=username).first()
    if existing:
        return jsonify({"error": f"Username '{username}' already exists"}), 409

    user = create_user(
        username=username,
        email=data.get("email"),
        display_name=data.get("display_name"),
        persona=data.get("persona", "ReadOnly"),
        ldap_dn=data.get("ldap_dn"),
    )
    # Optionally set a local password at creation time
    password = data.get("password")
    if password:
        user.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        db.session.commit()
    return jsonify(user.to_dict()), 201


@users_bp.get("/api/v1/users/<user_id>")
def get_user(user_id: str):
    """Return a single user by ID."""
    user = db.get_or_404(User, user_id)
    return jsonify(user.to_dict())


@users_bp.patch("/api/v1/users/<user_id>")
def update_user(user_id: str):
    """Update mutable user fields (display_name, email, is_active, persona)."""
    user = db.get_or_404(User, user_id)
    data = request.get_json(silent=True) or {}

    if "display_name" in data:
        user.display_name = data["display_name"]
    if "email" in data:
        user.email = data["email"]
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    if "persona" in data:
        user = update_user_persona(user_id, data["persona"])
    else:
        db.session.commit()

    return jsonify(user.to_dict())


@users_bp.patch("/api/v1/users/<user_id>/password")
def change_password(user_id: str):
    """Set or change a user's local password.

    Required body: ``password`` (new password, min 6 chars)
    """
    user = db.get_or_404(User, user_id)
    data = request.get_json(silent=True) or {}
    password = (data.get("password") or "").strip()
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    user.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db.session.commit()
    return jsonify({"message": "Password updated"})


@users_bp.delete("/api/v1/users/<user_id>")
def delete_user(user_id: str):
    """Permanently delete a user and all their role bindings."""
    user = db.get_or_404(User, user_id)
    db.session.delete(user)
    db.session.commit()
    return "", 204


@users_bp.post("/api/v1/users/import")
def bulk_import_users():
    """Bulk-import users from JSON or CSV.

    Accepts either:
      - ``application/json``: list of user objects
      - ``text/csv``:  CSV with header row (username, email, display_name, persona, password)

    Returns a summary: ``{"created": N, "skipped": N, "errors": [...]}``
    """
    content_type = request.content_type or ""
    records: list[dict] = []

    if "application/json" in content_type:
        body = request.get_json(silent=True)
        if not isinstance(body, list):
            return jsonify({"error": "Expected a JSON array of user objects"}), 400
        records = body
    elif "text/csv" in content_type or "text/plain" in content_type:
        text = request.get_data(as_text=True)
        reader = csv.DictReader(io.StringIO(text))
        records = [row for row in reader]
    else:
        # Try JSON first, then CSV
        body = request.get_json(silent=True)
        if isinstance(body, list):
            records = body
        else:
            text = request.get_data(as_text=True)
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    records = parsed
            except (ValueError, TypeError):
                pass
            if not records:
                try:
                    reader = csv.DictReader(io.StringIO(text))
                    records = [row for row in reader]
                except Exception:
                    pass

    if not records:
        return jsonify(
            {"error": "No records parsed — send a JSON array or CSV with header row"}
        ), 400

    created = 0
    skipped = 0
    errors: list[str] = []

    for i, row in enumerate(records):
        username = (row.get("username") or "").strip()
        if not username:
            errors.append(f"Row {i + 1}: missing username")
            continue

        existing = User.query.filter_by(username=username).first()
        if existing:
            skipped += 1
            continue

        try:
            user = create_user(
                username=username,
                email=(row.get("email") or "").strip() or None,
                display_name=(row.get("display_name") or row.get("displayName") or "").strip()
                or None,
                persona=(row.get("persona") or "ReadOnly").strip(),
                ldap_dn=(row.get("ldap_dn") or row.get("ldapDn") or "").strip() or None,
            )
            password = (row.get("password") or "").strip()
            if password:
                user.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                db.session.commit()
            created += 1
        except Exception as exc:
            errors.append(f"Row {i + 1} ({username}): {exc}")

    return jsonify({"created": created, "skipped": skipped, "errors": errors})


# ── User role bindings ────────────────────────────────────────────────────────


@users_bp.get("/api/v1/users/<user_id>/bindings")
def list_user_bindings(user_id: str):
    """List all role bindings for a user."""
    db.get_or_404(User, user_id)
    bindings = RoleBinding.query.filter_by(user_id=user_id).all()
    return jsonify([b.to_dict() for b in bindings])


@users_bp.post("/api/v1/users/<user_id>/bindings")
def add_user_binding(user_id: str):
    """Grant a user a scoped role binding.

    Required body: ``role_id``, ``scope``
    Optional: ``expires_at`` (ISO 8601)
    """
    data = request.get_json(silent=True) or {}
    role_id = (data.get("role_id") or "").strip()
    scope = (data.get("scope") or "").strip()
    if not role_id:
        return jsonify({"error": "role_id is required"}), 400
    if not scope:
        return jsonify({"error": "scope is required"}), 400

    expires_at = None
    if data.get("expires_at"):
        from datetime import datetime

        expires_at = datetime.fromisoformat(data["expires_at"])

    binding = add_scoped_role(user_id, role_id, scope, expires_at)
    return jsonify(binding.to_dict()), 201


@users_bp.delete("/api/v1/users/<user_id>/bindings/<binding_id>")
def remove_user_binding(user_id: str, binding_id: str):
    """Remove a specific role binding from a user."""
    binding = RoleBinding.query.filter_by(id=binding_id, user_id=user_id).first_or_404()
    db.session.delete(binding)
    db.session.commit()
    return "", 204


@users_bp.get("/api/v1/users/<user_id>/permissions")
def get_user_permissions(user_id: str):
    """Return the effective permissions for a user at a given scope.

    Query param: ``scope`` (default: ``organization``)
    """
    scope = request.args.get("scope", "organization")
    permissions = get_effective_permissions(user_id, scope)
    return jsonify({"user_id": user_id, "scope": scope, "permissions": permissions})


# ── Groups ────────────────────────────────────────────────────────────────────


@users_bp.get("/api/v1/groups")
def list_groups():
    """Return all groups."""
    groups = Group.query.order_by(Group.name).all()
    return jsonify([g.to_dict() for g in groups])


@users_bp.post("/api/v1/groups")
def create_group():
    """Create a new group.

    Required body: ``name``
    Optional: ``description``, ``ldap_dn``, ``git_source``
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    group = Group(
        id=resource_id("grp"),
        name=name,
        description=data.get("description"),
        ldap_dn=data.get("ldap_dn"),
        git_source=data.get("git_source"),
    )
    db.session.add(group)
    db.session.commit()
    return jsonify(group.to_dict()), 201


@users_bp.get("/api/v1/groups/<group_id>")
def get_group(group_id: str):
    """Return a single group by ID."""
    group = db.get_or_404(Group, group_id)
    return jsonify(group.to_dict())


@users_bp.patch("/api/v1/groups/<group_id>")
def update_group(group_id: str):
    """Update a group's name or description."""
    group = db.get_or_404(Group, group_id)
    data = request.get_json(silent=True) or {}
    if "name" in data:
        group.name = (data["name"] or "").strip() or group.name
    if "description" in data:
        group.description = data["description"] or None
    db.session.commit()
    return jsonify(group.to_dict())


@users_bp.delete("/api/v1/groups/<group_id>")
def delete_group(group_id: str):
    """Delete a group."""
    group = db.get_or_404(Group, group_id)
    db.session.delete(group)
    db.session.commit()
    return "", 204


@users_bp.post("/api/v1/groups/<group_id>/members/<user_id>")
def add_group_member(group_id: str, user_id: str):
    """Add a user to a group."""
    group = db.get_or_404(Group, group_id)
    user = db.get_or_404(User, user_id)
    if user not in group.users:
        group.users.append(user)
        db.session.commit()
    return jsonify({"group_id": group_id, "user_id": user_id, "status": "added"}), 200


@users_bp.delete("/api/v1/groups/<group_id>/members/<user_id>")
def remove_group_member(group_id: str, user_id: str):
    """Remove a user from a group."""
    group = db.get_or_404(Group, group_id)
    user = db.get_or_404(User, user_id)
    if user in group.users:
        group.users.remove(user)
        db.session.commit()
    return "", 204


# ── Roles ─────────────────────────────────────────────────────────────────────


@users_bp.get("/api/v1/roles")
def list_roles():
    """Return all defined roles."""
    roles = Role.query.order_by(Role.name).all()
    return jsonify([r.to_dict() for r in roles])


@users_bp.post("/api/v1/roles")
def create_role():
    """Create a custom role.

    Required body: ``name``, ``permissions`` (list of strings)
    Optional: ``description``
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    permissions = data.get("permissions", [])
    if not name:
        return jsonify({"error": "name is required"}), 400
    if not isinstance(permissions, list) or not permissions:
        return jsonify({"error": "permissions must be a non-empty list"}), 400

    role = Role(
        id=resource_id("role"),
        name=name,
        permissions=",".join(permissions),
        description=data.get("description"),
    )
    db.session.add(role)
    db.session.commit()
    return jsonify(role.to_dict()), 201


@users_bp.patch("/api/v1/roles/<role_id>")
def update_role(role_id: str):
    """Update a role's name, permissions, or description."""
    role = db.get_or_404(Role, role_id)
    data = request.get_json(silent=True) or {}
    if "name" in data:
        role.name = (data["name"] or "").strip() or role.name
    if "permissions" in data and isinstance(data["permissions"], list):
        role.permissions = ",".join(data["permissions"])
    if "description" in data:
        role.description = data["description"] or None
    db.session.commit()
    return jsonify(role.to_dict())


@users_bp.delete("/api/v1/roles/<role_id>")
def delete_role(role_id: str):
    """Delete a role. Fails if active bindings reference it."""
    role = db.get_or_404(Role, role_id)
    db.session.delete(role)
    db.session.commit()
    return "", 204


@users_bp.get("/api/v1/roles/<role_id>")
def get_role(role_id: str):
    """Return a single role by ID."""
    role = db.get_or_404(Role, role_id)
    return jsonify(role.to_dict())


# ── Scope-level RBAC matrix ───────────────────────────────────────────────────


@users_bp.get("/api/v1/rbac/bindings")
def list_scope_bindings():
    """Return all role bindings for a given resource scope.

    Query param: ``scope`` (required) — e.g. ``product:prod_xxx``

    Each binding is enriched with resolved ``user`` / ``group`` and ``role``
    objects so the frontend can render the permission matrix without extra calls.
    """
    scope = request.args.get("scope", "").strip()
    if not scope:
        return jsonify({"error": "scope query parameter is required"}), 400

    bindings = RoleBinding.query.filter_by(scope=scope).all()

    def _enrich(b: RoleBinding) -> dict:
        d = b.to_dict()
        if b.role:
            d["role"] = b.role.to_dict()
        if b.user:
            d["user"] = b.user.to_dict()
        if b.group:
            d["group"] = b.group.to_dict()
        return d

    return jsonify([_enrich(b) for b in bindings])


@users_bp.post("/api/v1/rbac/bindings")
def create_scope_binding():
    """Create a role binding for a user or group at a resource scope.

    Required body: ``role_id``, ``scope``
    One of: ``user_id`` or ``group_id``
    Optional: ``expires_at`` (ISO 8601)
    """
    data = request.get_json(silent=True) or {}
    role_id = (data.get("role_id") or "").strip()
    scope = (data.get("scope") or "").strip()
    user_id = (data.get("user_id") or "").strip() or None
    group_id = (data.get("group_id") or "").strip() or None

    if not role_id:
        return jsonify({"error": "role_id is required"}), 400
    if not scope:
        return jsonify({"error": "scope is required"}), 400
    if not user_id and not group_id:
        return jsonify({"error": "user_id or group_id is required"}), 400

    # Validate referenced objects exist
    db.get_or_404(Role, role_id)
    if user_id:
        db.get_or_404(User, user_id)
    if group_id:
        db.get_or_404(Group, group_id)

    expires_at = None
    if data.get("expires_at"):
        from datetime import datetime

        expires_at = datetime.fromisoformat(data["expires_at"])

    binding = RoleBinding(
        id=resource_id("rb"),
        role_id=role_id,
        user_id=user_id,
        group_id=group_id,
        scope=scope,
        expires_at=expires_at,
    )
    db.session.add(binding)
    db.session.commit()

    d = binding.to_dict()
    if binding.role:
        d["role"] = binding.role.to_dict()
    if binding.user:
        d["user"] = binding.user.to_dict()
    if binding.group:
        d["group"] = binding.group.to_dict()
    return jsonify(d), 201


@users_bp.delete("/api/v1/rbac/bindings/<binding_id>")
def delete_scope_binding(binding_id: str):
    """Remove a role binding by ID (any scope)."""
    binding = db.get_or_404(RoleBinding, binding_id)
    db.session.delete(binding)
    db.session.commit()
    return "", 204
