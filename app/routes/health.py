"""Kubernetes liveness and readiness probe endpoints.

These routes are deliberately lightweight — they must respond in milliseconds
even under load, as Kubernetes calls them continuously.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from app.extensions import db

log = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__)


@health_bp.get("/healthz")
def liveness():
    """Kubernetes liveness probe — confirms the process is alive."""
    return jsonify({"status": "ok"}), 200


@health_bp.get("/readyz")
def readiness():
    """Kubernetes readiness probe — confirms the app can serve traffic.

    Checks database connectivity; returns 503 if the DB is unreachable so
    Kubernetes removes the pod from the load-balancer until it recovers.
    """
    try:
        db.session.execute(db.text("SELECT 1"))
        db_healthy = True
    except Exception:
        log.exception("Readiness check: database unreachable")
        db_healthy = False

    status_code = 200 if db_healthy else 503
    body = {"status": "ready" if db_healthy else "unavailable", "db": db_healthy}
    return jsonify(body), status_code
