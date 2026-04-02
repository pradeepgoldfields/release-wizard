"""Unit tests for the Product Backlog endpoints.

Tests exercise the full REST API:
  GET    /api/v1/products/<id>/backlog
  POST   /api/v1/products/<id>/backlog
  GET    /api/v1/products/<id>/backlog/<item_id>
  PUT    /api/v1/products/<id>/backlog/<item_id>
  DELETE /api/v1/products/<id>/backlog/<item_id>
  PATCH  /api/v1/products/<id>/backlog/<item_id>/status
"""

from __future__ import annotations

import pytest

# ── helpers ────────────────────────────────────────────────────────────────────


@pytest.fixture()
def product(admin_client):
    r = admin_client.post("/api/v1/products", json={"name": "Backlog Test Product"})
    assert r.status_code == 201
    return r.get_json()


@pytest.fixture()
def backlog_item(admin_client, product):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/backlog",
        json={
            "title": "Sample backlog item",
            "description": "A test item",
            "item_type": "feature",
            "status": "open",
            "priority": "medium",
            "effort": 3,
            "labels": ["test", "backend"],
            "acceptance_criteria": "Must pass all tests.",
        },
    )
    assert r.status_code == 201
    return r.get_json()


# ── LIST ────────────────────────────────────────────────────────────────────────


def test_list_backlog_empty(admin_client, product):
    r = admin_client.get(f"/api/v1/products/{product['id']}/backlog")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 0
    assert data["items"] == []


def test_list_backlog_returns_created_items(admin_client, product, backlog_item):
    r = admin_client.get(f"/api/v1/products/{product['id']}/backlog")
    assert r.status_code == 200
    data = r.get_json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == backlog_item["id"]


def test_list_backlog_filter_by_status(admin_client, product):
    pid = product["id"]
    base = f"/api/v1/products/{pid}/backlog"

    admin_client.post(base, json={"title": "Open item", "status": "open"})
    admin_client.post(base, json={"title": "Done item", "status": "done"})

    r = admin_client.get(f"{base}?status=open")
    assert r.status_code == 200
    data = r.get_json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "open"


def test_list_backlog_filter_by_priority(admin_client, product):
    pid = product["id"]
    base = f"/api/v1/products/{pid}/backlog"

    admin_client.post(base, json={"title": "Critical bug", "priority": "critical"})
    admin_client.post(base, json={"title": "Low priority chore", "priority": "low"})

    r = admin_client.get(f"{base}?priority=critical")
    assert r.status_code == 200
    data = r.get_json()
    assert data["total"] == 1
    assert data["items"][0]["priority"] == "critical"


def test_list_backlog_filter_by_item_type(admin_client, product):
    pid = product["id"]
    base = f"/api/v1/products/{pid}/backlog"

    admin_client.post(base, json={"title": "A bug", "item_type": "bug"})
    admin_client.post(base, json={"title": "A feature", "item_type": "feature"})
    admin_client.post(base, json={"title": "A chore", "item_type": "chore"})

    r = admin_client.get(f"{base}?item_type=bug")
    data = r.get_json()
    assert data["total"] == 1
    assert data["items"][0]["item_type"] == "bug"


def test_list_backlog_search_by_title(admin_client, product):
    pid = product["id"]
    base = f"/api/v1/products/{pid}/backlog"

    admin_client.post(base, json={"title": "Implement OAuth login"})
    admin_client.post(base, json={"title": "Fix memory leak"})

    r = admin_client.get(f"{base}?q=oauth")
    data = r.get_json()
    assert data["total"] == 1
    assert "OAuth" in data["items"][0]["title"]


def test_list_backlog_isolated_per_product(admin_client, product):
    other = admin_client.post("/api/v1/products", json={"name": "Other Product"}).get_json()

    admin_client.post(
        f"/api/v1/products/{product['id']}/backlog", json={"title": "Item for product 1"}
    )
    admin_client.post(
        f"/api/v1/products/{other['id']}/backlog", json={"title": "Item for product 2"}
    )

    r1 = admin_client.get(f"/api/v1/products/{product['id']}/backlog").get_json()
    r2 = admin_client.get(f"/api/v1/products/{other['id']}/backlog").get_json()

    assert r1["total"] == 1
    assert r2["total"] == 1
    assert r1["items"][0]["title"] != r2["items"][0]["title"]


# ── CREATE ──────────────────────────────────────────────────────────────────────


def test_create_backlog_item_minimal(admin_client, product):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/backlog",
        json={"title": "Minimal item"},
    )
    assert r.status_code == 201
    data = r.get_json()
    assert data["title"] == "Minimal item"
    assert data["status"] == "open"
    assert data["priority"] == "medium"
    assert data["item_type"] == "feature"
    assert data["effort"] == 0
    assert data["labels"] == []


def test_create_backlog_item_full(admin_client, product):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/backlog",
        json={
            "title": "Full item",
            "description": "Full description",
            "item_type": "bug",
            "status": "in_progress",
            "priority": "high",
            "effort": 8,
            "labels": ["urgent", "backend"],
            "acceptance_criteria": "All tests green.",
            "notes": "See Jira ticket 123.",
        },
    )
    assert r.status_code == 201
    data = r.get_json()
    assert data["item_type"] == "bug"
    assert data["status"] == "in_progress"
    assert data["priority"] == "high"
    assert data["effort"] == 8
    assert data["labels"] == ["urgent", "backend"]
    assert data["acceptance_criteria"] == "All tests green."
    assert data["notes"] == "See Jira ticket 123."


def test_create_backlog_item_missing_title(admin_client, product):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/backlog",
        json={"description": "No title provided"},
    )
    assert r.status_code == 400
    assert "title" in r.get_json().get("error", "").lower()


def test_create_backlog_item_has_id_and_product_id(admin_client, product):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/backlog",
        json={"title": "Check ID fields"},
    )
    assert r.status_code == 201
    data = r.get_json()
    assert data["id"].startswith("backlog_")
    assert data["product_id"] == product["id"]
    assert data["created_at"] is not None


# ── GET single ──────────────────────────────────────────────────────────────────


def test_get_backlog_item(admin_client, product, backlog_item):
    r = admin_client.get(f"/api/v1/products/{product['id']}/backlog/{backlog_item['id']}")
    assert r.status_code == 200
    data = r.get_json()
    assert data["id"] == backlog_item["id"]
    assert data["title"] == backlog_item["title"]


def test_get_backlog_item_not_found(admin_client, product):
    r = admin_client.get(f"/api/v1/products/{product['id']}/backlog/backlog_nonexistent")
    assert r.status_code == 404


def test_get_backlog_item_wrong_product(admin_client, product):
    other = admin_client.post("/api/v1/products", json={"name": "Other"}).get_json()
    item = admin_client.post(
        f"/api/v1/products/{other['id']}/backlog", json={"title": "Other product item"}
    ).get_json()

    # Try to fetch item via wrong product
    r = admin_client.get(f"/api/v1/products/{product['id']}/backlog/{item['id']}")
    assert r.status_code == 404


# ── UPDATE ──────────────────────────────────────────────────────────────────────


def test_update_backlog_item_title(admin_client, product, backlog_item):
    r = admin_client.put(
        f"/api/v1/products/{product['id']}/backlog/{backlog_item['id']}",
        json={"title": "Updated title"},
    )
    assert r.status_code == 200
    assert r.get_json()["title"] == "Updated title"


def test_update_backlog_item_multiple_fields(admin_client, product, backlog_item):
    r = admin_client.put(
        f"/api/v1/products/{product['id']}/backlog/{backlog_item['id']}",
        json={
            "priority": "critical",
            "effort": 13,
            "labels": ["hotfix"],
            "status": "in_progress",
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["priority"] == "critical"
    assert data["effort"] == 13
    assert data["labels"] == ["hotfix"]
    assert data["status"] == "in_progress"


def test_update_backlog_item_not_found(admin_client, product):
    r = admin_client.put(
        f"/api/v1/products/{product['id']}/backlog/backlog_ghost",
        json={"title": "Ghost update"},
    )
    assert r.status_code == 404


# ── PATCH status ────────────────────────────────────────────────────────────────


def test_patch_status_to_done(admin_client, product, backlog_item):
    r = admin_client.patch(
        f"/api/v1/products/{product['id']}/backlog/{backlog_item['id']}/status",
        json={"status": "done"},
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "done"


def test_patch_status_cycle(admin_client, product, backlog_item):
    base = f"/api/v1/products/{product['id']}/backlog/{backlog_item['id']}/status"
    for status in ("in_progress", "done", "cancelled", "open"):
        r = admin_client.patch(base, json={"status": status})
        assert r.status_code == 200
        assert r.get_json()["status"] == status


def test_patch_status_missing_body(admin_client, product, backlog_item):
    r = admin_client.patch(
        f"/api/v1/products/{product['id']}/backlog/{backlog_item['id']}/status",
        json={},
    )
    assert r.status_code == 400


def test_patch_status_not_found(admin_client, product):
    r = admin_client.patch(
        f"/api/v1/products/{product['id']}/backlog/backlog_ghost/status",
        json={"status": "done"},
    )
    assert r.status_code == 404


# ── DELETE ──────────────────────────────────────────────────────────────────────


def test_delete_backlog_item(admin_client, product, backlog_item):
    r = admin_client.delete(f"/api/v1/products/{product['id']}/backlog/{backlog_item['id']}")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    # Confirm it's gone
    r2 = admin_client.get(f"/api/v1/products/{product['id']}/backlog/{backlog_item['id']}")
    assert r2.status_code == 404


def test_delete_backlog_item_not_found(admin_client, product):
    r = admin_client.delete(f"/api/v1/products/{product['id']}/backlog/backlog_ghost")
    assert r.status_code == 404


def test_delete_reduces_total(admin_client, product):
    pid = product["id"]
    base = f"/api/v1/products/{pid}/backlog"

    i1 = admin_client.post(base, json={"title": "Item 1"}).get_json()
    i2 = admin_client.post(base, json={"title": "Item 2"}).get_json()

    assert admin_client.get(base).get_json()["total"] == 2

    admin_client.delete(f"{base}/{i1['id']}")
    assert admin_client.get(base).get_json()["total"] == 1

    admin_client.delete(f"{base}/{i2['id']}")
    assert admin_client.get(base).get_json()["total"] == 0


# ── AUTH ────────────────────────────────────────────────────────────────────────


def test_backlog_requires_auth(product):
    """Unauthenticated request must return 401."""
    from app import create_app
    from app.config import TestConfig
    from app.extensions import db as _db

    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        c = application.test_client()
        r = c.get(f"/api/v1/products/{product['id']}/backlog")
        assert r.status_code == 401
        _db.drop_all()
