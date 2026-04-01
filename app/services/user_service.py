"""Business logic for User and Group management."""

from __future__ import annotations

from app.extensions import db
from app.models.auth import Role, RoleBinding, User
from app.services.id_service import resource_id


def create_user(
    username: str,
    email: str | None = None,
    display_name: str | None = None,
    ldap_dn: str | None = None,
) -> User:
    """Create a new User.  Access is granted separately via role bindings.

    Args:
        username: Unique login name.
        email: Contact email address.
        display_name: Full name for display in the UI.
        ldap_dn: Optional LDAP distinguished name for directory sync.

    Returns:
        The newly created User.
    """
    user = User(
        id=resource_id("usr"),
        username=username,
        email=email,
        display_name=display_name,
        ldap_dn=ldap_dn,
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


def add_scoped_role(
    user_id: str,
    role_id: str,
    scope: str,
    expires_at=None,
) -> RoleBinding:
    """Grant a user a role at a specific resource scope.

    Args:
        user_id: Target user.
        role_id: Role to grant.
        scope: Resource scope string, e.g. ``product:api-service``.
        expires_at: Optional expiry for JIT access (datetime or None).

    Returns:
        The new RoleBinding.
    """
    db.get_or_404(User, user_id)
    db.get_or_404(Role, role_id)
    binding = RoleBinding(
        id=resource_id("rb"),
        role_id=role_id,
        user_id=user_id,
        scope=scope,
        expires_at=expires_at,
    )
    db.session.add(binding)
    db.session.commit()
    return binding


def get_effective_permissions(user_id: str, scope: str) -> list[str]:
    """Return all permissions a user has at the given scope (and parent scopes).

    Delegates to the authorisation service for the actual RBAC resolution.
    """
    from app.services.authz_service import get_permissions_for_user

    return sorted(get_permissions_for_user(user_id, scope))
