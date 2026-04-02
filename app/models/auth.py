"""Authentication and authorisation domain models.

Implements a zero-trust RBAC model:
  User / Group  ──▶  RoleBinding  ──▶  Role  ──▶  permissions
Every RoleBinding is scoped to a resource (e.g. ``product:api-service``),
so permissions are never implicitly global.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions import db

# Many-to-many: User ↔ Group
user_groups = db.Table(
    "user_groups",
    db.Column("user_id", db.String(64), db.ForeignKey("users.id"), primary_key=True),
    db.Column("group_id", db.String(64), db.ForeignKey("groups.id"), primary_key=True),
)


class User(db.Model):
    """A platform user, optionally synced from an LDAP directory.

    Access is governed entirely by RoleBindings — there is no persona layer.
    """

    __tablename__ = "users"

    id = db.Column(db.String(64), primary_key=True)
    username = db.Column(db.String(128), unique=True, nullable=False)
    email = db.Column(db.String(256))
    display_name = db.Column(db.String(256))
    password_hash = db.Column(db.String(256))  # bcrypt hash; null = LDAP-only user
    ldap_dn = db.Column(db.String(512))
    is_active = db.Column(db.Boolean, default=True)
    is_builtin = db.Column(db.Boolean, default=False, nullable=False)  # protected system users
    must_change_password = db.Column(
        db.Boolean, default=False
    )  # force password reset on next login
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    groups = db.relationship("Group", secondary=user_groups, back_populates="users")
    role_bindings = db.relationship(
        "RoleBinding", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!r} username={self.username!r}>"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary (no credentials)."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "is_active": self.is_active,
            "is_builtin": bool(self.is_builtin),
            "must_change_password": bool(self.must_change_password),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Group(db.Model):
    """A collection of users, optionally backed by an LDAP group or Git definition."""

    __tablename__ = "groups"

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    description = db.Column(db.Text)
    ldap_dn = db.Column(db.String(512))
    git_source = db.Column(db.String(512))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    users = db.relationship("User", secondary=user_groups, back_populates="groups")
    role_bindings = db.relationship(
        "RoleBinding", back_populates="group", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Group id={self.id!r} name={self.name!r}>"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "ldap_dn": self.ldap_dn,
            "member_count": len(self.users),
        }


class Role(db.Model):
    """A named set of permissions granted via RoleBindings.

    Permissions are stored as a comma-separated string so they can be
    inspected and edited without a schema migration.  The ``permission_list``
    property provides a clean Python list.
    """

    __tablename__ = "roles"

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    permissions = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    is_builtin = db.Column(db.Boolean, default=False, nullable=False)

    role_bindings = db.relationship(
        "RoleBinding", back_populates="role", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Role id={self.id!r} name={self.name!r}>"

    @property
    def permission_list(self) -> list[str]:
        """Return the role's permissions as a deduplicated list."""
        return [p.strip() for p in (self.permissions or "").split(",") if p.strip()]

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "permissions": self.permission_list,
            "description": self.description,
            "is_builtin": bool(self.is_builtin),
        }


class RoleBinding(db.Model):
    """Binds a User or Group to a Role at a specific resource scope.

    Scope examples:
        ``organization``             – platform-wide
        ``product:api-service``      – scoped to one product
        ``environment:prod``         – scoped to one environment

    A non-null ``expires_at`` makes this a just-in-time (JIT) elevated binding.
    """

    __tablename__ = "role_bindings"

    id = db.Column(db.String(64), primary_key=True)
    role_id = db.Column(db.String(64), db.ForeignKey("roles.id"), nullable=False)
    user_id = db.Column(db.String(64), db.ForeignKey("users.id"), nullable=True)
    group_id = db.Column(db.String(64), db.ForeignKey("groups.id"), nullable=True)
    scope = db.Column(db.String(256), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    role = db.relationship("Role", back_populates="role_bindings")
    user = db.relationship("User", back_populates="role_bindings")
    group = db.relationship("Group", back_populates="role_bindings")

    def __repr__(self) -> str:
        principal = f"user:{self.user_id}" if self.user_id else f"group:{self.group_id}"
        return f"<RoleBinding {principal} → role:{self.role_id} @ {self.scope!r}>"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "role_id": self.role_id,
            "user_id": self.user_id,
            "group_id": self.group_id,
            "scope": self.scope,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
