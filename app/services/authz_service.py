"""Zero-trust authorization: every request is checked against role bindings."""

from __future__ import annotations

from datetime import UTC, datetime

from app.extensions import db
from app.models.auth import Role, RoleBinding, User

# ── Permission catalogue ───────────────────────────────────────────────────────
# Single source of truth for all permission groups.
# Each entry becomes a column-group in the Role Permissions matrix UI.
# To add a new resource: append a new dict here — the UI picks it up automatically.
#
# Format:
#   { "group": "<Display name>",
#     "perms": ["<resource>:<action>", ...],
#     "product_scoped": <True if this group belongs to product-child objects> }

PERMISSION_CATALOG: list[dict] = [
    {
        "group": "Products",
        "product_scoped": False,
        "perms": ["products:view", "products:create", "products:edit", "products:delete"],
    },
    {
        "group": "Applications",
        "product_scoped": True,
        "perms": [
            "applications:view",
            "applications:create",
            "applications:edit",
            "applications:delete",
        ],
    },
    {
        "group": "Backlog",
        "product_scoped": True,
        "perms": ["backlog:view", "backlog:create", "backlog:edit", "backlog:delete"],
    },
    {
        "group": "Pipelines",
        "product_scoped": True,
        "perms": [
            "pipelines:view",
            "pipelines:create",
            "pipelines:edit",
            "pipelines:delete",
            "pipelines:execute",
            "pipelines:run",
        ],
    },
    {
        "group": "Releases",
        "product_scoped": True,
        "perms": [
            "releases:view",
            "releases:create",
            "releases:edit",
            "releases:delete",
            "releases:execute",
            "releases:approve",
        ],
    },
    {
        "group": "Tasks",
        "product_scoped": True,
        "perms": ["tasks:view", "tasks:create", "tasks:edit", "tasks:delete", "tasks:execute"],
    },
    {
        "group": "Stages",
        "product_scoped": True,
        "perms": ["stages:view", "stages:create", "stages:edit", "stages:delete", "stages:execute"],
    },
    {
        "group": "Environments",
        "product_scoped": True,
        "perms": [
            "environments:view",
            "environments:create",
            "environments:edit",
            "environments:delete",
        ],
    },
    {
        "group": "Templates",
        "product_scoped": True,
        "perms": ["templates:view", "templates:create", "templates:edit", "templates:delete"],
    },
    {
        "group": "Webhooks",
        "product_scoped": True,
        "perms": ["webhooks:view", "webhooks:create", "webhooks:edit", "webhooks:delete"],
    },
    {
        "group": "Compliance",
        "product_scoped": True,
        "perms": ["compliance:view", "compliance:edit", "compliance:approve"],
    },
    {
        "group": "Plugins",
        "product_scoped": False,
        "perms": ["plugins:view", "plugins:install", "plugins:configure", "plugins:delete"],
    },
    {
        "group": "Agent Pools",
        "product_scoped": False,
        "perms": [
            "agent-pools:view",
            "agent-pools:create",
            "agent-pools:edit",
            "agent-pools:delete",
        ],
    },
    {
        "group": "Vault",
        "product_scoped": False,
        "perms": ["vault:view", "vault:create", "vault:reveal", "vault:delete"],
    },
    {
        "group": "App Dictionary",
        "product_scoped": False,
        "perms": ["app-dictionary:view", "app-dictionary:edit"],
    },
    {
        "group": "Monitoring",
        "product_scoped": False,
        "perms": ["monitoring:view", "monitoring:configure"],
    },
    {
        "group": "Users",
        "product_scoped": False,
        "perms": ["users:view", "users:create", "users:edit", "users:delete"],
    },
    {
        "group": "Groups",
        "product_scoped": False,
        "perms": ["groups:view", "groups:create", "groups:edit", "groups:delete"],
    },
    {
        "group": "Roles",
        "product_scoped": False,
        "perms": ["roles:view", "roles:create", "roles:edit", "roles:delete"],
    },
    {
        "group": "Permissions",
        "product_scoped": False,
        "perms": [
            "permissions:view",
            "permissions:grant",
            "permissions:revoke",
            "permissions:change",
        ],
    },
    {
        "group": "Global Variables",
        "product_scoped": False,
        "perms": ["global-vars:view", "global-vars:edit"],
    },
]

# Convenience sets derived from the catalog
ALL_PERMISSIONS: list[str] = [p for g in PERMISSION_CATALOG for p in g["perms"]]
PRODUCT_PERMISSIONS: list[str] = [
    p for g in PERMISSION_CATALOG if g["product_scoped"] for p in g["perms"]
]


def get_permissions_for_user(user_id: str, scope: str) -> set[str]:
    """
    Collect all permissions the user has at the given scope (and parent scopes).
    Scope hierarchy: organization > product:{id} > environment:{id}
    """
    now = datetime.now(UTC)

    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        return set()

    principal_user_ids = {user.id}
    group_ids = {g.id for g in user.groups}

    scopes_to_check = _expand_scope(scope)

    permissions: set[str] = set()

    bindings = RoleBinding.query.filter(
        RoleBinding.scope.in_(scopes_to_check),
        db.or_(
            RoleBinding.user_id.in_(principal_user_ids),
            RoleBinding.group_id.in_(group_ids),
        ),
    ).all()

    for binding in bindings:
        if binding.expires_at and binding.expires_at < now:
            continue
        role = db.session.get(Role, binding.role_id)
        if role:
            permissions.update(role.permission_list)

    return permissions


def authorize(user_id: str, action: str, scope: str) -> bool:
    """Returns True if the user has the given permission at the scope."""
    permissions = get_permissions_for_user(user_id, scope)
    resource = action.split(".")[0]
    return action in permissions or f"{resource}.*" in permissions


def get_visible_product_ids(user_id: str) -> set[str] | None:
    """Return the set of product IDs visible to the user.

    Returns ``None`` (meaning "all products") when the user has an
    organisation-scope binding — i.e. a platform-wide role.
    Returns an empty set if the user has no product access at all.
    """
    now = datetime.now(UTC)

    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        return set()

    principal_user_ids = {user.id}
    group_ids = {g.id for g in user.groups}

    bindings = RoleBinding.query.filter(
        db.or_(
            RoleBinding.user_id.in_(principal_user_ids),
            RoleBinding.group_id.in_(group_ids),
        )
    ).all()

    active_bindings = [b for b in bindings if not (b.expires_at and b.expires_at < now)]

    # Any organisation-scope binding means the user can see everything
    for b in active_bindings:
        if b.scope == "organization":
            role = db.session.get(Role, b.role_id)
            if role and role.permission_list:
                return None  # unrestricted

    # Collect explicit product-scoped binding product IDs
    product_ids: set[str] = set()
    for b in active_bindings:
        if b.scope.startswith("product:"):
            pid = b.scope.split(":", 1)[1]
            role = db.session.get(Role, b.role_id)
            if role and (
                "products:view" in role.permission_list
                or any(
                    p.startswith("applications:")
                    or p.startswith("pipelines:")
                    or p.startswith("releases:")
                    or p.startswith("tasks:")
                    or p.startswith("stages:")
                    for p in role.permission_list
                )
            ):
                product_ids.add(pid)

    return product_ids


def has_product_permission(user_id: str, product_id: str, permission: str) -> bool:
    """Return True if the user has ``permission`` for the given product."""
    perms = get_permissions_for_user(user_id, f"product:{product_id}")
    return permission in perms


def _expand_scope(scope: str) -> list[str]:
    """Returns a list of scopes from most specific to least specific."""
    scopes = [scope, "organization"]
    return list(dict.fromkeys(scopes))  # deduplicate preserving order
