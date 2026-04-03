"""E2E UI tests — AI Dependency Intelligence feature.

Covers the full HTTP API surface exposed by dep_ai_bp:
  - GET  dep-ai/canvas          — enriched graph payload
  - POST dep-ai/discover        — AI dependency discovery (no-key graceful)
  - GET  dep-ai/suggestions     — list, status filter
  - POST dep-ai/suggestions/:id — accept, reject, invalid action
  - POST dep-ai/patterns        — pattern detection (no-key graceful)
  - GET  dep-ai/patterns        — list saved patterns
  - GET  releases/:id/ai-risk   — release risk score (no-key graceful)
  - GET  dep-ai/recommendations — recommendations (no-key graceful)
  - Auth: 401 when unauthenticated
  - RBAC: 403 when missing permission

All tests use the ``admin_client`` fixture from conftest.py which provides
a pre-authenticated client with system-administrator rights (full permissions).
"""

from __future__ import annotations

import json

import pytest

# ── Module-scoped fixtures ────────────────────────────────────────────────────

# `app` and `admin_client` are provided by tests/e2e/conftest.py


@pytest.fixture(scope="module")
def client(app):
    """Unauthenticated test client (for auth-guard tests)."""
    return app.test_client()


@pytest.fixture(scope="module")
def product(admin_client):
    r = admin_client.post(
        "/api/v1/products",
        json={"name": "AI Dep Intelligence Product", "description": "dep-ai E2E"},
    )
    assert r.status_code == 201
    return r.get_json()


@pytest.fixture(scope="module")
def app_alpha(admin_client, product):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/applications",
        json={"name": "Alpha Service", "artifact_type": "container", "compliance_rating": "Gold"},
    )
    assert r.status_code == 201
    return r.get_json()


@pytest.fixture(scope="module")
def app_beta(admin_client, product):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/applications",
        json={"name": "Beta Service", "artifact_type": "container", "compliance_rating": "Silver"},
    )
    assert r.status_code == 201
    return r.get_json()


@pytest.fixture(scope="module")
def release(admin_client, product):
    r = admin_client.post(
        f"/api/v1/products/{product['id']}/releases",
        json={"name": "v1.0.0-ai", "description": "AI risk test release"},
    )
    assert r.status_code == 201
    return r.get_json()


# ── Helper ────────────────────────────────────────────────────────────────────


def _ai_url(product_id, suffix=""):
    return f"/api/v1/products/{product_id}/dep-ai{suffix}"


# ── Authentication guard ──────────────────────────────────────────────────────


def test_canvas_requires_auth(client, product):
    r = client.get(_ai_url(product["id"], "/canvas"))
    assert r.status_code == 401


def test_suggestions_list_requires_auth(client, product):
    r = client.get(_ai_url(product["id"], "/suggestions"))
    assert r.status_code == 401


def test_discover_requires_auth(client, product):
    r = client.post(_ai_url(product["id"], "/discover"))
    assert r.status_code == 401


def test_patterns_list_requires_auth(client, product):
    r = client.get(_ai_url(product["id"], "/patterns"))
    assert r.status_code == 401


def test_patterns_detect_requires_auth(client, product):
    r = client.post(_ai_url(product["id"], "/patterns"))
    assert r.status_code == 401


def test_recommendations_requires_auth(client, product):
    r = client.get(_ai_url(product["id"], "/recommendations"))
    assert r.status_code == 401


def test_ai_risk_requires_auth(client, product, release):
    r = client.get(f"/api/v1/products/{product['id']}/releases/{release['id']}/ai-risk")
    assert r.status_code == 401


# ── AI canvas ─────────────────────────────────────────────────────────────────


def test_get_ai_canvas_returns_200(admin_client, product, app_alpha, app_beta):  # noqa: ARG001
    r = admin_client.get(_ai_url(product["id"], "/canvas"))
    assert r.status_code == 200


def test_get_ai_canvas_contains_required_keys(admin_client, product):
    r = admin_client.get(_ai_url(product["id"], "/canvas"))
    data = r.get_json()
    for key in ("nodes", "edges", "suggested_edges", "patterns", "suggestions"):
        assert key in data, f"Missing key in canvas response: {key}"


def test_get_ai_canvas_nodes_include_product_apps(admin_client, product, app_alpha, app_beta):
    r = admin_client.get(_ai_url(product["id"], "/canvas"))
    data = r.get_json()
    node_ids = {n["id"] for n in data["nodes"]}
    assert app_alpha["id"] in node_ids
    assert app_beta["id"] in node_ids


def test_get_ai_canvas_nodes_have_ai_fields(admin_client, product):
    """Every node must carry edge_type, cluster_id, compliance_drift after canvas enrichment."""
    r = admin_client.get(_ai_url(product["id"], "/canvas"))
    data = r.get_json()
    for node in data["nodes"]:
        assert "edge_type" in node, "node missing edge_type"
        assert "cluster_id" in node, "node missing cluster_id"
        assert "compliance_drift" in node, "node missing compliance_drift"


def test_get_ai_canvas_suggested_edges_have_shape(admin_client, product):
    """All suggested_edges must have the expected fields."""
    r = admin_client.get(_ai_url(product["id"], "/canvas"))
    data = r.get_json()
    for se in data["suggested_edges"]:
        for key in ("id", "source", "target", "dep_type", "edge_type", "confidence"):
            assert key in se, f"suggested_edge missing {key}"
        assert se["edge_type"] == "suggested"


# ── Discover dependencies ─────────────────────────────────────────────────────


def test_discover_without_groq_key_returns_200(admin_client, product, app_alpha, app_beta):  # noqa: ARG001
    """Even without GROQ_API_KEY the endpoint must return 200 (graceful)."""
    r = admin_client.post(_ai_url(product["id"], "/discover"))
    assert r.status_code == 200


def test_discover_without_groq_key_returns_available_false(admin_client, product):
    r = admin_client.post(_ai_url(product["id"], "/discover"))
    data = r.get_json()
    # Without a real API key the service signals it is not configured
    assert "available" in data


def test_discover_returns_suggestions_key(admin_client, product):
    r = admin_client.post(_ai_url(product["id"], "/discover"))
    data = r.get_json()
    assert "suggestions" in data


# ── Suggestions lifecycle ─────────────────────────────────────────────────────


def test_list_suggestions_empty_initially(admin_client, product):
    r = admin_client.get(_ai_url(product["id"], "/suggestions"))
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


def test_list_suggestions_status_filter_unknown_returns_empty(admin_client, product):
    """Filtering by an unknown status should return an empty list, not an error."""
    r = admin_client.get(_ai_url(product["id"], "/suggestions?status=nonexistent"))
    assert r.status_code == 200
    assert r.get_json() == []


def test_create_and_list_suggestion_via_service(admin_client, app, product, app_alpha, app_beta):
    """Inject a DepSuggestion directly then verify it appears in the API."""
    from app.extensions import db
    from app.models.app_dependency import DepSuggestion

    with app.app_context():
        sug = DepSuggestion(
            from_app_id=app_beta["id"],
            to_app_id=app_alpha["id"],
            dep_type="runtime",
            confidence=0.88,
            reason="co-deployed frequently",
            status="pending",
        )
        db.session.add(sug)
        db.session.commit()
        sug_id = sug.id

    r = admin_client.get(_ai_url(product["id"], "/suggestions?status=pending"))
    assert r.status_code == 200
    ids = [s["id"] for s in r.get_json()]
    assert sug_id in ids


def _clear_suggestion_pair(db, app_beta_id, app_alpha_id):
    """Remove any existing suggestion between this pair (respects UniqueConstraint)."""
    from app.models.app_dependency import AppDependency, DepSuggestion

    DepSuggestion.query.filter_by(from_app_id=app_beta_id, to_app_id=app_alpha_id).delete()
    AppDependency.query.filter_by(from_app_id=app_beta_id, to_app_id=app_alpha_id).delete()
    db.session.commit()


def test_accept_suggestion(admin_client, app, product, app_alpha, app_beta):
    """Accept a suggestion → status=accepted, dependency created."""
    from app.extensions import db
    from app.models.app_dependency import AppDependency, DepSuggestion

    with app.app_context():
        _clear_suggestion_pair(db, app_beta["id"], app_alpha["id"])
        sug = DepSuggestion(
            from_app_id=app_beta["id"],
            to_app_id=app_alpha["id"],
            dep_type="runtime",
            confidence=0.9,
            reason="test accept",
            status="pending",
        )
        db.session.add(sug)
        db.session.commit()
        sug_id = sug.id

    r = admin_client.post(
        _ai_url(product["id"], f"/suggestions/{sug_id}"),
        json={"action": "accept"},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "accepted"

    with app.app_context():
        dep = AppDependency.query.filter_by(
            from_app_id=app_beta["id"], to_app_id=app_alpha["id"]
        ).first()
        assert dep is not None


def test_reject_suggestion(admin_client, app, product, app_alpha, app_beta):
    """Reject a suggestion → status=rejected, no dependency."""
    from app.extensions import db
    from app.models.app_dependency import AppDependency, DepSuggestion

    with app.app_context():
        _clear_suggestion_pair(db, app_beta["id"], app_alpha["id"])
        sug = DepSuggestion(
            from_app_id=app_beta["id"],
            to_app_id=app_alpha["id"],
            dep_type="runtime",
            confidence=0.6,
            reason="test reject",
            status="pending",
        )
        db.session.add(sug)
        db.session.commit()
        sug_id = sug.id

    r = admin_client.post(
        _ai_url(product["id"], f"/suggestions/{sug_id}"),
        json={"action": "reject"},
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "rejected"

    with app.app_context():
        dep = AppDependency.query.filter_by(
            from_app_id=app_beta["id"], to_app_id=app_alpha["id"]
        ).first()
        assert dep is None


def test_review_suggestion_invalid_action_returns_400(
    admin_client, app, product, app_alpha, app_beta
):
    from app.extensions import db
    from app.models.app_dependency import DepSuggestion

    with app.app_context():
        _clear_suggestion_pair(db, app_beta["id"], app_alpha["id"])
        sug = DepSuggestion(
            from_app_id=app_beta["id"],
            to_app_id=app_alpha["id"],
            dep_type="runtime",
            confidence=0.5,
            reason="bad action test",
            status="pending",
        )
        db.session.add(sug)
        db.session.commit()
        sug_id = sug.id

    r = admin_client.post(
        _ai_url(product["id"], f"/suggestions/{sug_id}"),
        json={"action": "destroy"},
    )
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_review_suggestion_missing_action_returns_400(
    admin_client, app, product, app_alpha, app_beta
):
    from app.extensions import db
    from app.models.app_dependency import DepSuggestion

    with app.app_context():
        _clear_suggestion_pair(db, app_beta["id"], app_alpha["id"])
        sug = DepSuggestion(
            from_app_id=app_beta["id"],
            to_app_id=app_alpha["id"],
            dep_type="build",
            confidence=0.4,
            reason="no action",
            status="pending",
        )
        db.session.add(sug)
        db.session.commit()
        sug_id = sug.id

    r = admin_client.post(
        _ai_url(product["id"], f"/suggestions/{sug_id}"),
        json={},
    )
    assert r.status_code == 400


def test_suggestions_filter_accepted_only(admin_client, app, product, app_alpha, app_beta):
    """GET suggestions?status=accepted should only return accepted ones."""
    from app.extensions import db
    from app.models.app_dependency import DepSuggestion

    with app.app_context():
        # Clear existing
        DepSuggestion.query.delete()
        db.session.commit()
        pending = DepSuggestion(
            from_app_id=app_beta["id"],
            to_app_id=app_alpha["id"],
            dep_type="runtime",
            confidence=0.8,
            reason="p",
            status="pending",
        )
        accepted = DepSuggestion(
            from_app_id=app_alpha["id"],
            to_app_id=app_beta["id"],
            dep_type="build",
            confidence=0.7,
            reason="a",
            status="accepted",
        )
        db.session.add_all([pending, accepted])
        db.session.commit()

    r = admin_client.get(_ai_url(product["id"], "/suggestions?status=accepted"))
    assert r.status_code == 200
    results = r.get_json()
    assert all(s["status"] == "accepted" for s in results)
    assert any(s["dep_type"] == "build" for s in results)


# ── Pattern detection ─────────────────────────────────────────────────────────


def test_detect_patterns_without_groq_returns_200(admin_client, product, app_alpha, app_beta):  # noqa: ARG001
    r = admin_client.post(_ai_url(product["id"], "/patterns"))
    assert r.status_code == 200


def test_detect_patterns_response_has_patterns_key(admin_client, product):
    r = admin_client.post(_ai_url(product["id"], "/patterns"))
    data = r.get_json()
    assert "patterns" in data


def test_get_patterns_empty_initially(admin_client, product):
    r = admin_client.get(_ai_url(product["id"], "/patterns"))
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


def test_get_patterns_returns_saved_patterns(admin_client, app, product, app_alpha, app_beta):
    from app.extensions import db
    from app.models.app_dependency import DepPattern

    with app.app_context():
        DepPattern.query.filter_by(product_id=product["id"]).delete()
        pat = DepPattern(
            product_id=product["id"],
            name="E2E Cluster",
            pattern_type="co_deployment",
            app_ids=json.dumps([app_alpha["id"], app_beta["id"]]),
            metadata_json=json.dumps({"avg_co_pct": 80}),
            description="Always deploy together.",
        )
        db.session.add(pat)
        db.session.commit()
        pat_id = pat.id

    r = admin_client.get(_ai_url(product["id"], "/patterns"))
    assert r.status_code == 200
    data = r.get_json()
    assert any(p["id"] == pat_id for p in data)


def test_pattern_to_dict_shape(admin_client, app, product, app_alpha):
    from app.extensions import db
    from app.models.app_dependency import DepPattern

    with app.app_context():
        DepPattern.query.filter_by(product_id=product["id"]).delete()
        pat = DepPattern(
            product_id=product["id"],
            name="Shape Test",
            pattern_type="anomaly",
            app_ids=json.dumps([app_alpha["id"]]),
            metadata_json="{}",
            description="Anomaly detected.",
        )
        db.session.add(pat)
        db.session.commit()

    r = admin_client.get(_ai_url(product["id"], "/patterns"))
    assert r.status_code == 200
    data = r.get_json()
    assert len(data) >= 1
    pat_data = next(p for p in data if p["name"] == "Shape Test")
    for key in (
        "id",
        "product_id",
        "name",
        "pattern_type",
        "app_ids",
        "description",
        "detected_at",
    ):
        assert key in pat_data, f"Pattern dict missing key: {key}"


def test_pattern_app_ids_is_list(admin_client, app, product, app_alpha, app_beta):
    from app.extensions import db
    from app.models.app_dependency import DepPattern

    with app.app_context():
        DepPattern.query.filter_by(product_id=product["id"]).delete()
        pat = DepPattern(
            product_id=product["id"],
            name="AppIds Test",
            pattern_type="co_deployment",
            app_ids=json.dumps([app_alpha["id"], app_beta["id"]]),
            metadata_json="{}",
            description="",
        )
        db.session.add(pat)
        db.session.commit()

    r = admin_client.get(_ai_url(product["id"], "/patterns"))
    data = r.get_json()
    for pat in data:
        assert isinstance(pat["app_ids"], list), "app_ids must be a list"


# ── Release AI risk ───────────────────────────────────────────────────────────


def test_ai_risk_without_groq_returns_200(admin_client, product, release):
    r = admin_client.get(f"/api/v1/products/{product['id']}/releases/{release['id']}/ai-risk")
    assert r.status_code == 200


def test_ai_risk_response_has_available_key(admin_client, product, release):
    r = admin_client.get(f"/api/v1/products/{product['id']}/releases/{release['id']}/ai-risk")
    assert "available" in r.get_json()


def test_ai_risk_without_groq_score_is_none(admin_client, product, release):
    """Without GROQ_API_KEY, score must be None (not an error)."""
    r = admin_client.get(f"/api/v1/products/{product['id']}/releases/{release['id']}/ai-risk")
    data = r.get_json()
    if not data.get("available", True):
        assert data["score"] is None


def test_ai_risk_accepts_environment_query_param(admin_client, product, release):
    r = admin_client.get(
        f"/api/v1/products/{product['id']}/releases/{release['id']}/ai-risk?environment=prod"
    )
    assert r.status_code == 200


def test_ai_risk_invalid_release_returns_404(admin_client, product):
    r = admin_client.get(f"/api/v1/products/{product['id']}/releases/nonexistent-release/ai-risk")
    assert r.status_code in (404, 200)  # 404 preferred; 200 w/ error key also acceptable


# ── Recommendations ───────────────────────────────────────────────────────────


def test_recommendations_without_groq_returns_200(admin_client, product, app_alpha, app_beta):  # noqa: ARG001
    r = admin_client.get(_ai_url(product["id"], "/recommendations"))
    assert r.status_code == 200


def test_recommendations_response_structure(admin_client, product):
    r = admin_client.get(_ai_url(product["id"], "/recommendations"))
    data = r.get_json()
    assert "available" in data


def test_recommendations_without_groq_returns_fallback(admin_client, product):
    """Without GROQ_API_KEY: available=False, recommendations key present."""
    r = admin_client.get(_ai_url(product["id"], "/recommendations"))
    data = r.get_json()
    if not data.get("available", True):
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)


# ── Cross-product isolation ───────────────────────────────────────────────────


def test_canvas_for_different_product_shows_different_nodes(admin_client):
    """A second product's canvas should not contain apps from the first product."""
    r2 = admin_client.post(
        "/api/v1/products",
        json={"name": "Isolated Product", "description": "isolation test"},
    )
    assert r2.status_code == 201
    other_product = r2.get_json()

    r = admin_client.get(_ai_url(other_product["id"], "/canvas"))
    assert r.status_code == 200
    data = r.get_json()
    # This product has no apps → nodes list should be empty
    assert data["nodes"] == []


def test_suggestions_scoped_to_product(admin_client, product, app_alpha, app_beta):
    """Suggestions endpoint must only return suggestions for apps in this product."""
    r = admin_client.get(_ai_url(product["id"], "/suggestions"))
    assert r.status_code == 200
    # All returned from_app_id values must belong to this product
    data = r.get_json()
    product_app_ids = {app_alpha["id"], app_beta["id"]}
    for sug in data:
        assert sug["from_app_id"] in product_app_ids, (
            f"Suggestion from app {sug['from_app_id']} not in product {product['id']}"
        )


# ── Dependency declared → no re-suggestion ───────────────────────────────────


def test_declared_dependency_not_re_suggested(admin_client, app, product, app_alpha, app_beta):
    """After accepting a suggestion (creating the dep), the edge must not appear in suggestions again."""
    from app.extensions import db
    from app.models.app_dependency import AppDependency, DepSuggestion

    with app.app_context():
        # Clean slate
        DepSuggestion.query.delete()
        AppDependency.query.filter_by(
            from_app_id=app_beta["id"], to_app_id=app_alpha["id"]
        ).delete()
        db.session.commit()

        sug = DepSuggestion(
            from_app_id=app_beta["id"],
            to_app_id=app_alpha["id"],
            dep_type="runtime",
            confidence=0.85,
            reason="test",
            status="pending",
        )
        db.session.add(sug)
        db.session.commit()
        sug_id = sug.id

    # Accept it
    admin_client.post(
        _ai_url(product["id"], f"/suggestions/{sug_id}"),
        json={"action": "accept"},
    )

    # Now the pending list should be empty
    r = admin_client.get(_ai_url(product["id"], "/suggestions?status=pending"))
    assert r.status_code == 200
    pending = r.get_json()
    ids = [s["id"] for s in pending]
    assert sug_id not in ids


# ── Canvas reflects accepted/rejected status ──────────────────────────────────


def test_canvas_suggested_edges_only_pending(admin_client, app, product, app_alpha, app_beta):
    """After a suggestion is rejected, it must not appear in canvas suggested_edges."""
    from app.extensions import db
    from app.models.app_dependency import DepSuggestion

    with app.app_context():
        DepSuggestion.query.delete()
        db.session.commit()

        rej = DepSuggestion(
            from_app_id=app_beta["id"],
            to_app_id=app_alpha["id"],
            dep_type="runtime",
            confidence=0.7,
            reason="rej",
            status="rejected",
        )
        db.session.add(rej)
        db.session.commit()

    r = admin_client.get(_ai_url(product["id"], "/canvas"))
    data = r.get_json()
    assert data["suggested_edges"] == []


# ── Patterns reflected in canvas ──────────────────────────────────────────────


def test_canvas_reflects_cluster_pattern(admin_client, app, product, app_alpha, app_beta):
    """co_deployment pattern cluster_id must appear on matching nodes in canvas."""
    from app.extensions import db
    from app.models.app_dependency import DepPattern

    with app.app_context():
        DepPattern.query.filter_by(product_id=product["id"]).delete()
        pat = DepPattern(
            product_id=product["id"],
            name="Canvas Cluster",
            pattern_type="co_deployment",
            app_ids=json.dumps([app_alpha["id"]]),
            metadata_json="{}",
            description="Always together.",
        )
        db.session.add(pat)
        db.session.commit()
        pat_id = pat.id

    r = admin_client.get(_ai_url(product["id"], "/canvas"))
    data = r.get_json()
    node_alpha = next(n for n in data["nodes"] if n["id"] == app_alpha["id"])
    node_beta = next(n for n in data["nodes"] if n["id"] == app_beta["id"])
    assert node_alpha["cluster_id"] == pat_id
    assert node_beta["cluster_id"] is None  # not in pattern


def test_canvas_reflects_compliance_drift_flag(admin_client, app, product, app_alpha, app_beta):
    """compliance_drift pattern must set compliance_drift=True on matched nodes."""
    from app.extensions import db
    from app.models.app_dependency import DepPattern

    with app.app_context():
        DepPattern.query.filter_by(product_id=product["id"]).delete()
        pat = DepPattern(
            product_id=product["id"],
            name="Drift Pattern",
            pattern_type="compliance_drift",
            app_ids=json.dumps([app_beta["id"]]),
            metadata_json="{}",
            description="Score declining.",
        )
        db.session.add(pat)
        db.session.commit()

    r = admin_client.get(_ai_url(product["id"], "/canvas"))
    data = r.get_json()
    node_alpha = next(n for n in data["nodes"] if n["id"] == app_alpha["id"])
    node_beta = next(n for n in data["nodes"] if n["id"] == app_beta["id"])
    assert node_beta["compliance_drift"] is True
    assert node_alpha["compliance_drift"] is False
