"""Service layer — business logic separated from HTTP concerns.

Import from here for a stable public API:
    from app.services import create_product, start_pipeline_run, …
"""

from app.services.audit_service import build_release_audit_report, record_event
from app.services.authz_service import authorize, get_permissions_for_user
from app.services.compliance_service import (
    calculate_pipeline_score,
    check_release_admission,
    score_to_rating,
)
from app.services.id_service import pipeline_run_id, release_run_id, resource_id
from app.services.pipeline_service import create_pipeline, update_compliance_score
from app.services.product_service import create_application, create_product
from app.services.release_service import attach_pipeline_to_release, create_release
from app.services.run_service import start_pipeline_run, start_release_run, update_run_status
from app.services.user_service import (
    add_scoped_role,
    create_user,
    get_effective_permissions,
)

__all__ = [
    "pipeline_run_id",
    "release_run_id",
    "resource_id",
    "calculate_pipeline_score",
    "check_release_admission",
    "score_to_rating",
    "authorize",
    "get_permissions_for_user",
    "record_event",
    "build_release_audit_report",
    "create_product",
    "create_application",
    "create_pipeline",
    "update_compliance_score",
    "create_release",
    "attach_pipeline_to_release",
    "start_pipeline_run",
    "start_release_run",
    "update_run_status",
    "create_user",
    "add_scoped_role",
    "get_effective_permissions",
]
