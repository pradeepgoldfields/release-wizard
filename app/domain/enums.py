"""Domain enumerations — single source of truth for all status/rating constants."""

from enum import StrEnum


class RunStatus(StrEnum):
    """Lifecycle states for pipeline and release run executions."""

    PENDING = "Pending"
    RUNNING = "Running"
    IN_PROGRESS = "InProgress"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class ComplianceRating(StrEnum):
    """Compliance maturity levels, ordered lowest to highest."""

    NON_COMPLIANT = "Non-Compliant"
    BRONZE = "Bronze"
    SILVER = "Silver"
    GOLD = "Gold"
    PLATINUM = "Platinum"


class PipelineKind(StrEnum):
    """Whether a pipeline is a continuous-integration or continuous-deployment pipeline."""

    CI = "ci"
    CD = "cd"


class ArtifactType(StrEnum):
    """Classification of a deployable application artifact."""

    CONTAINER = "container"
    LIBRARY = "library"
    PACKAGE = "package"


class EnvironmentType(StrEnum):
    """Standard deployment environment tiers."""

    DEV = "dev"
    QA = "qa"
    STAGING = "staging"
    PROD = "prod"
    CUSTOM = "custom"


class AuditDecision(StrEnum):
    """Authorization decision recorded in the immutable audit log."""

    ALLOW = "ALLOW"
    DENY = "DENY"

