"""Shared fixtures for E2E tests.

All E2E tests run against the full Flask app with an in-memory SQLite database.
The ``admin_client`` fixture provides an authenticated client pre-loaded with
a system-administrator JWT token so tests focus on product flows, not auth.
"""

from __future__ import annotations

import bcrypt
import pytest

from app import _ensure_builtin_roles, create_app
from app.config import TestConfig
from app.extensions import db as _db
from app.models.auth import Role, RoleBinding, User
from app.services.id_service import resource_id


@pytest.fixture(scope="module")
def app():
    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        _ensure_builtin_roles()
        yield application
        _db.drop_all()


@pytest.fixture(scope="module")
def admin_client(app):
    """Authenticated test client with system-administrator role."""
    with app.app_context():
        pw_hash = bcrypt.hashpw(b"Admin1234!", bcrypt.gensalt()).decode()
        user = User(
            id=resource_id("usr"),
            username="e2e_admin",
            email="e2e_admin@test.local",
            display_name="E2E Admin",
            password_hash=pw_hash,
            is_active=True,
        )
        _db.session.add(user)
        _db.session.flush()

        sys_admin = Role.query.filter_by(name="system-administrator").first()
        binding = RoleBinding(
            id=resource_id("rb"),
            role_id=sys_admin.id,
            user_id=user.id,
            scope="organization",
        )
        _db.session.add(binding)
        _db.session.commit()

    c = app.test_client()
    login_r = c.post(
        "/api/v1/auth/login",
        json={"username": "e2e_admin", "password": "Admin1234!"},
    )
    assert login_r.status_code == 200, f"Login failed: {login_r.get_json()}"
    token = login_r.get_json()["token"]

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

        @property
        def application(self):
            return self._c.application

    return AuthClient(c, token)
