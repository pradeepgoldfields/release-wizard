"""Shared fixtures for unit tests.

Provides an ``admin_client`` fixture that creates a system-administrator user
directly via the ORM (bypassing HTTP auth), logs in, and returns a test client
pre-configured with a valid Bearer token.
"""

from __future__ import annotations

import bcrypt
import pytest

from app import _ensure_builtin_roles, create_app
from app.config import TestConfig
from app.extensions import db as _db
from app.models.auth import Role, RoleBinding, User
from app.services.id_service import resource_id


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        _ensure_builtin_roles()   # skipped by create_app under TESTING; seed manually
        yield application
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin_client(app):
    """Return a test client authenticated as a system-administrator.

    Creates the admin user directly via the ORM so we avoid the chicken-and-egg
    of needing auth to create the first user.
    """
    with app.app_context():
        # Create user directly via ORM
        pw_hash = bcrypt.hashpw(b"Admin1234!", bcrypt.gensalt()).decode()
        user = User(
            id=resource_id("usr"),
            username="test_admin",
            email="admin@test.local",
            display_name="Test Admin",
            password_hash=pw_hash,
            is_active=True,
        )
        _db.session.add(user)
        _db.session.flush()

        # Bind system-administrator role
        sys_admin = Role.query.filter_by(name="system-administrator").first()
        assert sys_admin is not None, "system-administrator role not found after _ensure_builtin_roles()"
        binding = RoleBinding(
            id=resource_id("rb"),
            role_id=sys_admin.id,
            user_id=user.id,
            scope="organization",
        )
        _db.session.add(binding)
        _db.session.commit()

    # Log in via HTTP to get a real JWT
    c = app.test_client()
    login_r = c.post(
        "/api/v1/auth/login",
        json={"username": "test_admin", "password": "Admin1234!"},
    )
    assert login_r.status_code == 200, f"Login failed: {login_r.get_json()}"
    token = login_r.get_json()["token"]

    # Wrap the client so every request carries the Authorization header
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

        def patch(self, *a, **kw):
            return self._c.patch(*a, **self._merge(kw))

        def delete(self, *a, **kw):
            return self._c.delete(*a, **self._merge(kw))

    return AuthClient(c, token)
