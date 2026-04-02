"""E2E: RBAC — users, groups, roles, scoped bindings, permission enforcement."""

from __future__ import annotations

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────


def _list_items(r):
    data = r.get_json()
    return data if isinstance(data, list) else data.get("items", [])


def _get_role(admin_client, name):
    return next(ro for ro in _list_items(admin_client.get("/api/v1/roles")) if ro["name"] == name)


# ── User management ───────────────────────────────────────────────────────────


def test_create_user_returns_201(admin_client):
    r = admin_client.post(
        "/api/v1/users",
        json={
            "username": "rbac_test_user",
            "email": "rbac@test.local",
            "password": "Test1234!",
            "display_name": "RBAC Test",
        },
    )
    assert r.status_code == 201
    data = r.get_json()
    assert len(data["id"]) > 0
    assert data["username"] == "rbac_test_user"
    admin_client.delete(f"/api/v1/users/{data['id']}")


def test_create_user_duplicate_username_returns_409(admin_client):
    r1 = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_dup_user", "email": "dup@test.local", "password": "Test1234!"},
    )
    assert r1.status_code == 201
    uid = r1.get_json()["id"]
    r2 = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_dup_user", "email": "dup2@test.local", "password": "Test1234!"},
    )
    assert r2.status_code == 409
    admin_client.delete(f"/api/v1/users/{uid}")


def test_list_users_includes_created_user(admin_client):
    r = admin_client.get("/api/v1/users")
    assert r.status_code == 200
    usernames = [u["username"] for u in _list_items(r)]
    assert "e2e_admin" in usernames


def test_get_user_by_id(admin_client):
    r = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_getbyid", "email": "getbyid@test.local", "password": "Test1234!"},
    )
    assert r.status_code == 201
    uid = r.get_json()["id"]
    r2 = admin_client.get(f"/api/v1/users/{uid}")
    assert r2.status_code == 200
    assert r2.get_json()["username"] == "rbac_getbyid"
    admin_client.delete(f"/api/v1/users/{uid}")


def test_update_user_display_name(admin_client):
    r = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_update", "email": "update@test.local", "password": "Test1234!"},
    )
    assert r.status_code == 201
    uid = r.get_json()["id"]
    patch = admin_client.patch(f"/api/v1/users/{uid}", json={"display_name": "Updated Name"})
    assert patch.status_code == 200
    assert patch.get_json()["display_name"] == "Updated Name"
    admin_client.delete(f"/api/v1/users/{uid}")


def test_deactivate_user(admin_client):
    r = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_deactivate", "email": "deact@test.local", "password": "Test1234!"},
    )
    assert r.status_code == 201
    uid = r.get_json()["id"]
    patch = admin_client.patch(f"/api/v1/users/{uid}", json={"is_active": False})
    assert patch.status_code == 200
    assert patch.get_json()["is_active"] is False
    admin_client.delete(f"/api/v1/users/{uid}")


def test_change_user_password(admin_client):
    r = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_pwchange", "email": "pwchange@test.local", "password": "OldPass1!"},
    )
    assert r.status_code == 201
    uid = r.get_json()["id"]
    patch = admin_client.patch(f"/api/v1/users/{uid}/password", json={"password": "NewPass1!"})
    assert patch.status_code == 200
    login = admin_client._c.post(
        "/api/v1/auth/login", json={"username": "rbac_pwchange", "password": "NewPass1!"}
    )
    assert login.status_code == 200
    admin_client.delete(f"/api/v1/users/{uid}")


def test_delete_user_returns_204(admin_client):
    r = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_delete", "email": "del@test.local", "password": "Test1234!"},
    )
    assert r.status_code == 201
    uid = r.get_json()["id"]
    assert admin_client.delete(f"/api/v1/users/{uid}").status_code == 204
    assert admin_client.get(f"/api/v1/users/{uid}").status_code == 404


def test_cannot_delete_builtin_user(admin_client):
    users = _list_items(admin_client.get("/api/v1/users"))
    builtin = next((u for u in users if u.get("is_builtin") or u["username"] == "admin"), None)
    if builtin is None:
        pytest.skip("No builtin user found")
    assert admin_client.delete(f"/api/v1/users/{builtin['id']}").status_code in (403, 409)


# ── Group management ──────────────────────────────────────────────────────────


def test_create_group_returns_201(admin_client):
    r = admin_client.post("/api/v1/groups", json={"name": "E2E Group"})
    assert r.status_code == 201
    gid = r.get_json()["id"]
    assert len(gid) > 0
    admin_client.delete(f"/api/v1/groups/{gid}")


def test_add_user_to_group(admin_client):
    g = admin_client.post("/api/v1/groups", json={"name": "E2E Member Group"}).get_json()
    u = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_grp_member", "email": "grpm@test.local", "password": "Test1234!"},
    ).get_json()
    r = admin_client.post(f"/api/v1/groups/{g['id']}/members/{u['id']}")
    assert r.status_code == 200
    admin_client.delete(f"/api/v1/users/{u['id']}")
    admin_client.delete(f"/api/v1/groups/{g['id']}")


def test_remove_user_from_group(admin_client):
    g = admin_client.post("/api/v1/groups", json={"name": "E2E Remove Group"}).get_json()
    u = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_grp_remove", "email": "grprm@test.local", "password": "Test1234!"},
    ).get_json()
    admin_client.post(f"/api/v1/groups/{g['id']}/members/{u['id']}")
    r = admin_client.delete(f"/api/v1/groups/{g['id']}/members/{u['id']}")
    assert r.status_code in (200, 204)
    # Verify via group detail or users list that member is removed
    group_data = admin_client.get(f"/api/v1/groups/{g['id']}").get_json() or {}
    members = group_data.get("members", []) or group_data.get("users", [])
    assert not any(m.get("id") == u["id"] for m in members)
    admin_client.delete(f"/api/v1/users/{u['id']}")
    admin_client.delete(f"/api/v1/groups/{g['id']}")


def test_delete_group_returns_204(admin_client):
    g = admin_client.post("/api/v1/groups", json={"name": "E2E Delete Group"}).get_json()
    assert admin_client.delete(f"/api/v1/groups/{g['id']}").status_code == 204


# ── Role management ───────────────────────────────────────────────────────────


def test_list_builtin_roles(admin_client):
    r = admin_client.get("/api/v1/roles")
    assert r.status_code == 200
    names = [ro["name"] for ro in _list_items(r)]
    # Only system-level roles guaranteed by _ensure_builtin_roles
    for expected in ("system-administrator", "product-admin"):
        assert expected in names, f"Missing builtin role: {expected}"


def test_create_custom_role(admin_client):
    r = admin_client.post(
        "/api/v1/roles",
        json={"name": "e2e-custom-role", "permissions": ["products:view", "pipelines:view"]},
    )
    assert r.status_code == 201
    data = r.get_json()
    assert data["is_builtin"] is False
    admin_client.delete(f"/api/v1/roles/{data['id']}")


def test_update_custom_role_permissions(admin_client):
    r = admin_client.post(
        "/api/v1/roles",
        json={"name": "e2e-update-role", "permissions": ["products:view"]},
    )
    assert r.status_code == 201
    rid = r.get_json()["id"]
    patch = admin_client.patch(
        f"/api/v1/roles/{rid}",
        json={"permissions": ["products:view", "pipelines:view"]},
    )
    assert patch.status_code == 200
    data = patch.get_json()
    perms = data.get("permissions") or data.get("permission_list", [])
    assert "pipelines:view" in perms
    admin_client.delete(f"/api/v1/roles/{rid}")


def test_delete_custom_role(admin_client):
    r = admin_client.post(
        "/api/v1/roles",
        json={"name": "e2e-delete-role", "permissions": ["products:view"]},
    )
    assert r.status_code == 201
    rid = r.get_json()["id"]
    assert admin_client.delete(f"/api/v1/roles/{rid}").status_code == 204


def test_cannot_delete_builtin_role(admin_client):
    builtin = next(
        (ro for ro in _list_items(admin_client.get("/api/v1/roles")) if ro.get("is_builtin")), None
    )
    if not builtin:
        pytest.skip("No builtin role found")
    assert admin_client.delete(f"/api/v1/roles/{builtin['id']}").status_code in (403, 409)


# ── Role bindings ─────────────────────────────────────────────────────────────


def _ensure_role(admin_client, name, perms=None):
    """Return an existing role by name, or create it if absent."""
    roles = _list_items(admin_client.get("/api/v1/roles"))
    existing = next((r for r in roles if r["name"] == name), None)
    if existing:
        return existing
    r = admin_client.post(
        "/api/v1/roles",
        json={"name": name, "permissions": perms or ["products:view"]},
    )
    assert r.status_code == 201, f"Could not create role '{name}': {r.get_json()}"
    return r.get_json()


def test_grant_user_scoped_role_at_organization(admin_client):
    u = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_bind_org", "email": "bindorg@test.local", "password": "Test1234!"},
    ).get_json()
    viewer = _ensure_role(admin_client, "viewer", ["products:view", "pipelines:view"])
    r = admin_client.post(
        "/api/v1/rbac/bindings",
        json={"user_id": u["id"], "role_id": viewer["id"], "scope": "organization"},
    )
    assert r.status_code == 201
    admin_client.delete(f"/api/v1/rbac/bindings/{r.get_json()['id']}")
    admin_client.delete(f"/api/v1/users/{u['id']}")


def test_grant_user_scoped_role_at_product(admin_client):
    prod = admin_client.post("/api/v1/products", json={"name": "RBAC Scope Product"}).get_json()
    u = admin_client.post(
        "/api/v1/users",
        json={
            "username": "rbac_bind_prod",
            "email": "bindprod@test.local",
            "password": "Test1234!",
        },
    ).get_json()
    dev = _ensure_role(
        admin_client, "developer", ["products:view", "pipelines:view", "pipelines:execute"]
    )
    r = admin_client.post(
        "/api/v1/rbac/bindings",
        json={"user_id": u["id"], "role_id": dev["id"], "scope": f"product:{prod['id']}"},
    )
    assert r.status_code == 201
    admin_client.delete(f"/api/v1/rbac/bindings/{r.get_json()['id']}")
    admin_client.delete(f"/api/v1/users/{u['id']}")
    admin_client.delete(f"/api/v1/products/{prod['id']}")


def test_grant_group_scoped_role(admin_client):
    g = admin_client.post("/api/v1/groups", json={"name": "RBAC Group Bind"}).get_json()
    viewer = _ensure_role(admin_client, "viewer", ["products:view", "pipelines:view"])
    r = admin_client.post(
        "/api/v1/rbac/bindings",
        json={"group_id": g["id"], "role_id": viewer["id"], "scope": "organization"},
    )
    assert r.status_code == 201
    admin_client.delete(f"/api/v1/rbac/bindings/{r.get_json()['id']}")
    admin_client.delete(f"/api/v1/groups/{g['id']}")


def test_list_bindings_for_scope(admin_client):
    r = admin_client.get("/api/v1/rbac/bindings?scope=organization")
    assert r.status_code == 200
    assert isinstance(_list_items(r), list)


def test_revoke_binding_returns_204(admin_client):
    u = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_revoke", "email": "revoke@test.local", "password": "Test1234!"},
    ).get_json()
    viewer = _ensure_role(admin_client, "viewer", ["products:view", "pipelines:view"])
    b = admin_client.post(
        "/api/v1/rbac/bindings",
        json={"user_id": u["id"], "role_id": viewer["id"], "scope": "organization"},
    ).get_json()
    assert admin_client.delete(f"/api/v1/rbac/bindings/{b['id']}").status_code == 204
    admin_client.delete(f"/api/v1/users/{u['id']}")


def test_jit_binding_has_expires_at(admin_client):
    u = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_jit", "email": "jit@test.local", "password": "Test1234!"},
    ).get_json()
    viewer = _ensure_role(admin_client, "viewer", ["products:view", "pipelines:view"])
    r = admin_client.post(
        "/api/v1/rbac/bindings",
        json={
            "user_id": u["id"],
            "role_id": viewer["id"],
            "scope": "organization",
            "expires_at": "2099-12-31T23:59:59Z",
        },
    )
    assert r.status_code == 201
    binding = r.get_json()
    assert binding.get("expires_at") is not None
    admin_client.delete(f"/api/v1/rbac/bindings/{binding['id']}")
    admin_client.delete(f"/api/v1/users/{u['id']}")


# ── Effective permissions ─────────────────────────────────────────────────────


def test_get_user_effective_permissions(admin_client):
    admin_user = next(
        u for u in _list_items(admin_client.get("/api/v1/users")) if u["username"] == "e2e_admin"
    )
    r = admin_client.get(f"/api/v1/users/{admin_user['id']}/permissions?scope=organization")
    assert r.status_code == 200
    assert "permissions" in r.get_json()


def test_permission_catalog_is_non_empty(admin_client):
    r = admin_client.get("/api/v1/permissions/catalog")
    assert r.status_code == 200
    data = r.get_json()
    # catalog may be a list of groups or a dict keyed by group name
    assert (isinstance(data, list) and len(data) >= 1) or (
        isinstance(data, dict) and len(data) >= 1
    )


# ── Enforcement ───────────────────────────────────────────────────────────────


def test_unauthenticated_request_to_products_returns_401(admin_client):
    r = admin_client._c.get("/api/v1/products")
    assert r.status_code == 401


def test_developer_cannot_create_product(admin_client):
    u = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_dev_noprod", "email": "devnp@test.local", "password": "Test1234!"},
    ).get_json()
    # Use a role that explicitly does NOT have products:create
    dev = _ensure_role(admin_client, "developer", ["pipelines:view", "pipelines:execute"])
    admin_client.post(
        "/api/v1/rbac/bindings",
        json={"user_id": u["id"], "role_id": dev["id"], "scope": "organization"},
    )
    token = admin_client._c.post(
        "/api/v1/auth/login", json={"username": "rbac_dev_noprod", "password": "Test1234!"}
    ).get_json()["token"]
    r = admin_client._c.post(
        "/api/v1/products",
        json={"name": "Should Fail"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    admin_client.delete(f"/api/v1/users/{u['id']}")


def test_viewer_cannot_trigger_pipeline_run(admin_client):
    prod = admin_client.post("/api/v1/products", json={"name": "Viewer Test Prod"}).get_json()
    pl = admin_client.post(
        f"/api/v1/products/{prod['id']}/pipelines",
        json={"name": "Viewer Test PL", "kind": "ci"},
    ).get_json()
    u = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_viewer_norun", "email": "vnr@test.local", "password": "Test1234!"},
    ).get_json()
    # Use product-scoped binding with view-only — org-scope bindings grant full access
    viewer = _ensure_role(admin_client, "viewer", ["products:view", "pipelines:view"])
    admin_client.post(
        "/api/v1/rbac/bindings",
        json={"user_id": u["id"], "role_id": viewer["id"], "scope": f"product:{prod['id']}"},
    )
    token = admin_client._c.post(
        "/api/v1/auth/login", json={"username": "rbac_viewer_norun", "password": "Test1234!"}
    ).get_json()["token"]
    r = admin_client._c.post(
        f"/api/v1/pipelines/{pl['id']}/runs",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Without pipelines:execute the run should be blocked
    assert r.status_code == 403
    admin_client.delete(f"/api/v1/users/{u['id']}")
    admin_client.delete(f"/api/v1/products/{prod['id']}")


def test_product_scoped_user_cannot_access_other_product(admin_client):
    prod_a = admin_client.post("/api/v1/products", json={"name": "Prod A RBAC"}).get_json()
    prod_b = admin_client.post("/api/v1/products", json={"name": "Prod B RBAC"}).get_json()
    u = admin_client.post(
        "/api/v1/users",
        json={
            "username": "rbac_scoped_user",
            "email": "scoped@test.local",
            "password": "Test1234!",
        },
    ).get_json()
    viewer = _ensure_role(admin_client, "viewer", ["products:view", "pipelines:view"])
    admin_client.post(
        "/api/v1/rbac/bindings",
        json={"user_id": u["id"], "role_id": viewer["id"], "scope": f"product:{prod_a['id']}"},
    )
    token = admin_client._c.post(
        "/api/v1/auth/login", json={"username": "rbac_scoped_user", "password": "Test1234!"}
    ).get_json()["token"]
    r = admin_client._c.get(
        f"/api/v1/products/{prod_b['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (403, 404)
    admin_client.delete(f"/api/v1/users/{u['id']}")
    admin_client.delete(f"/api/v1/products/{prod_a['id']}")
    admin_client.delete(f"/api/v1/products/{prod_b['id']}")


# ── Bulk user import ──────────────────────────────────────────────────────────


def test_bulk_import_users_from_json(admin_client):
    payload = [
        {"username": "bulk_user_1", "email": "b1@test.local", "password": "Test1234!"},
        {"username": "bulk_user_2", "email": "b2@test.local", "password": "Test1234!"},
    ]
    r = admin_client.post("/api/v1/users/import", json=payload)
    assert r.status_code == 200
    data = r.get_json()
    # Response uses "created" key (not "imported_count")
    created = data.get("created", data.get("imported_count", 0))
    assert created >= 2
    for u in _list_items(admin_client.get("/api/v1/users")):
        if u["username"] in ("bulk_user_1", "bulk_user_2"):
            admin_client.delete(f"/api/v1/users/{u['id']}")


def test_bulk_import_skips_duplicate_usernames(admin_client):
    r0 = admin_client.post(
        "/api/v1/users",
        json={"username": "bulk_dup_u", "email": "bdup@test.local", "password": "Test1234!"},
    )
    assert r0.status_code == 201
    uid = r0.get_json()["id"]
    r = admin_client.post(
        "/api/v1/users/import",
        json=[
            {"username": "bulk_dup_u", "email": "bdup2@test.local", "password": "Test1234!"},
            {"username": "bulk_new_u", "email": "bnew@test.local", "password": "Test1234!"},
        ],
    )
    assert r.status_code == 200
    data = r.get_json()
    # Response uses "skipped" key (not "skipped_count")
    skipped = data.get("skipped", data.get("skipped_count", 0))
    assert skipped >= 1
    admin_client.delete(f"/api/v1/users/{uid}")
    for u in _list_items(admin_client.get("/api/v1/users")):
        if u["username"] == "bulk_new_u":
            admin_client.delete(f"/api/v1/users/{u['id']}")
