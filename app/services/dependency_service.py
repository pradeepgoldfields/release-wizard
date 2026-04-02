"""Dependency service — graph traversal, impact analysis, deployment inventory."""

from __future__ import annotations

import json
from collections import deque
from datetime import UTC, datetime

from app.extensions import db
from app.models.app_dependency import AppDependency, EnvDeploymentRecord
from app.models.application import ApplicationArtifact

# ── Dependency CRUD ──────────────────────────────────────────────────────────


def create_dependency(
    from_app_id: str,
    to_app_id: str,
    dep_type: str = "runtime",
    description: str | None = None,
    created_by: str | None = None,
) -> AppDependency:
    """Declare that ``from_app`` depends on ``to_app``.

    Raises :class:`ValueError` on self-reference or duplicate.
    """
    if from_app_id == to_app_id:
        raise ValueError("An application cannot depend on itself.")
    existing = AppDependency.query.filter_by(from_app_id=from_app_id, to_app_id=to_app_id).first()
    if existing:
        raise ValueError("Dependency already exists.")
    dep = AppDependency(
        from_app_id=from_app_id,
        to_app_id=to_app_id,
        dep_type=dep_type,
        description=description,
        created_by=created_by,
    )
    db.session.add(dep)
    db.session.commit()
    return dep


def delete_dependency(dep_id: str) -> None:
    dep = db.get_or_404(AppDependency, dep_id)
    db.session.delete(dep)
    db.session.commit()


def list_dependencies(product_id: str) -> list[AppDependency]:
    """All dependency edges whose ``from_app`` belongs to this product."""
    return (
        AppDependency.query.join(
            ApplicationArtifact, AppDependency.from_app_id == ApplicationArtifact.id
        )
        .filter(ApplicationArtifact.product_id == product_id)
        .all()
    )


# ── Graph traversal ──────────────────────────────────────────────────────────


def get_dependents(
    app_id: str,
    dep_types: list[str] | None = None,
    max_hops: int = 3,
) -> list[str]:
    """BFS: find all application IDs that (transitively) depend on ``app_id``.

    "Depend on" means: applications that call or embed ``app_id`` and would
    be affected if ``app_id`` changes its interface or behaviour.

    Returns a list of app IDs (excluding ``app_id`` itself).
    """
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(app_id, 0)])
    while queue:
        current_id, hops = queue.popleft()
        if hops >= max_hops:
            continue
        callers_q = AppDependency.query.filter_by(to_app_id=current_id)
        if dep_types:
            callers_q = callers_q.filter(AppDependency.dep_type.in_(dep_types))
        for dep in callers_q.all():
            if dep.from_app_id not in visited and dep.from_app_id != app_id:
                visited.add(dep.from_app_id)
                queue.append((dep.from_app_id, hops + 1))
    return list(visited)


def get_dependency_graph(product_id: str) -> dict:
    """Return a JointJS-compatible graph payload for all apps in a product.

    Node color encodes the application's compliance rating.
    Edge label carries the dependency type.
    """
    apps = ApplicationArtifact.query.filter_by(product_id=product_id).all()
    deps = list_dependencies(product_id)
    app_ids = {a.id for a in apps}

    rating_color = {
        "Platinum": "#3B82F6",  # blue-500
        "Gold": "#22C55E",  # green-500
        "Silver": "#EAB308",  # yellow-500
        "Bronze": "#F97316",  # orange-500
        "Non-Compliant": "#EF4444",  # red-500
    }

    nodes = [
        {
            "id": a.id,
            "label": a.name,
            "color": rating_color.get(a.compliance_rating or "Non-Compliant", "#6B7280"),
            "compliance_rating": a.compliance_rating or "Non-Compliant",
            "artifact_type": a.artifact_type,
        }
        for a in apps
    ]
    edges = [
        {
            "id": d.id,
            "source": d.from_app_id,
            "target": d.to_app_id,
            "dep_type": d.dep_type,
            "label": d.dep_type,
        }
        for d in deps
        if d.from_app_id in app_ids and d.to_app_id in app_ids
    ]
    return {"nodes": nodes, "edges": edges}


# ── Deployment inventory ─────────────────────────────────────────────────────


def upsert_deployment(
    product_id: str,
    app_id: str,
    env_name: str,
    artifact_id: str,
    pipeline_run_id: str,
    deployed_by: str | None = None,
) -> EnvDeploymentRecord:
    """Create or update the deployment record for ``(app_id, env_name)``."""
    record = EnvDeploymentRecord.query.filter_by(app_id=app_id, env_name=env_name).first()
    if record is None:
        record = EnvDeploymentRecord(product_id=product_id, app_id=app_id, env_name=env_name)
        db.session.add(record)
    record.artifact_id = artifact_id
    record.pipeline_run_id = pipeline_run_id
    record.deployed_by = deployed_by
    record.deployed_at = datetime.now(UTC)
    db.session.commit()
    return record


def list_deployments(product_id: str, env_name: str | None = None) -> list[EnvDeploymentRecord]:
    q = EnvDeploymentRecord.query.filter_by(product_id=product_id)
    if env_name:
        q = q.filter_by(env_name=env_name)
    return q.order_by(EnvDeploymentRecord.deployed_at.desc()).all()


# ── Impact analysis ──────────────────────────────────────────────────────────


def compute_impact(release_id: str, target_env: str | None = None) -> dict:
    """Compute blast-radius for a release.

    Identifies all applications referenced by the release's pipeline groups,
    finds their transitive dependents, and enriches with current deployment
    state and compliance rating.
    """
    from app.models.pipeline import Pipeline  # noqa: PLC0415
    from app.models.release import Release, ReleaseApplicationGroup  # noqa: PLC0415

    db.get_or_404(Release, release_id)  # 404 guard

    # Collect app IDs from all pipelines referenced by release application groups
    changed_app_ids: set[str] = set()
    for group in ReleaseApplicationGroup.query.filter_by(release_id=release_id).all():
        pipeline_ids = json.loads(group.pipeline_ids or "[]")
        for pid in pipeline_ids:
            pl = db.session.get(Pipeline, pid)
            if pl and pl.application_id:
                changed_app_ids.add(pl.application_id)

    # Collect transitive dependents for each changed app (runtime + build only)
    all_dependent_ids: set[str] = set()
    for app_id in changed_app_ids:
        all_dependent_ids.update(get_dependents(app_id, dep_types=["runtime", "build"], max_hops=3))
    # Exclude the apps being changed themselves
    all_dependent_ids -= changed_app_ids

    # Enrich dependents with compliance + deployment info
    enriched = []
    warnings = []
    for dep_app_id in all_dependent_ids:
        app = db.session.get(ApplicationArtifact, dep_app_id)
        if not app:
            continue
        record = None
        if target_env:
            record = EnvDeploymentRecord.query.filter_by(
                app_id=dep_app_id, env_name=target_env
            ).first()
        rating = app.compliance_rating or "Non-Compliant"
        entry = {
            "app_id": dep_app_id,
            "app_name": app.name,
            "compliance_rating": rating,
            "current_version": record.artifact_id if record else None,
            "last_deployed_at": (
                record.deployed_at.isoformat() if record and record.deployed_at else None
            ),
        }
        enriched.append(entry)
        if rating in ("Non-Compliant", "Bronze"):
            warnings.append(
                {
                    "app_id": dep_app_id,
                    "app_name": app.name,
                    "reason": f"Dependent has {rating} compliance rating",
                }
            )

    changed_apps = []
    for app_id in changed_app_ids:
        app = db.session.get(ApplicationArtifact, app_id)
        if app:
            changed_apps.append(
                {
                    "app_id": app_id,
                    "app_name": app.name,
                    "compliance_rating": app.compliance_rating or "Non-Compliant",
                }
            )

    return {
        "release_id": release_id,
        "applications_being_changed": changed_apps,
        "affected_dependents": enriched,
        "affected_count": len(enriched),
        "compliance_warnings": warnings,
        "warning_count": len(warnings),
    }


# ── env-name resolution helper ───────────────────────────────────────────────


def resolve_env_name(run) -> str | None:
    """Derive environment name from a pipeline run's runtime_properties or kind.

    Priority:
    1. ``runtime_properties["environment"]`` key set at trigger time
    2. Pipeline kind: ``"cd"`` → ``"prod"``, ``"ci"`` → skip (no deployment record)
    """
    try:
        props = json.loads(run.runtime_properties or "{}")
        env = props.get("environment")
        if env:
            return str(env)
    except (ValueError, TypeError):
        pass
    if run.pipeline and run.pipeline.kind == "cd":
        return "prod"
    return None
