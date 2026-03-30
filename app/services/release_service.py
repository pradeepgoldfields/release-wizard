"""Business logic for Release management and pipeline admission control."""

from __future__ import annotations

from app.extensions import db
from app.models.pipeline import Pipeline
from app.models.release import Release
from app.services.audit_service import record_event
from app.services.compliance_service import check_release_admission
from app.services.id_service import resource_id


def create_release(
    product_id: str,
    name: str,
    version: str | None = None,
    description: str | None = None,
    created_by: str = "system",
) -> Release:
    """Create and persist a new Release under a Product.

    Emits a ``release.created`` audit event after persisting.
    """
    release = Release(
        id=resource_id("rel"),
        product_id=product_id,
        name=name,
        version=version,
        description=description,
        created_by=created_by,
    )
    db.session.add(release)
    db.session.commit()
    record_event("release.created", created_by, "release", release.id, "create")
    return release


def attach_pipeline_to_release(
    product_id: str,
    release_id: str,
    pipeline_id: str,
    requested_by: str = "unknown",
) -> dict:
    """Attach a pipeline to a release, enforcing compliance admission rules.

    Args:
        product_id: Parent product scope (used to validate release ownership).
        release_id: Target release.
        pipeline_id: Pipeline to attach.
        requested_by: Username of the actor requesting the attachment.

    Returns:
        A dict with ``allowed`` (bool) and, on failure, ``violations`` (list[str]).
    """
    release = Release.query.filter_by(id=release_id, product_id=product_id).first_or_404()
    pipeline = db.get_or_404(Pipeline, pipeline_id)

    admission = check_release_admission(pipeline, release)
    if not admission["allowed"]:
        record_event(
            "pipeline.admission.failed",
            requested_by,
            "release",
            release_id,
            "attach_pipeline",
            decision="DENY",
            detail={"pipeline_id": pipeline_id, "violations": admission["violations"]},
        )
        return {"allowed": False, "violations": admission["violations"]}

    if pipeline not in release.pipelines:
        release.pipelines.append(pipeline)
        db.session.commit()
        record_event(
            "pipeline.attached",
            requested_by,
            "release",
            release_id,
            "attach_pipeline",
            detail={"pipeline_id": pipeline_id},
        )
    return {"allowed": True, "release_id": release_id, "pipeline_id": pipeline_id}
