"""Generates time-sortable unique IDs for platform objects."""

from ulid import ULID


def new_ulid() -> str:
    return str(ULID())


def pipeline_run_id() -> str:
    return f"plrun_{new_ulid()}"


def release_run_id() -> str:
    return f"rrun_{new_ulid()}"


def stage_run_id() -> str:
    return f"srun_{new_ulid()}"


def resource_id(prefix: str) -> str:
    return f"{prefix}_{new_ulid()}"
