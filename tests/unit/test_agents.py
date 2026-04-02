"""Unit tests for AgentPool endpoints.

Covers: list pools, create pool, get pool, update pool, delete pool.
"""

from __future__ import annotations

# ── helpers ───────────────────────────────────────────────────────────────────


def _create_pool(admin_client, name="test-pool"):
    r = admin_client.post(
        "/api/v1/agent-pools",
        json={
            "name": name,
            "description": "A test pool",
            "pool_type": "subprocess",
            "max_agents": 5,
        },
    )
    assert r.status_code == 201, r.get_json()
    return r.get_json()


# ── list ──────────────────────────────────────────────────────────────────────


def test_list_agent_pools(admin_client, app):
    r = admin_client.get("/api/v1/agent-pools")
    assert r.status_code == 200
    # Built-in pools are seeded by the app factory; we just check shape
    data = r.get_json()
    assert isinstance(data, list)


# ── create ────────────────────────────────────────────────────────────────────


def test_create_agent_pool_success(admin_client, app):
    r = admin_client.post(
        "/api/v1/agent-pools",
        json={"name": "custom-pool", "description": "custom", "pool_type": "subprocess"},
    )
    assert r.status_code == 201
    data = r.get_json()
    assert data["name"] == "custom-pool"
    assert "id" in data


def test_create_agent_pool_missing_name(admin_client, app):
    r = admin_client.post(
        "/api/v1/agent-pools",
        json={"description": "no name here"},
    )
    assert r.status_code == 400


def test_create_agent_pool_duplicate_name(admin_client, app):
    _create_pool(admin_client, name="unique-pool")
    r = admin_client.post(
        "/api/v1/agent-pools",
        json={"name": "unique-pool"},
    )
    assert r.status_code == 409


# ── get ───────────────────────────────────────────────────────────────────────


def test_get_agent_pool_found(admin_client, app):
    pool = _create_pool(admin_client, name="get-pool")
    r = admin_client.get(f"/api/v1/agent-pools/{pool['id']}")
    assert r.status_code == 200
    assert r.get_json()["name"] == "get-pool"


def test_get_agent_pool_not_found(admin_client, app):
    r = admin_client.get("/api/v1/agent-pools/nonexistent")
    assert r.status_code == 404


# ── update ────────────────────────────────────────────────────────────────────


def test_update_agent_pool(admin_client, app):
    pool = _create_pool(admin_client, name="upd-pool")
    r = admin_client.patch(
        f"/api/v1/agent-pools/{pool['id']}",
        json={"description": "updated desc", "max_agents": 20},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["description"] == "updated desc"
    assert data["max_agents"] == 20


# ── delete ────────────────────────────────────────────────────────────────────


def test_delete_agent_pool(admin_client, app):
    pool = _create_pool(admin_client, name="del-pool")
    r = admin_client.delete(f"/api/v1/agent-pools/{pool['id']}")
    assert r.status_code in (200, 204)

    r2 = admin_client.get(f"/api/v1/agent-pools/{pool['id']}")
    assert r2.status_code == 404
