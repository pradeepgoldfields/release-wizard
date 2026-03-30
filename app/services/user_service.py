"""Business logic for User and Group management, including persona assignment.

Personas are convenience templates: when a user is created with a persona,
the service automatically creates the appropriate default Role and RoleBindings
at the organisation scope so the user can get started immediately.
Explicit per-product/per-environment bindings are added via the RBAC API.
"""

from __future__ import annotations

from app.domain.enums import UserPersona
from app.extensions import db
from app.models.auth import Role, RoleBinding, User
from app.services.id_service import resource_id

# Default permissions bundled into each persona role
PERSONA_PERMISSIONS: dict[str, list[str]] = {
    UserPersona.PLATFORM_ADMIN: [
        "product.view",
        "product.manage",
        "release.view",
        "release.create",
        "release.edit",
        "release.delete",
        "release.deploy",
        "pipeline.view",
        "pipeline.edit",
        "pipeline.run",
        "environment.view",
        "environment.deploy",
        "environment.approve",
        "gate.view",
        "gate.approve",
        "gate.override",
        "user.view",
        "user.manage",
        "compliance.view",
        "compliance.manage",
    ],
    UserPersona.PRODUCT_OWNER: [
        "product.view",
        "product.manage",
        "release.view",
        "release.create",
        "release.edit",
        "release.delete",
        "pipeline.view",
        "pipeline.edit",
        "environment.view",
        "user.view",
        "compliance.view",
    ],
    UserPersona.RELEASE_MANAGER: [
        "release.view",
        "release.create",
        "release.edit",
        "release.deploy",
        "pipeline.view",
        "environment.view",
        "compliance.view",
    ],
    UserPersona.PIPELINE_AUTHOR: [
        "pipeline.view",
        "pipeline.edit",
        "pipeline.run",
        "release.view",
        "environment.view",
        "compliance.view",
    ],
    UserPersona.DEPLOYER: [
        "environment.view",
        "environment.deploy",
        "release.view",
        "pipeline.view",
        "compliance.view",
    ],
    UserPersona.APPROVER: [
        "gate.view",
        "gate.approve",
        "environment.view",
        "release.view",
        "compliance.view",
    ],
    UserPersona.COMPLIANCE_ADMIN: [
        "compliance.view",
        "compliance.manage",
        "product.view",
        "release.view",
        "pipeline.view",
        "environment.view",
        "user.view",
    ],
    UserPersona.READ_ONLY: [
        "product.view",
        "release.view",
        "pipeline.view",
        "environment.view",
        "compliance.view",
        "user.view",
    ],
}


def _ensure_persona_role(persona: str) -> Role:
    """Return the Role for a persona, creating it if it does not exist."""
    role_id = f"role_persona_{persona.lower().replace('-', '_')}"
    role = db.session.get(Role, role_id)
    if role is None:
        permissions = PERSONA_PERMISSIONS.get(persona, ["product.view"])
        role = Role(
            id=role_id,
            name=f"Persona: {persona}",
            permissions=",".join(permissions),
            description=f"Default role for the {persona} persona.",
        )
        db.session.add(role)
        db.session.flush()  # assign id without committing
    return role


def create_user(
    username: str,
    email: str | None = None,
    display_name: str | None = None,
    persona: str = UserPersona.READ_ONLY,
    ldap_dn: str | None = None,
) -> User:
    """Create a User and apply the default persona RoleBinding at org scope.

    Args:
        username: Unique login name.
        email: Contact email address.
        display_name: Full name for display in the UI.
        persona: One of :class:`~app.domain.enums.UserPersona`.
        ldap_dn: Optional LDAP distinguished name for directory sync.

    Returns:
        The newly created User.
    """
    role = _ensure_persona_role(persona)
    user = User(
        id=resource_id("usr"),
        username=username,
        email=email,
        display_name=display_name,
        persona=persona,
        ldap_dn=ldap_dn,
        is_active=True,
    )
    db.session.add(user)
    db.session.flush()

    binding = RoleBinding(
        id=resource_id("rb"),
        role_id=role.id,
        user_id=user.id,
        scope="organization",
    )
    db.session.add(binding)
    db.session.commit()
    return user


def update_user_persona(user_id: str, new_persona: str) -> User:
    """Change a user's persona and replace their organisation-scope binding.

    Scoped (product / environment) bindings are NOT touched.
    """
    user = db.get_or_404(User, user_id)
    new_role = _ensure_persona_role(new_persona)
    user.persona = new_persona

    # Remove existing org-scope binding for this user
    old_bindings = RoleBinding.query.filter_by(user_id=user_id, scope="organization").all()
    for binding in old_bindings:
        db.session.delete(binding)

    new_binding = RoleBinding(
        id=resource_id("rb"),
        role_id=new_role.id,
        user_id=user_id,
        scope="organization",
    )
    db.session.add(new_binding)
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
