"""Business logic for Pipeline and Stage management."""

from __future__ import annotations

import json

from app.extensions import db
from app.models.pipeline import Pipeline, Stage
from app.services.compliance_service import calculate_pipeline_score
from app.services.id_service import resource_id


def create_pipeline(
    product_id: str,
    name: str,
    kind: str = "ci",
    git_repo: str | None = None,
    git_branch: str = "main",
    stages: list[dict] | None = None,
    application_id: str | None = None,
) -> Pipeline:
    """Create a Pipeline and its initial Stages under a Product.

    Args:
        product_id: Parent product identifier.
        name: Human-readable pipeline name.
        kind: ``ci`` or ``cd``.
        git_repo: Source repository URL.
        git_branch: Branch to monitor.
        stages: Optional list of stage definition dicts.

    Returns:
        The newly created Pipeline with its stages attached.
    """
    pipeline = Pipeline(
        id=resource_id("pl"),
        product_id=product_id,
        application_id=application_id,
        name=name,
        kind=kind,
        git_repo=git_repo,
        git_branch=git_branch,
    )
    db.session.add(pipeline)

    for stage_data in stages or []:
        stage = Stage(
            id=stage_data.get("id") or resource_id("stg"),
            pipeline_id=pipeline.id,
            name=stage_data["name"],
            order=stage_data.get("order", 0),
            container_image=stage_data.get("container_image"),
            run_language=stage_data.get("run_language"),
            run_code=stage_data.get("run_code"),
            run_file=stage_data.get("run_file"),
            execution_mode=stage_data.get("execution_mode", "sequential"),
            input_schema=json.dumps(stage_data.get("input_schema", {})),
            output_schema=json.dumps(stage_data.get("output_schema", {})),
        )
        db.session.add(stage)

    db.session.commit()
    return pipeline


def update_compliance_score(
    product_id: str,
    pipeline_id: str,
    mandatory_pct: float,
    best_practice_pct: float,
    runtime_pct: float,
    metadata_pct: float,
) -> Pipeline:
    """Recalculate and persist the weighted compliance score for a pipeline.

    Args:
        product_id: Parent product scope (used to validate ownership).
        pipeline_id: Pipeline to update.
        mandatory_pct: Score for mandatory org controls (0–100).
        best_practice_pct: Score for best-practice controls (0–100).
        runtime_pct: Score derived from runtime behaviour (0–100).
        metadata_pct: Score for metadata completeness (0–100).

    Returns:
        The updated Pipeline instance.
    """
    pipeline = Pipeline.query.filter_by(id=pipeline_id, product_id=product_id).first_or_404()
    score, rating = calculate_pipeline_score(
        mandatory_pct, best_practice_pct, runtime_pct, metadata_pct
    )
    pipeline.compliance_score = score
    pipeline.compliance_rating = rating
    db.session.commit()
    return pipeline
