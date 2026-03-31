"""DevSecOps Maturity Model API endpoints."""

from __future__ import annotations

from flask import Blueprint, jsonify

maturity_bp = Blueprint("maturity", __name__, url_prefix="/api/v1/maturity")


@maturity_bp.get("/task-types")
def list_task_types():
    """Return canonical task type options for the UI picker."""
    from app.services.maturity_service import TASK_TYPE_OPTIONS

    return jsonify(TASK_TYPE_OPTIONS)


@maturity_bp.get("/pipeline/<pipeline_id>")
def pipeline_maturity(pipeline_id: str):
    from app.services.maturity_service import score_pipeline

    return jsonify(score_pipeline(pipeline_id))


@maturity_bp.get("/application/<application_id>")
def application_maturity(application_id: str):
    from app.services.maturity_service import score_application

    return jsonify(score_application(application_id))


@maturity_bp.get("/product/<product_id>")
def product_maturity(product_id: str):
    from app.services.maturity_service import score_product

    return jsonify(score_product(product_id))


@maturity_bp.get("/overview")
def maturity_overview():
    from app.services.maturity_service import get_overview

    return jsonify(get_overview())
