"""Calculates compliance ratings for pipelines and enforces release admission rules."""

from __future__ import annotations

from app.domain.enums import ComplianceRating

# Rating thresholds — ordered highest to lowest so the first match wins
RATING_THRESHOLDS: list[tuple[float, str]] = [
    (90, ComplianceRating.PLATINUM),
    (75, ComplianceRating.GOLD),
    (60, ComplianceRating.SILVER),
    (40, ComplianceRating.BRONZE),
    (0, ComplianceRating.NON_COMPLIANT),
]

RATING_ORDER: list[str] = [
    ComplianceRating.NON_COMPLIANT,
    ComplianceRating.BRONZE,
    ComplianceRating.SILVER,
    ComplianceRating.GOLD,
    ComplianceRating.PLATINUM,
]


def score_to_rating(score: float) -> str:
    """Map a numeric score (0–100) to a :class:`~app.domain.enums.ComplianceRating`."""
    for threshold, rating in RATING_THRESHOLDS:
        if score >= threshold:
            return rating
    return ComplianceRating.NON_COMPLIANT


def rating_meets_minimum(actual: str, minimum: str) -> bool:
    """Return True if *actual* rating is equal to or higher than *minimum* rating."""
    actual_idx = RATING_ORDER.index(actual) if actual in RATING_ORDER else 0
    min_idx = RATING_ORDER.index(minimum) if minimum in RATING_ORDER else 0
    return actual_idx >= min_idx


def calculate_pipeline_score(
    mandatory_pct: float,
    best_practice_pct: float,
    runtime_pct: float,
    metadata_pct: float,
) -> tuple[float, str]:
    """Return weighted compliance (score, rating) per the design specification.

    Weights:
        mandatory     60 %
        best_practice 20 %
        runtime       15 %
        metadata       5 %
    """
    score = (
        mandatory_pct * 0.60 + best_practice_pct * 0.20 + runtime_pct * 0.15 + metadata_pct * 0.05
    )
    return round(score, 2), score_to_rating(score)


def check_release_admission(pipeline, release) -> dict:
    """Check whether a pipeline's compliance rating satisfies all active admission rules.

    Evaluates rules scoped to the release's product and the global
    ``organization`` scope.

    Returns:
        ``{"allowed": bool, "violations": list[str]}``
    """
    from app.models.compliance import ComplianceRule

    product_scope = f"product:{release.product_id}"
    rules = ComplianceRule.query.filter(
        ComplianceRule.is_active == True,  # noqa: E712 — SQLAlchemy requires ==
        ComplianceRule.scope.in_([product_scope, "organization"]),
    ).all()

    violations: list[str] = []
    for rule in rules:
        if not rating_meets_minimum(pipeline.compliance_rating, rule.min_rating):
            violations.append(
                f"Rule '{rule.id}': minimum rating for {rule.scope} is "
                f"{rule.min_rating}, pipeline has {pipeline.compliance_rating} "
                f"({pipeline.compliance_score:.1f}%)"
            )

    return {"allowed": len(violations) == 0, "violations": violations}
