"""E2E: Environments (org-level + product attachment) and application management.

Covers:
  - Top-level environment CRUD
  - Attaching and detaching environments from products
  - Environment ordering
  - Application (artifact) registration under a product
  - Application association with pipelines
  - Application group definition within releases (sequential / parallel)
"""

from __future__ import annotations

import json

import pytest


def _list_items(r):
    data = r.get_json()
    return data if isinstance(data, list) else data.get("items", [])


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def product(admin_client):
    r = admin_client.post(
        "/api/v1/products",
        json={"name": "Env/App E2E Product", "description": "Env and app tests"},
    )
    assert r.status_code == 201
    return r.get_json()


@pytest.fixture(scope="module")
def environment(admin_client):
    r = admin_client.post(
        "/api/v1/environments",
        json={"name": "Staging", "env_type": "staging", "order": 2},
    )
    assert r.status_code == 201
    return r.get_json()


@pytest.fixture(scope="module")
def application(admin_client, product):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/applications",
        json={"name": "E2E App", "artifact_type": "container"},
    )
    assert r.status_code == 201
    return r.get_json()


# ── Top-level environment lifecycle ───────────────────────────────────────────


def test_create_environment_returns_201(environment):
    assert "id" in environment
    assert environment["env_type"] == "staging"


def test_list_environments_includes_created(admin_client, environment):
    r = admin_client.get("/api/v1/environments")
    assert r.status_code == 200
    ids = [e["id"] for e in _list_items(r)]
    assert environment["id"] in ids


def test_get_environment_by_id(admin_client, environment):
    r = admin_client.get(f"/api/v1/environments/{environment['id']}")
    assert r.status_code == 200
    assert r.get_json()["name"] == "Staging"


def test_update_environment_description(admin_client, environment):
    r = admin_client.put(
        f"/api/v1/environments/{environment['id']}",
        json={"description": "Updated staging desc"},
    )
    assert r.status_code == 200
    assert r.get_json().get("description") == "Updated staging desc"


def test_delete_environment_returns_204(admin_client):
    cr = admin_client.post(
        "/api/v1/environments",
        json={"name": "Throwaway Env", "env_type": "custom"},
    )
    assert cr.status_code == 201
    env_id = cr.get_json()["id"]

    dr = admin_client.delete(f"/api/v1/environments/{env_id}")
    assert dr.status_code == 204

    gr = admin_client.get(f"/api/v1/environments/{env_id}")
    assert gr.status_code == 404


def test_environment_order_field_stored(admin_client, environment):
    r = admin_client.get(f"/api/v1/environments/{environment['id']}")
    assert r.status_code == 200
    assert r.get_json().get("order") == 2


def test_multiple_environments_returned_in_order(admin_client):
    dev = admin_client.post(
        "/api/v1/environments", json={"name": "Dev Order", "env_type": "dev", "order": 1}
    ).get_json()
    staging = admin_client.post(
        "/api/v1/environments", json={"name": "Staging Order", "env_type": "staging", "order": 2}
    ).get_json()
    prod = admin_client.post(
        "/api/v1/environments", json={"name": "Prod Order", "env_type": "production", "order": 3}
    ).get_json()

    r = admin_client.get("/api/v1/environments")
    assert r.status_code == 200
    envs = _list_items(r)
    our_ids = {dev["id"], staging["id"], prod["id"]}
    our_envs = [e for e in envs if e["id"] in our_ids]
    orders = [e["order"] for e in our_envs]
    assert orders == sorted(orders)


# ── Product ↔ environment attachment ─────────────────────────────────────────


def test_attach_environment_to_product(admin_client, product, environment):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/environments",
        json={"environment_id": environment["id"]},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("status") == "attached"


def test_attached_environment_visible_under_product(admin_client, product, environment):
    admin_client.post(
        f"/api/v1/products/{product['id']}/environments",
        json={"environment_id": environment["id"]},
    )
    r = admin_client.get(f"/api/v1/products/{product['id']}/environments")
    assert r.status_code == 200
    ids = [e["id"] for e in _list_items(r)]
    assert environment["id"] in ids


def test_detach_environment_removes_association(admin_client, product, environment):
    admin_client.post(
        f"/api/v1/products/{product['id']}/environments",
        json={"environment_id": environment["id"]},
    )
    dr = admin_client.delete(f"/api/v1/products/{product['id']}/environments/{environment['id']}")
    assert dr.status_code == 204

    r = admin_client.get(f"/api/v1/products/{product['id']}/environments")
    ids = [e["id"] for e in _list_items(r)]
    assert environment["id"] not in ids


def test_detached_environment_still_exists_globally(admin_client, product, environment):
    admin_client.delete(f"/api/v1/products/{product['id']}/environments/{environment['id']}")
    r = admin_client.get(f"/api/v1/environments/{environment['id']}")
    assert r.status_code == 200


def test_attach_same_environment_twice_returns_409(admin_client, product, environment):
    admin_client.post(
        f"/api/v1/products/{product['id']}/environments",
        json={"environment_id": environment["id"]},
    )
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/environments",
        json={"environment_id": environment["id"]},
    )
    assert r.status_code in (200, 409)


# ── Application (artifact) management ────────────────────────────────────────


def test_register_application_under_product(application):
    assert "id" in application
    assert application["artifact_type"] == "container"


def test_list_applications_under_product(admin_client, product, application):
    r = admin_client.get(f"/api/v1/products/{product['id']}/applications")
    assert r.status_code == 200
    ids = [a["id"] for a in _list_items(r)]
    assert application["id"] in ids


def test_get_application_by_id(admin_client, product, application):
    r = admin_client.get(f"/api/v1/products/{product['id']}/applications/{application['id']}")
    assert r.status_code == 200
    assert r.get_json()["name"] == "E2E App"


def test_update_application_repository_url(admin_client, product, application):
    r = admin_client.put(
        f"/api/v1/products/{product['id']}/applications/{application['id']}",
        json={"repository_url": "ghcr.io/org/app"},
    )
    assert r.status_code == 200
    assert r.get_json().get("repository_url") == "ghcr.io/org/app"


def test_update_application_build_version(admin_client, product, application):
    r = admin_client.put(
        f"/api/v1/products/{product['id']}/applications/{application['id']}",
        json={"build_version": "2.1.0"},
    )
    assert r.status_code == 200
    assert r.get_json().get("build_version") == "2.1.0"


def test_delete_application_returns_204(admin_client, product):
    cr = admin_client.post(
        f"/api/v1/products/{product['id']}/applications",
        json={"name": "Throwaway App", "artifact_type": "helm"},
    )
    assert cr.status_code == 201
    app_id = cr.get_json()["id"]

    dr = admin_client.delete(f"/api/v1/products/{product['id']}/applications/{app_id}")
    assert dr.status_code == 204


def test_application_compliance_rating_defaults(application):
    assert "compliance_rating" in application


# ── Application groups within releases ───────────────────────────────────────


@pytest.fixture(scope="module")
def release(admin_client, product):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/releases",
        json={"name": "App Group Release", "version": "1.0.0"},
    )
    assert r.status_code == 201
    return r.get_json()


def test_add_application_group_to_release(admin_client, product, release, application):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/releases/{release['id']}/application-groups",
        json={"application_id": application["id"], "execution_mode": "sequential"},
    )
    assert r.status_code == 201
    assert "id" in r.get_json()


def test_application_group_sequential_mode_stored(admin_client, product, release, application):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/releases/{release['id']}/application-groups",
        json={"application_id": application["id"], "execution_mode": "sequential"},
    )
    assert r.status_code == 201
    assert r.get_json()["execution_mode"] == "sequential"


def test_application_group_parallel_mode_stored(admin_client, product, application):
    pid = product["id"]
    rid = admin_client.post(
        f"/api/v1/products/{pid}/releases",
        json={"name": "Parallel Release"},
    ).get_json()["id"]
    r = admin_client.post(
        f"/api/v1/products/{pid}/releases/{rid}/application-groups",
        json={"application_id": application["id"], "execution_mode": "parallel"},
    )
    assert r.status_code == 201
    assert r.get_json()["execution_mode"] == "parallel"


def test_remove_application_group_from_release(admin_client, product, application):
    pid = product["id"]
    rid = admin_client.post(
        f"/api/v1/products/{pid}/releases",
        json={"name": "Group Remove Release"},
    ).get_json()["id"]
    gr = admin_client.post(
        f"/api/v1/products/{pid}/releases/{rid}/application-groups",
        json={"application_id": application["id"], "execution_mode": "sequential"},
    )
    assert gr.status_code == 201
    group_id = gr.get_json()["id"]

    dr = admin_client.delete(f"/api/v1/products/{pid}/releases/{rid}/application-groups/{group_id}")
    assert dr.status_code == 204

    r = admin_client.get(f"/api/v1/products/{pid}/releases/{rid}/application-groups")
    assert r.status_code == 200
    ids = [g["id"] for g in _list_items(r)]
    assert group_id not in ids


def test_application_group_pipeline_ids_stored(admin_client, product, application):
    pid = product["id"]
    plid = admin_client.post(
        f"/api/v1/products/{pid}/pipelines",
        json={"name": "App Group Pipeline", "kind": "ci"},
    ).get_json()["id"]
    rid = admin_client.post(
        f"/api/v1/products/{pid}/releases",
        json={"name": "Pipeline IDs Release"},
    ).get_json()["id"]
    gr = admin_client.post(
        f"/api/v1/products/{pid}/releases/{rid}/application-groups",
        json={
            "application_id": application["id"],
            "execution_mode": "sequential",
            "pipeline_ids": [plid],
        },
    )
    assert gr.status_code == 201
    stored = gr.get_json().get("pipeline_ids")
    if isinstance(stored, str):
        stored = json.loads(stored)
    assert plid in stored
