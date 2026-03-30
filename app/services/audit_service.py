"""Records immutable audit events and generates structured audit reports."""

import json
from datetime import UTC, datetime

from app.extensions import db
from app.models.compliance import AuditEvent
from app.services.id_service import resource_id


def record_event(
    event_type: str,
    actor: str,
    resource_type: str,
    resource_id_val: str,
    action: str,
    decision: str = "ALLOW",
    detail: dict | None = None,
):
    event = AuditEvent(
        id=resource_id("evt"),
        event_type=event_type,
        actor=actor,
        resource_type=resource_type,
        resource_id=resource_id_val,
        action=action,
        decision=decision,
        detail=json.dumps(detail or {}),
        timestamp=datetime.now(UTC),
    )
    db.session.add(event)
    db.session.commit()
    return event


def build_release_audit_report(release_id: str) -> dict:
    """Assembles the full structured audit report for a release."""
    from app.extensions import db as _db
    from app.models.release import Release
    from app.models.run import ReleaseRun

    release = _db.get_or_404(Release, release_id)
    runs = (
        ReleaseRun.query.filter_by(release_id=release_id)
        .order_by(ReleaseRun.started_at.desc())
        .all()
    )
    events = (
        AuditEvent.query.filter_by(resource_type="release", resource_id=release_id)
        .order_by(AuditEvent.timestamp)
        .all()
    )

    pipeline_summaries = []
    for pipeline in release.pipelines:
        pipeline_summaries.append(
            {
                "id": pipeline.id,
                "name": pipeline.name,
                "kind": pipeline.kind,
                "compliance_rating": pipeline.compliance_rating,
                "compliance_score": pipeline.compliance_score,
                "definition_sha": pipeline.definition_sha,
                "stages": [s.to_dict() for s in pipeline.stages],
            }
        )

    return {
        "release": release.to_dict(),
        "product_id": release.product_id,
        "pipelines": pipeline_summaries,
        "runs": [r.to_dict(include_pipeline_runs=True) for r in runs],
        "audit_events": [e.to_dict() for e in events],
        "generated_at": datetime.now(UTC).isoformat(),
    }
