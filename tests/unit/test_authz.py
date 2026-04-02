"""Unit tests for RBAC / authorisation.

Covers:
- Unauthenticated requests are rejected (401)
- A user without the required permission gets 403
- A user with the correct permission can access the resource
- Role creation, listing, and binding
- Permission checks via the authz_service directly
"""

from __future__ import annotations

import bcrypt

from app.extensions import db
from app.models.auth import Role, RoleBinding, User
from app.models.product import Product
from app.services.authz_service import get_permissions_for_user
from app.services.id_service import resource_id

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_product(app) -> str:
    with app.app_context():
        p = Product(
            id=resource_id("prod"),
            name="RBAC Product",
            description="",
        )
        db.session.add(p)
        db.session.commit()
        return p.id


def _make_user_client(app, flask_client, username: str, permissions: list[str]):
    """Create a user with a custom role and return an authenticated test client."""
    with app.app_context():
        pw_hash = bcrypt.hashpw(b"Test1234!", bcrypt.gensalt()).decode()
        user = User(
            id=resource_id("usr"),
            username=username,
            email=f"{username}@test.local",
            display_name=username,
            password_hash=pw_hash,
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()

        role = Role(
            id=resource_id("role"),
            name=f"role-{username}",
            permissions=",".join(permissions),
        )
        db.session.add(role)
        db.session.flush()

        binding = RoleBinding(
            id=resource_id("rb"),
            role_id=role.id,
            user_id=user.id,
            scope="organization",
        )
        db.session.add(binding)
        db.session.commit()

    r = flask_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Test1234!"},
    )
    assert r.status_code == 200, r.get_json()
    token = r.get_json()["token"]

    class AuthClient:
        def __init__(self, inner, tok):
            self._c = inner
            self._auth = {"Authorization": f"Bearer {tok}"}

        def _merge(self, kw):
            existing = kw.pop("headers", {}) or {}
            kw["headers"] = {**existing, **self._auth}
            return kw

        def get(self, *a, **kw):
            return self._c.get(*a, **self._merge(kw))

        def post(self, *a, **kw):
            return self._c.post(*a, **self._merge(kw))

        def put(self, *a, **kw):
            return self._c.put(*a, **self._merge(kw))

        def delete(self, *a, **kw):
            return self._c.delete(*a, **self._merge(kw))

    return AuthClient(flask_client, token)


# ── unauthenticated access ────────────────────────────────────────────────────


def test_unauthenticated_request_returns_401(client, app):
    prod_id = _make_product(app)
    r = client.get(f"/api/v1/products/{prod_id}/pipelines")
    assert r.status_code == 401


def test_unauthenticated_post_returns_401(client, app):
    prod_id = _make_product(app)
    r = client.post(
        f"/api/v1/products/{prod_id}/pipelines",
        json={"name": "No Auth"},
    )
    assert r.status_code == 401


# ── insufficient permissions ──────────────────────────────────────────────────


def test_no_permission_returns_403(app, client):
    prod_id = _make_product(app)
    limited = _make_user_client(app, client, "limited_user", ["products:view"])

    r = limited.post(
        f"/api/v1/products/{prod_id}/pipelines",
        json={"name": "Should Fail"},
    )
    assert r.status_code == 403


def test_view_only_can_list_but_not_create(app, client):
    prod_id = _make_product(app)
    viewer = _make_user_client(app, client, "viewer_user", ["products:view", "pipelines:view"])

    list_r = viewer.get(f"/api/v1/products/{prod_id}/pipelines")
    assert list_r.status_code == 200

    create_r = viewer.post(
        f"/api/v1/products/{prod_id}/pipelines",
        json={"name": "Blocked"},
    )
    assert create_r.status_code == 403


# ── sufficient permissions ────────────────────────────────────────────────────


def test_correct_permission_allows_access(app, client):
    prod_id = _make_product(app)
    creator = _make_user_client(
        app,
        client,
        "creator_user",
        ["products:view", "pipelines:view", "pipelines:create"],
    )

    r = creator.post(
        f"/api/v1/products/{prod_id}/pipelines",
        json={"name": "Allowed Pipeline"},
    )
    assert r.status_code == 201


# ── has_permission service ────────────────────────────────────────────────────


def test_has_permission_true(app):
    with app.app_context():
        pw_hash = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
        user = User(
            id=resource_id("usr"),
            username="perm_test_user",
            email="perm@test.local",
            password_hash=pw_hash,
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()

        role = Role(
            id=resource_id("role"),
            name="perm-test-role",
            permissions="pipelines:view,pipelines:create",
        )
        db.session.add(role)
        db.session.flush()

        db.session.add(
            RoleBinding(
                id=resource_id("rb"),
                role_id=role.id,
                user_id=user.id,
                scope="organization",
            )
        )
        db.session.commit()

        perms = get_permissions_for_user(user.id, "organization")
        assert "pipelines:view" in perms
        assert "pipelines:create" in perms
        assert "pipelines:delete" not in perms


def test_has_permission_admin_has_all(app):
    """The built-in system-administrator should have all permissions."""
    with app.app_context():
        sys_admin = Role.query.filter_by(name="system-administrator").first()
        assert sys_admin is not None

        perms = set(sys_admin.permissions.split(","))
        assert "pipelines:view" in perms
        assert "vault:reveal" in perms
        assert "users:delete" in perms


# ── role management ───────────────────────────────────────────────────────────


def test_list_roles(admin_client, app):
    r = admin_client.get("/api/v1/roles")
    assert r.status_code == 200
    names = [role["name"] for role in r.get_json()]
    assert "system-administrator" in names


def test_create_and_list_custom_role(admin_client, app):
    r = admin_client.post(
        "/api/v1/roles",
        json={
            "name": "custom-tester",
            "permissions": ["pipelines:view", "runs:view"],
            "description": "Read-only pipeline and run access",
        },
    )
    assert r.status_code == 201
    data = r.get_json()
    assert data["name"] == "custom-tester"

    list_r = admin_client.get("/api/v1/roles")
    names = [role["name"] for role in list_r.get_json()]
    assert "custom-tester" in names
