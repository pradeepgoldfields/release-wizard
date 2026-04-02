"""Unit tests for Vault (secrets) endpoints.

Covers: list, create, get metadata, reveal, update, delete.
Admin-only write operations are tested with admin_client.
Access-control (non-admin reveal) is tested with a regular user client.
"""

from __future__ import annotations

# ── helpers ───────────────────────────────────────────────────────────────────


def _create_secret(admin_client, name="MY_SECRET", value="s3cr3t"):
    r = admin_client.post(
        "/api/v1/vault",
        json={"name": name, "value": value, "description": "test secret", "allowed_users": "*"},
    )
    assert r.status_code == 201, r.get_json()
    return r.get_json()


# ── list ──────────────────────────────────────────────────────────────────────


def test_list_secrets_empty(admin_client, app):
    r = admin_client.get("/api/v1/vault")
    assert r.status_code == 200
    assert r.get_json() == []


def test_list_secrets_redacts_value(admin_client, app):
    _create_secret(admin_client)
    r = admin_client.get("/api/v1/vault")
    assert r.status_code == 200
    items = r.get_json()
    assert len(items) == 1
    assert "value" not in items[0]
    assert "ciphertext" not in items[0]


# ── create ────────────────────────────────────────────────────────────────────


def test_create_secret_success(admin_client, app):
    r = admin_client.post(
        "/api/v1/vault",
        json={"name": "DB_PASSWORD", "value": "hunter2"},
    )
    assert r.status_code == 201
    data = r.get_json()
    assert data["name"] == "DB_PASSWORD"
    assert "id" in data
    assert "value" not in data


def test_create_secret_missing_name(admin_client, app):
    r = admin_client.post("/api/v1/vault", json={"value": "hunter2"})
    assert r.status_code == 400


def test_create_secret_missing_value(admin_client, app):
    r = admin_client.post("/api/v1/vault", json={"name": "EMPTY"})
    assert r.status_code == 400


def test_create_secret_duplicate_name(admin_client, app):
    _create_secret(admin_client, name="DUPE")
    r = admin_client.post("/api/v1/vault", json={"name": "DUPE", "value": "other"})
    assert r.status_code == 409


# ── get metadata ──────────────────────────────────────────────────────────────


def test_get_secret_metadata(admin_client, app):
    sec = _create_secret(admin_client, name="META_TEST")
    r = admin_client.get(f"/api/v1/vault/{sec['id']}")
    assert r.status_code == 200
    data = r.get_json()
    assert data["name"] == "META_TEST"
    assert "value" not in data
    assert "ciphertext" not in data


def test_get_secret_not_found(admin_client, app):
    r = admin_client.get("/api/v1/vault/nonexistent")
    assert r.status_code == 404


# ── reveal ────────────────────────────────────────────────────────────────────


def test_reveal_secret_as_admin(admin_client, app):
    sec = _create_secret(admin_client, name="REVEAL_ME", value="plaintext_value")
    r = admin_client.post(f"/api/v1/vault/{sec['id']}/reveal")
    assert r.status_code == 200
    data = r.get_json()
    assert data["value"] == "plaintext_value"


def test_reveal_nonexistent_secret(admin_client, app):
    r = admin_client.post("/api/v1/vault/nonexistent/reveal")
    assert r.status_code == 404


# ── update ────────────────────────────────────────────────────────────────────


def test_update_secret_value(admin_client, app):
    sec = _create_secret(admin_client, name="UPD_SECRET", value="old_value")

    r = admin_client.put(
        f"/api/v1/vault/{sec['id']}",
        json={"value": "new_value"},
    )
    assert r.status_code == 200

    reveal = admin_client.post(f"/api/v1/vault/{sec['id']}/reveal")
    assert reveal.get_json()["value"] == "new_value"


def test_update_secret_description(admin_client, app):
    sec = _create_secret(admin_client, name="DESC_SECRET")
    r = admin_client.put(
        f"/api/v1/vault/{sec['id']}",
        json={"description": "updated description"},
    )
    assert r.status_code == 200
    assert r.get_json()["description"] == "updated description"


# ── delete ────────────────────────────────────────────────────────────────────


def test_delete_secret(admin_client, app):
    sec = _create_secret(admin_client, name="DEL_SECRET")
    r = admin_client.delete(f"/api/v1/vault/{sec['id']}")
    assert r.status_code == 200

    r2 = admin_client.get(f"/api/v1/vault/{sec['id']}")
    assert r2.status_code == 404
