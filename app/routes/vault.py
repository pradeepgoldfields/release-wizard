"""Secrets vault API endpoints."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models.vault import VaultSecret
from app.services.id_service import resource_id
from app.services.vault_service import can_access, decrypt, encrypt

vault_bp = Blueprint("vault", __name__, url_prefix="/api/v1/vault")


def _require_vault_write():
    """Require vault:create permission (or system-administrator role)."""
    user = getattr(g, "current_user", None)
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    from app.services.authz_service import get_permissions_for_user  # noqa: PLC0415

    perms = get_permissions_for_user(user.id, "organization")
    if "vault:create" not in perms and "vault:delete" not in perms:
        return jsonify({"error": "Admin required"}), 403
    return None


def _current_username() -> str:
    user = getattr(g, "current_user", None)
    return user.username if user else "system"


def _is_admin() -> bool:
    user = getattr(g, "current_user", None)
    if not user:
        return False
    from app.services.authz_service import get_permissions_for_user  # noqa: PLC0415

    perms = get_permissions_for_user(user.id, "organization")
    return "vault:reveal" in perms or "vault:create" in perms


@vault_bp.get("")
def list_secrets():
    """List all secrets (values redacted)."""
    secrets = VaultSecret.query.order_by(VaultSecret.name).all()
    username = _current_username()
    admin = _is_admin()
    result = []
    for s in secrets:
        if can_access(s, username, admin):
            result.append(s.to_dict())
    return jsonify(result)


@vault_bp.post("")
def create_secret():
    """Create a new secret."""
    err = _require_vault_write()
    if err:
        return err
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    value = (data.get("value") or "").strip()
    if not name or not value:
        return jsonify({"error": "name and value are required"}), 400
    if VaultSecret.query.filter_by(name=name).first():
        return jsonify({"error": f"Secret '{name}' already exists"}), 409
    secret = VaultSecret(
        id=resource_id("sec"),
        name=name,
        description=data.get("description", ""),
        ciphertext=encrypt(value),
        allowed_users=data.get("allowed_users", "*"),
        created_by=_current_username(),
    )
    db.session.add(secret)
    db.session.commit()
    return jsonify(secret.to_dict()), 201


@vault_bp.get("/<secret_id>")
def get_secret(secret_id: str):
    """Get secret metadata (no value)."""
    secret = db.get_or_404(VaultSecret, secret_id)
    username = _current_username()
    if not can_access(secret, username, _is_admin()):
        return jsonify({"error": "Access denied"}), 403
    return jsonify(secret.to_dict())


@vault_bp.post("/<secret_id>/reveal")
def reveal_secret(secret_id: str):
    """Reveal the decrypted secret value."""
    secret = db.get_or_404(VaultSecret, secret_id)
    username = _current_username()
    if not can_access(secret, username, _is_admin()):
        return jsonify({"error": "Access denied"}), 403
    try:
        value = decrypt(secret.ciphertext)
    except Exception:
        return jsonify({"error": "Failed to decrypt secret"}), 500
    return jsonify({"id": secret.id, "name": secret.name, "value": value})


@vault_bp.put("/<secret_id>")
def update_secret(secret_id: str):
    """Update a secret's value or metadata."""
    err = _require_vault_write()
    if err:
        return err
    secret = db.get_or_404(VaultSecret, secret_id)
    data = request.get_json(force=True) or {}
    if "value" in data and data["value"]:
        secret.ciphertext = encrypt(data["value"])
    if "description" in data:
        secret.description = data["description"]
    if "allowed_users" in data:
        secret.allowed_users = data["allowed_users"]
    if "name" in data and data["name"]:
        secret.name = data["name"]
    db.session.commit()
    return jsonify(secret.to_dict())


@vault_bp.delete("/<secret_id>")
def delete_secret(secret_id: str):
    """Delete a secret."""
    err = _require_vault_write()
    if err:
        return err
    secret = db.get_or_404(VaultSecret, secret_id)
    db.session.delete(secret)
    db.session.commit()
    return jsonify({"deleted": secret_id})
