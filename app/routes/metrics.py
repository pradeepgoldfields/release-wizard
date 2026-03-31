"""Prometheus metrics endpoint and alert rules API.

Exposes:
  GET /metrics               — Prometheus text format (public, no auth)
  GET /api/v1/metrics/stats  — JSON snapshot of current metric values
  GET /api/v1/metrics/alerts — Alert rule definitions + current firing status
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify

metrics_bp = Blueprint("metrics", __name__)

# ── Prometheus metric definitions ─────────────────────────────────────────────

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    REGISTRY,
)

# Pipeline execution metrics
pipeline_runs_total = Counter(
    "conduit_pipeline_runs_total",
    "Total number of pipeline runs started",
    ["pipeline_id", "pipeline_name", "status"],
)
pipeline_run_duration_seconds = Histogram(
    "conduit_pipeline_run_duration_seconds",
    "Pipeline run duration in seconds",
    ["pipeline_name"],
    buckets=[5, 10, 30, 60, 120, 300, 600, 1800],
)
active_pipeline_runs = Gauge(
    "conduit_active_pipeline_runs",
    "Number of currently running pipeline runs",
)

# Task execution metrics
task_runs_total = Counter(
    "conduit_task_runs_total",
    "Total number of task runs",
    ["task_name", "status"],
)
task_run_duration_seconds = Histogram(
    "conduit_task_run_duration_seconds",
    "Task run duration in seconds",
    ["task_name"],
    buckets=[1, 5, 10, 30, 60, 120, 300],
)

# Platform metrics
products_total = Gauge("conduit_products_total", "Total number of products")
pipelines_total = Gauge("conduit_pipelines_total", "Total number of pipelines")
releases_total = Gauge("conduit_releases_total", "Total number of releases")
users_total = Gauge("conduit_users_total", "Total number of users")

# Compliance metrics
compliance_score_avg = Gauge(
    "conduit_compliance_score_avg",
    "Average compliance score across all pipelines",
)
pipelines_compliant = Gauge(
    "conduit_pipelines_compliant_total",
    "Number of pipelines with compliance score >= 80",
)

# Release metrics
release_runs_total = Counter(
    "conduit_release_runs_total",
    "Total number of release runs",
    ["status"],
)
active_release_runs = Gauge(
    "conduit_active_release_runs",
    "Number of currently running release runs",
)

# HTTP request metrics
http_requests_total = Counter(
    "conduit_http_requests_total",
    "Total HTTP requests by method, endpoint and status",
    ["method", "endpoint", "status"],
)
http_request_duration_seconds = Histogram(
    "conduit_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)


def _refresh_platform_gauges() -> None:
    """Re-sample platform-level gauges from the DB on each /metrics scrape."""
    try:
        from app.extensions import db
        from app.models.auth import User
        from app.models.pipeline import Pipeline
        from app.models.product import Product
        from app.models.release import Release
        from app.models.run import PipelineRun, ReleaseRun

        products_total.set(Product.query.count())
        pipelines_total.set(Pipeline.query.count())
        releases_total.set(Release.query.count())
        users_total.set(User.query.count())

        # Active runs
        active_pipeline_runs.set(
            PipelineRun.query.filter_by(status="Running").count()
        )
        active_release_runs.set(
            ReleaseRun.query.filter_by(status="Running").count()
        )

        # Compliance scores
        pipelines = Pipeline.query.all()
        scores = [p.compliance_score for p in pipelines if p.compliance_score is not None]
        if scores:
            compliance_score_avg.set(sum(scores) / len(scores))
            pipelines_compliant.set(sum(1 for s in scores if s >= 80))
        else:
            compliance_score_avg.set(0)
            pipelines_compliant.set(0)

    except Exception:
        pass  # Don't crash the metrics endpoint if DB is unavailable


# ── Routes ────────────────────────────────────────────────────────────────────

@metrics_bp.get("/metrics")
def prometheus_metrics():
    """Prometheus scrape endpoint — returns metrics in text exposition format."""
    _refresh_platform_gauges()
    return Response(generate_latest(REGISTRY), mimetype=CONTENT_TYPE_LATEST)


@metrics_bp.get("/api/v1/metrics/stats")
def metrics_stats():
    """Return a JSON snapshot of current metric values for the UI dashboard."""
    _refresh_platform_gauges()

    try:
        from app.extensions import db
        from app.models.pipeline import Pipeline
        from app.models.product import Product
        from app.models.release import Release
        from app.models.run import PipelineRun, ReleaseRun
        from app.models.auth import User
        from sqlalchemy import func

        # Recent run stats (last 24h)
        from datetime import UTC, datetime, timedelta
        since = datetime.now(UTC) - timedelta(hours=24)

        run_counts = (
            db.session.query(PipelineRun.status, func.count(PipelineRun.id))
            .filter(PipelineRun.started_at >= since)
            .group_by(PipelineRun.status)
            .all()
        )
        run_by_status = {s: c for s, c in run_counts}

        # Average run duration (last 50 completed runs)
        completed = (
            PipelineRun.query
            .filter(PipelineRun.finished_at.isnot(None), PipelineRun.started_at.isnot(None))
            .order_by(PipelineRun.started_at.desc())
            .limit(50)
            .all()
        )
        durations = [
            (r.finished_at - r.started_at).total_seconds()
            for r in completed
            if r.finished_at and r.started_at
        ]
        avg_duration = round(sum(durations) / len(durations), 1) if durations else 0

        pipelines = Pipeline.query.all()
        scores = [p.compliance_score for p in pipelines if p.compliance_score is not None]

        return jsonify({
            "platform": {
                "products": Product.query.count(),
                "pipelines": Pipeline.query.count(),
                "releases": Release.query.count(),
                "users": User.query.count(),
            },
            "runs_last_24h": {
                "total": sum(run_by_status.values()),
                "succeeded": run_by_status.get("Succeeded", 0),
                "failed": run_by_status.get("Failed", 0),
                "running": run_by_status.get("Running", 0),
                "cancelled": run_by_status.get("Cancelled", 0),
                "warning": run_by_status.get("Warning", 0),
            },
            "active_runs": {
                "pipeline": PipelineRun.query.filter_by(status="Running").count(),
                "release": ReleaseRun.query.filter_by(status="Running").count(),
            },
            "compliance": {
                "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
                "compliant_pipelines": sum(1 for s in scores if s >= 80),
                "total_pipelines": len(scores),
            },
            "performance": {
                "avg_run_duration_s": avg_duration,
                "sample_size": len(durations),
            },
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# Alert rule definitions
_ALERT_RULES = [
    {
        "name": "HighFailureRate",
        "severity": "critical",
        "description": "More than 20% of pipeline runs in the last hour have failed.",
        "condition": "rate(conduit_pipeline_runs_total{status='Failed'}[1h]) / rate(conduit_pipeline_runs_total[1h]) > 0.2",
        "for": "5m",
    },
    {
        "name": "LongRunningPipeline",
        "severity": "warning",
        "description": "A pipeline run has been running for more than 30 minutes.",
        "condition": "conduit_pipeline_run_duration_seconds > 1800",
        "for": "0m",
    },
    {
        "name": "NoRecentRuns",
        "severity": "warning",
        "description": "No pipeline runs have completed in the last 24 hours.",
        "condition": "increase(conduit_pipeline_runs_total[24h]) == 0",
        "for": "1h",
    },
    {
        "name": "LowComplianceScore",
        "severity": "warning",
        "description": "Average compliance score across all pipelines has dropped below 70.",
        "condition": "conduit_compliance_score_avg < 70",
        "for": "5m",
    },
    {
        "name": "ManyActiveRuns",
        "severity": "info",
        "description": "More than 10 pipeline runs are executing simultaneously.",
        "condition": "conduit_active_pipeline_runs > 10",
        "for": "1m",
    },
    {
        "name": "HighHttpErrorRate",
        "severity": "critical",
        "description": "More than 5% of HTTP requests are returning 5xx errors.",
        "condition": "rate(conduit_http_requests_total{status=~'5..'}[5m]) / rate(conduit_http_requests_total[5m]) > 0.05",
        "for": "2m",
    },
]


@metrics_bp.get("/api/v1/metrics/alerts")
def metrics_alerts():
    """Return alert rule definitions with current firing status evaluated from DB."""
    try:
        from app.extensions import db
        from app.models.run import PipelineRun
        from datetime import UTC, datetime, timedelta

        since_1h = datetime.now(UTC) - timedelta(hours=1)
        total_1h = PipelineRun.query.filter(PipelineRun.started_at >= since_1h).count()
        failed_1h = PipelineRun.query.filter(
            PipelineRun.started_at >= since_1h, PipelineRun.status == "Failed"
        ).count()
        active = PipelineRun.query.filter_by(status="Running").count()

        from app.models.pipeline import Pipeline
        pipelines = Pipeline.query.all()
        scores = [p.compliance_score for p in pipelines if p.compliance_score is not None]
        avg_score = sum(scores) / len(scores) if scores else 100

        # Evaluate each rule against live data
        def _is_firing(rule_name: str) -> bool:
            if rule_name == "HighFailureRate":
                return total_1h > 0 and (failed_1h / total_1h) > 0.2
            if rule_name == "LongRunningPipeline":
                from app.models.run import PipelineRun as _PR
                threshold = datetime.now(UTC) - timedelta(minutes=30)
                return _PR.query.filter(
                    _PR.status == "Running", _PR.started_at <= threshold
                ).count() > 0
            if rule_name == "NoRecentRuns":
                since_24h = datetime.now(UTC) - timedelta(hours=24)
                return PipelineRun.query.filter(PipelineRun.started_at >= since_24h).count() == 0
            if rule_name == "LowComplianceScore":
                return avg_score < 70
            if rule_name == "ManyActiveRuns":
                return active > 10
            return False

        result = []
        for rule in _ALERT_RULES:
            firing = _is_firing(rule["name"])
            result.append({**rule, "firing": firing})
        return jsonify(result)

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Monitoring stack management ───────────────────────────────────────────────

@metrics_bp.get("/api/v1/metrics/stack/status")
def stack_status():
    """Return running status of Prometheus/Alertmanager/Grafana containers."""
    from app.services.monitoring_stack_service import get_stack_status
    return jsonify(get_stack_status())


@metrics_bp.post("/api/v1/metrics/stack/start")
def stack_start():
    """Write config files and start the monitoring stack via docker-compose."""
    from app.services.monitoring_stack_service import start_stack
    result = start_stack()
    return jsonify(result), (200 if result.get("ok") else 500)


@metrics_bp.post("/api/v1/metrics/stack/stop")
def stack_stop():
    """Stop the monitoring stack containers."""
    from app.services.monitoring_stack_service import stop_stack
    result = stop_stack()
    return jsonify(result), (200 if result.get("ok") else 500)
