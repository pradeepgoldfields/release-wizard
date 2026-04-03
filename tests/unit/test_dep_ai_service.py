"""Unit tests for dep_ai_service — AI dependency intelligence.

All Groq calls are mocked so tests run without a real API key.
Covers:
  - Graceful fallback when GROQ_API_KEY is absent
  - _collect_cooccurrence: returns empty dict for empty product
  - discover_dependencies: no-key fallback, empty history, Groq mock path
  - accept_suggestion: creates AppDependency and marks suggestion accepted
  - reject_suggestion: marks rejected, idempotent status
  - list_suggestions: filters by status and product
  - detect_patterns: no-key fallback, saves and replaces DepPattern rows
  - score_release_risk: no-key fallback, shape of returned dict
  - get_ai_canvas_data: merges confirmed edges + pending suggestions + patterns
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db
from app.models.app_dependency import AppDependency, DepPattern, DepSuggestion
from app.models.application import ApplicationArtifact
from app.models.product import Product
from app.services import resource_id

# ── Shared fixtures ───────────────────────────────────────────────────────────


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture()
def product(app):
    with app.app_context():
        p = Product(id=resource_id("prod"), name="AI Test Product", description="dep ai tests")
        _db.session.add(p)
        _db.session.commit()
        return p.id


@pytest.fixture()
def two_apps(app, product):
    """Two applications: alpha (provider) and beta (consumer)."""
    with app.app_context():
        alpha = ApplicationArtifact(
            id=resource_id("app"),
            product_id=product,
            name="Alpha Service",
            compliance_rating="Gold",
        )
        beta = ApplicationArtifact(
            id=resource_id("app"),
            product_id=product,
            name="Beta Service",
            compliance_rating="Silver",
        )
        _db.session.add_all([alpha, beta])
        _db.session.commit()
        return {"alpha": alpha.id, "beta": beta.id}


@pytest.fixture()
def pending_suggestion(app, two_apps):
    """A pending DepSuggestion from beta → alpha."""
    with app.app_context():
        sug = DepSuggestion(
            from_app_id=two_apps["beta"],
            to_app_id=two_apps["alpha"],
            dep_type="runtime",
            confidence=0.85,
            reason="Co-deployed in 12/15 runs",
            status="pending",
        )
        _db.session.add(sug)
        _db.session.commit()
        return sug.id


# ── Groq availability / graceful fallback ─────────────────────────────────────


def test_discover_no_groq_key_returns_fallback(app, product):
    """Without GROQ_API_KEY the service returns available=False without crashing."""
    with app.app_context():
        app.config["GROQ_API_KEY"] = ""
        from app.services.dep_ai_service import discover_dependencies

        result = discover_dependencies(product)
        assert result["available"] is False
        assert "GROQ_API_KEY" in result["reason"]
        assert "suggestions" in result


def test_detect_patterns_no_groq_key_returns_fallback(app, product):
    with app.app_context():
        app.config["GROQ_API_KEY"] = ""
        from app.services.dep_ai_service import detect_patterns

        result = detect_patterns(product)
        assert result["available"] is False
        assert "patterns" in result


def test_score_release_risk_no_groq_key_returns_fallback(app, product):
    """score_release_risk with no key should return available=False, score=None."""
    with app.app_context():
        app.config["GROQ_API_KEY"] = ""
        from app.services.dep_ai_service import score_release_risk

        result = score_release_risk("nonexistent-release-id")
        assert result["available"] is False
        assert result["score"] is None


def test_get_recommendations_no_groq_key_returns_fallback(app, product):
    with app.app_context():
        app.config["GROQ_API_KEY"] = ""
        from app.services.dep_ai_service import get_recommendations

        result = get_recommendations(product)
        assert result["available"] is False
        assert "recommendations" in result


# ── _collect_cooccurrence ─────────────────────────────────────────────────────


def test_collect_cooccurrence_empty_product(app, product):
    """No releases → pairs=[], total_release_runs=0."""
    with app.app_context():
        from app.services.dep_ai_service import _collect_cooccurrence

        data = _collect_cooccurrence(product)
        assert data["pairs"] == []
        assert data["total_release_runs"] == 0
        assert data["lookback_days"] == 90


def test_collect_cooccurrence_includes_app_names(app, two_apps, product):
    """Even with no runs, apps dict must reflect product apps."""
    with app.app_context():
        from app.services.dep_ai_service import _collect_cooccurrence

        data = _collect_cooccurrence(product)
        assert two_apps["alpha"] in data["apps"]
        assert two_apps["beta"] in data["apps"]
        assert data["apps"][two_apps["alpha"]] == "Alpha Service"


# ── discover_dependencies (mocked Groq) ───────────────────────────────────────


def test_discover_empty_history_skips_groq(app, product, two_apps):
    """If there are no co-deployment pairs, Groq is not called and we get a message."""
    with app.app_context():
        app.config["GROQ_API_KEY"] = "fake-key"
        with patch("app.services.dep_ai_service._call_groq") as mock_groq:
            from app.services.dep_ai_service import discover_dependencies

            result = discover_dependencies(product)
        mock_groq.assert_not_called()
        assert result["available"] is True
        assert result["suggestions"] == []


def test_discover_creates_suggestions_from_groq(app, product, two_apps):
    """Mocked Groq response creates DepSuggestion rows."""
    with app.app_context():
        app.config["GROQ_API_KEY"] = "fake-key"

        groq_payload = {
            "suggestions": [
                {
                    "from_app_id": two_apps["beta"],
                    "to_app_id": two_apps["alpha"],
                    "dep_type": "runtime",
                    "confidence": 0.9,
                    "reason": "Co-deployed in 90% of runs",
                }
            ]
        }

        with (
            patch("app.services.dep_ai_service._collect_cooccurrence") as mock_cooc,
            patch("app.services.dep_ai_service._call_groq", return_value=groq_payload),
        ):
            mock_cooc.return_value = {
                "pairs": [
                    {
                        "app_a": two_apps["alpha"],
                        "app_b": two_apps["beta"],
                        "count": 5,
                        "total_runs": 5,
                        "pct": 100.0,
                        "app_a_name": "Alpha Service",
                        "app_b_name": "Beta Service",
                    }
                ],
                "apps": {two_apps["alpha"]: "Alpha Service", two_apps["beta"]: "Beta Service"},
                "total_release_runs": 5,
                "lookback_days": 90,
            }
            from app.services.dep_ai_service import discover_dependencies

            result = discover_dependencies(product)

        assert result["available"] is True
        assert len(result["suggestions"]) == 1
        assert result["suggestions"][0]["dep_type"] == "runtime"
        assert result["suggestions"][0]["confidence"] == 0.9

        # Row must be persisted
        saved = DepSuggestion.query.filter_by(
            from_app_id=two_apps["beta"], to_app_id=two_apps["alpha"]
        ).first()
        assert saved is not None
        assert saved.status == "pending"


def test_discover_skips_self_references(app, product, two_apps):
    """Groq suggestions where from==to must be silently ignored."""
    with app.app_context():
        app.config["GROQ_API_KEY"] = "fake-key"
        groq_payload = {
            "suggestions": [
                {
                    "from_app_id": two_apps["alpha"],
                    "to_app_id": two_apps["alpha"],
                    "dep_type": "runtime",
                    "confidence": 0.9,
                    "reason": "self",
                },
            ]
        }
        with (
            patch("app.services.dep_ai_service._collect_cooccurrence") as mock_cooc,
            patch("app.services.dep_ai_service._call_groq", return_value=groq_payload),
        ):
            mock_cooc.return_value = {
                "pairs": [
                    {
                        "app_a": two_apps["alpha"],
                        "app_b": two_apps["beta"],
                        "count": 3,
                        "total_runs": 3,
                        "pct": 100.0,
                        "app_a_name": "Alpha",
                        "app_b_name": "Beta",
                    }
                ],
                "apps": {two_apps["alpha"]: "Alpha", two_apps["beta"]: "Beta"},
                "total_release_runs": 3,
                "lookback_days": 90,
            }
            from app.services.dep_ai_service import discover_dependencies

            result = discover_dependencies(product)
        assert result["suggestions"] == []
        assert DepSuggestion.query.count() == 0


def test_discover_skips_already_declared_edges(app, product, two_apps):
    """Edges already in AppDependency should not become suggestions."""
    with app.app_context():
        app.config["GROQ_API_KEY"] = "fake-key"
        # Declare the edge first
        dep = AppDependency(
            id=resource_id("dep"),
            from_app_id=two_apps["beta"],
            to_app_id=two_apps["alpha"],
            dep_type="runtime",
        )
        _db.session.add(dep)
        _db.session.commit()

        groq_payload = {
            "suggestions": [
                {
                    "from_app_id": two_apps["beta"],
                    "to_app_id": two_apps["alpha"],
                    "dep_type": "runtime",
                    "confidence": 0.9,
                    "reason": "already declared",
                },
            ]
        }
        with (
            patch("app.services.dep_ai_service._collect_cooccurrence") as mock_cooc,
            patch("app.services.dep_ai_service._call_groq", return_value=groq_payload),
        ):
            mock_cooc.return_value = {
                "pairs": [
                    {
                        "app_a": two_apps["alpha"],
                        "app_b": two_apps["beta"],
                        "count": 5,
                        "total_runs": 5,
                        "pct": 100.0,
                        "app_a_name": "Alpha",
                        "app_b_name": "Beta",
                    }
                ],
                "apps": {two_apps["alpha"]: "Alpha", two_apps["beta"]: "Beta"},
                "total_release_runs": 5,
                "lookback_days": 90,
            }
            from app.services.dep_ai_service import discover_dependencies

            result = discover_dependencies(product)
        assert result["suggestions"] == []


def test_discover_skips_rejected_suggestions(app, product, two_apps):
    """Previously rejected suggestions must not be re-created."""
    with app.app_context():
        app.config["GROQ_API_KEY"] = "fake-key"
        rej = DepSuggestion(
            from_app_id=two_apps["beta"],
            to_app_id=two_apps["alpha"],
            dep_type="runtime",
            confidence=0.8,
            reason="old",
            status="rejected",
        )
        _db.session.add(rej)
        _db.session.commit()

        groq_payload = {
            "suggestions": [
                {
                    "from_app_id": two_apps["beta"],
                    "to_app_id": two_apps["alpha"],
                    "dep_type": "runtime",
                    "confidence": 0.9,
                    "reason": "re-suggested",
                },
            ]
        }
        with (
            patch("app.services.dep_ai_service._collect_cooccurrence") as mock_cooc,
            patch("app.services.dep_ai_service._call_groq", return_value=groq_payload),
        ):
            mock_cooc.return_value = {
                "pairs": [
                    {
                        "app_a": two_apps["alpha"],
                        "app_b": two_apps["beta"],
                        "count": 5,
                        "total_runs": 5,
                        "pct": 100.0,
                        "app_a_name": "Alpha",
                        "app_b_name": "Beta",
                    }
                ],
                "apps": {two_apps["alpha"]: "Alpha", two_apps["beta"]: "Beta"},
                "total_release_runs": 5,
                "lookback_days": 90,
            }
            from app.services.dep_ai_service import discover_dependencies

            result = discover_dependencies(product)
        assert result["suggestions"] == []
        # Still only one row (the rejected one)
        assert DepSuggestion.query.count() == 1


def test_discover_groq_failure_returns_graceful_message(app, product, two_apps):
    """If _call_groq returns None (e.g. network error), return graceful dict."""
    with app.app_context():
        app.config["GROQ_API_KEY"] = "fake-key"
        with (
            patch("app.services.dep_ai_service._collect_cooccurrence") as mock_cooc,
            patch("app.services.dep_ai_service._call_groq", return_value=None),
        ):
            mock_cooc.return_value = {
                "pairs": [
                    {
                        "app_a": two_apps["alpha"],
                        "app_b": two_apps["beta"],
                        "count": 3,
                        "total_runs": 3,
                        "pct": 100.0,
                        "app_a_name": "Alpha",
                        "app_b_name": "Beta",
                    }
                ],
                "apps": {two_apps["alpha"]: "Alpha", two_apps["beta"]: "Beta"},
                "total_release_runs": 3,
                "lookback_days": 90,
            }
            from app.services.dep_ai_service import discover_dependencies

            result = discover_dependencies(product)
        assert result["available"] is True
        assert result["suggestions"] == []
        assert "message" in result


# ── accept_suggestion ─────────────────────────────────────────────────────────


def test_accept_suggestion_creates_dependency(app, two_apps, pending_suggestion):
    """Accepting a suggestion must create an AppDependency row."""
    with app.app_context():
        from app.services.dep_ai_service import accept_suggestion

        result = accept_suggestion(pending_suggestion, reviewed_by="alice")
        assert result["status"] == "accepted"
        assert result["reviewed_by"] == "alice"

        dep = AppDependency.query.filter_by(
            from_app_id=two_apps["beta"], to_app_id=two_apps["alpha"]
        ).first()
        assert dep is not None
        assert dep.dep_type == "runtime"


def test_accept_suggestion_contains_ai_note_in_description(app, two_apps, pending_suggestion):
    """Dependency description created by accept_suggestion should reference AI confidence."""
    with app.app_context():
        from app.services.dep_ai_service import accept_suggestion

        accept_suggestion(pending_suggestion, reviewed_by="alice")
        dep = AppDependency.query.filter_by(
            from_app_id=two_apps["beta"], to_app_id=two_apps["alpha"]
        ).first()
        assert "AI-suggested" in (dep.description or "")


def test_accept_already_accepted_returns_error(app, two_apps, pending_suggestion):
    """Accepting an already-accepted suggestion should return an error dict."""
    with app.app_context():
        from app.services.dep_ai_service import accept_suggestion

        accept_suggestion(pending_suggestion, reviewed_by="alice")
        result2 = accept_suggestion(pending_suggestion, reviewed_by="bob")
        assert "error" in result2


def test_accept_suggestion_idempotent_if_dep_exists(app, two_apps, pending_suggestion):
    """If the AppDependency already exists (edge case), accept should still mark accepted."""
    with app.app_context():
        # Pre-create the dependency to trigger the ValueError path
        existing_dep = AppDependency(
            id=resource_id("dep"),
            from_app_id=two_apps["beta"],
            to_app_id=two_apps["alpha"],
            dep_type="runtime",
        )
        _db.session.add(existing_dep)
        _db.session.commit()

        from app.services.dep_ai_service import accept_suggestion

        result = accept_suggestion(pending_suggestion, reviewed_by="alice")
        assert result["status"] == "accepted"


# ── reject_suggestion ─────────────────────────────────────────────────────────


def test_reject_suggestion_marks_rejected(app, two_apps, pending_suggestion):
    with app.app_context():
        from app.services.dep_ai_service import reject_suggestion

        result = reject_suggestion(pending_suggestion, reviewed_by="bob")
        assert result["status"] == "rejected"
        assert result["reviewed_by"] == "bob"
        assert result["reviewed_at"] is not None


def test_reject_suggestion_no_dependency_created(app, two_apps, pending_suggestion):
    """Rejecting must NOT create an AppDependency."""
    with app.app_context():
        from app.services.dep_ai_service import reject_suggestion

        reject_suggestion(pending_suggestion, reviewed_by="bob")
        assert AppDependency.query.count() == 0


# ── list_suggestions ──────────────────────────────────────────────────────────


def test_list_suggestions_all_statuses(app, product, two_apps, pending_suggestion):
    with app.app_context():
        # Add an accepted suggestion
        acc = DepSuggestion(
            from_app_id=two_apps["alpha"],
            to_app_id=two_apps["beta"],
            dep_type="build",
            confidence=0.7,
            reason="build dep",
            status="accepted",
        )
        _db.session.add(acc)
        _db.session.commit()

        from app.services.dep_ai_service import list_suggestions

        all_sugs = list_suggestions(product)
        assert len(all_sugs) == 2

        pending = list_suggestions(product, status="pending")
        assert all(s["status"] == "pending" for s in pending)

        accepted = list_suggestions(product, status="accepted")
        assert all(s["status"] == "accepted" for s in accepted)


def test_list_suggestions_scoped_to_product(app, product, two_apps, pending_suggestion):
    """Suggestions for apps in another product must not appear."""
    with app.app_context():
        other_product = Product(id=resource_id("prod"), name="Other Product", description="")
        other_app = ApplicationArtifact(
            id=resource_id("app"),
            product_id=other_product.id,
            name="Other App",
            compliance_rating="Gold",
        )
        _db.session.add_all([other_product, other_app])
        _db.session.commit()

        # Suggestion for an app in other_product
        other_sug = DepSuggestion(
            from_app_id=other_app.id,
            to_app_id=two_apps["alpha"],  # to_app is in first product — edge case
            dep_type="runtime",
            confidence=0.6,
            reason="cross-product",
            status="pending",
        )
        _db.session.add(other_sug)
        _db.session.commit()

        from app.services.dep_ai_service import list_suggestions

        sugs = list_suggestions(product)
        # Only the suggestion from beta (which is in 'product') should appear
        assert all(s["from_app_id"] == two_apps["beta"] for s in sugs)


def test_list_suggestions_to_dict_keys(app, product, two_apps, pending_suggestion):
    """Every suggestion dict must include the expected keys."""
    with app.app_context():
        from app.services.dep_ai_service import list_suggestions

        sugs = list_suggestions(product)
        for s in sugs:
            for key in (
                "id",
                "from_app_id",
                "to_app_id",
                "dep_type",
                "confidence",
                "reason",
                "status",
                "suggested_at",
            ):
                assert key in s, f"Missing key: {key}"


# ── detect_patterns ───────────────────────────────────────────────────────────


def test_detect_patterns_saves_rows(app, product, two_apps):
    """Mocked Groq response causes DepPattern rows to be saved."""
    with app.app_context():
        app.config["GROQ_API_KEY"] = "fake-key"
        groq_payload = {
            "patterns": [
                {
                    "pattern_type": "co_deployment",
                    "name": "Core Cluster",
                    "description": "Alpha and Beta always deploy together.",
                    "app_ids": [two_apps["alpha"], two_apps["beta"]],
                    "key_metrics": {"avg_co_pct": 95},
                }
            ]
        }
        with patch("app.services.dep_ai_service._call_groq", return_value=groq_payload):
            from app.services.dep_ai_service import detect_patterns

            result = detect_patterns(product)

        assert result["available"] is True
        assert result["count"] == 1
        assert len(result["patterns"]) == 1

        saved = DepPattern.query.filter_by(product_id=product).all()
        assert len(saved) == 1
        assert saved[0].pattern_type == "co_deployment"
        assert saved[0].name == "Core Cluster"


def test_detect_patterns_replaces_old_rows(app, product, two_apps):
    """Running detect_patterns again must delete old patterns and insert fresh ones."""
    with app.app_context():
        app.config["GROQ_API_KEY"] = "fake-key"
        old_pat = DepPattern(
            product_id=product,
            name="Old Pattern",
            pattern_type="anomaly",
            app_ids=json.dumps([two_apps["alpha"]]),
            metadata_json="{}",
            description="stale",
        )
        _db.session.add(old_pat)
        _db.session.commit()
        assert DepPattern.query.filter_by(product_id=product).count() == 1

        groq_payload = {
            "patterns": [
                {
                    "pattern_type": "co_deployment",
                    "name": "New Cluster",
                    "description": "Fresh.",
                    "app_ids": [two_apps["beta"]],
                    "key_metrics": {},
                },
            ]
        }
        with patch("app.services.dep_ai_service._call_groq", return_value=groq_payload):
            from app.services.dep_ai_service import detect_patterns

            detect_patterns(product)

        patterns = DepPattern.query.filter_by(product_id=product).all()
        assert len(patterns) == 1
        assert patterns[0].name == "New Cluster"


def test_detect_patterns_caps_at_10(app, product, two_apps):
    """Groq returning >10 patterns must be capped at 10 saved rows."""
    with app.app_context():
        app.config["GROQ_API_KEY"] = "fake-key"
        many = [
            {
                "pattern_type": "co_deployment",
                "name": f"P{i}",
                "description": ".",
                "app_ids": [],
                "key_metrics": {},
            }
            for i in range(15)
        ]
        with patch("app.services.dep_ai_service._call_groq", return_value={"patterns": many}):
            from app.services.dep_ai_service import detect_patterns

            detect_patterns(product)
        assert DepPattern.query.filter_by(product_id=product).count() == 10


def test_detect_patterns_no_apps_returns_message(app, product):
    """Product with no apps should return graceful message without calling Groq."""
    with app.app_context():
        app.config["GROQ_API_KEY"] = "fake-key"
        with patch("app.services.dep_ai_service._call_groq") as mock_groq:
            from app.services.dep_ai_service import detect_patterns

            result = detect_patterns(product)
        mock_groq.assert_not_called()
        assert result["available"] is True
        assert result["patterns"] == []


# ── get_ai_canvas_data ────────────────────────────────────────────────────────


def test_get_ai_canvas_data_structure(app, product, two_apps, pending_suggestion):
    """Canvas data must contain nodes, edges, suggested_edges, patterns, suggestions."""
    with app.app_context():
        from app.services.dep_ai_service import get_ai_canvas_data

        data = get_ai_canvas_data(product)
        assert "nodes" in data
        assert "edges" in data
        assert "suggested_edges" in data
        assert "patterns" in data
        assert "suggestions" in data
        # Our two apps must appear in nodes
        node_ids = {n["id"] for n in data["nodes"]}
        assert two_apps["alpha"] in node_ids
        assert two_apps["beta"] in node_ids


def test_get_ai_canvas_data_suggested_edges_from_pending(
    app, product, two_apps, pending_suggestion
):
    """Pending suggestions must appear as suggested_edges in the canvas payload."""
    with app.app_context():
        from app.services.dep_ai_service import get_ai_canvas_data

        data = get_ai_canvas_data(product)
        assert len(data["suggested_edges"]) == 1
        se = data["suggested_edges"][0]
        assert se["edge_type"] == "suggested"
        assert se["source"] == two_apps["beta"]
        assert se["target"] == two_apps["alpha"]


def test_get_ai_canvas_data_cluster_enrichment(app, product, two_apps):
    """Nodes belonging to a co_deployment pattern get a cluster_id in canvas data."""
    with app.app_context():
        pat = DepPattern(
            product_id=product,
            name="Test Cluster",
            pattern_type="co_deployment",
            app_ids=json.dumps([two_apps["alpha"], two_apps["beta"]]),
            metadata_json="{}",
            description="They always deploy together.",
        )
        _db.session.add(pat)
        _db.session.commit()
        pat_id = pat.id

        from app.services.dep_ai_service import get_ai_canvas_data

        data = get_ai_canvas_data(product)
        for node in data["nodes"]:
            assert node["cluster_id"] == pat_id


def test_get_ai_canvas_data_drift_flag(app, product, two_apps):
    """Nodes in a compliance_drift pattern get compliance_drift=True."""
    with app.app_context():
        pat = DepPattern(
            product_id=product,
            name="Drift Group",
            pattern_type="compliance_drift",
            app_ids=json.dumps([two_apps["alpha"]]),
            metadata_json="{}",
            description="Compliance declining.",
        )
        _db.session.add(pat)
        _db.session.commit()

        from app.services.dep_ai_service import get_ai_canvas_data

        data = get_ai_canvas_data(product)
        node_alpha = next(n for n in data["nodes"] if n["id"] == two_apps["alpha"])
        node_beta = next(n for n in data["nodes"] if n["id"] == two_apps["beta"])
        assert node_alpha["compliance_drift"] is True
        assert node_beta["compliance_drift"] is False
