"""Zero-trust authorization: every request is checked against role bindings."""

from datetime import UTC, datetime

from app.extensions import db
from app.models.auth import Role, RoleBinding, User


def get_permissions_for_user(user_id: str, scope: str) -> set[str]:
    """
    Collect all permissions the user has at the given scope (or its parent scopes).
    Scope hierarchy: organization > product:{id} > environment:{id}
    """
    now = datetime.now(UTC)

    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        return set()

    # Collect principals: the user + all their groups
    principal_user_ids = {user.id}
    group_ids = {g.id for g in user.groups}

    # Build a list of scopes to check (most specific → least specific)
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
        # Skip expired JIT bindings
        if binding.expires_at and binding.expires_at < now:
            continue
        role = db.session.get(Role, binding.role_id)
        if role:
            permissions.update(role.permission_list)

    return permissions


def authorize(user_id: str, action: str, scope: str) -> bool:
    """Returns True if the user has the given permission at the scope."""
    permissions = get_permissions_for_user(user_id, scope)
    # Wildcard support: "release.*" grants "release.create", "release.delete" etc.
    resource = action.split(".")[0]
    return action in permissions or f"{resource}.*" in permissions


def _expand_scope(scope: str) -> list[str]:
    """Returns a list of scopes from most specific to least specific."""
    scopes = [scope, "organization"]
    # e.g. "environment:prod" also inherits from "product:{id}" if linked
    return list(dict.fromkeys(scopes))  # deduplicate preserving order
