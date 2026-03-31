"""Property resolution service — CloudBees-style hierarchical property lookup.

Resolution order (most-specific first):
  Runtime overrides  → ParameterValue on task_run / stage_run / pipeline_run
  Design-time defs   → Property on task → stage → pipeline → product

Each level can define a value; the first match wins.

Public API
----------
  list_properties(owner_type, owner_id)         → [Property]
  set_property(owner_type, owner_id, name, ...) → Property
  delete_property(owner_type, owner_id, name)   → None
  resolve(name, *, pipeline_run, stage_run, task_run, task, stage, pipeline, product)
  resolve_all(*, pipeline_run, stage_run, task_run, task, stage, pipeline, product)
  set_parameter_value(run_type, run_id, name, value) → ParameterValue
  list_parameter_values(run_type, run_id)             → [ParameterValue]
"""

from __future__ import annotations

from typing import Any

from app.extensions import db
from app.models.property import ParameterValue, Property
from app.services.id_service import resource_id

# ── Design-time owner chain ───────────────────────────────────────────────────
# Maps owner_type → (parent_owner_type, attr_on_child_that_gives_parent_id)
_DESIGN_CHAIN: dict[str, tuple[str, str] | None] = {
    "task": ("stage", "stage_id"),
    "stage": ("pipeline", "pipeline_id"),
    "pipeline": ("product", "product_id"),
    "product": None,
}

# ── Runtime run chain ─────────────────────────────────────────────────────────
_RUNTIME_CHAIN: list[tuple[str, str | None]] = [
    # (run_type, attr_to_get_id)  — ordered most-specific → least-specific
    ("task_run", "id"),
    ("stage_run", "id"),
    ("pipeline_run", "id"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Design-time CRUD
# ─────────────────────────────────────────────────────────────────────────────


def list_properties(owner_type: str, owner_id: str) -> list[Property]:
    """Return all properties defined directly on this owner (no inheritance)."""
    return (
        Property.query.filter_by(owner_type=owner_type, owner_id=owner_id)
        .order_by(Property.name)
        .all()
    )


def set_property(
    owner_type: str,
    owner_id: str,
    name: str,
    value: str | None,
    *,
    value_type: str = "string",
    description: str | None = None,
    is_required: bool = False,
) -> Property:
    """Upsert a property on a definition object."""
    prop = Property.query.filter_by(owner_type=owner_type, owner_id=owner_id, name=name).first()
    if prop:
        prop.value = value
        prop.value_type = value_type
        if description is not None:
            prop.description = description
        prop.is_required = is_required
    else:
        prop = Property(
            id=resource_id("prop"),
            owner_type=owner_type,
            owner_id=owner_id,
            name=name,
            value=value,
            value_type=value_type,
            description=description,
            is_required=is_required,
        )
        db.session.add(prop)
    db.session.commit()
    return prop


def delete_property(owner_type: str, owner_id: str, name: str) -> None:
    """Delete a design-time property. No-op if not found."""
    prop = Property.query.filter_by(owner_type=owner_type, owner_id=owner_id, name=name).first()
    if prop:
        db.session.delete(prop)
        db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Runtime parameter value CRUD
# ─────────────────────────────────────────────────────────────────────────────


def set_parameter_value(run_type: str, run_id: str, name: str, value: str | None) -> ParameterValue:
    """Upsert a runtime parameter override."""
    pv = ParameterValue.query.filter_by(run_type=run_type, run_id=run_id, name=name).first()
    if pv:
        pv.value = value
    else:
        pv = ParameterValue(
            id=resource_id("pval"),
            run_type=run_type,
            run_id=run_id,
            name=name,
            value=value,
        )
        db.session.add(pv)
    db.session.commit()
    return pv


def list_parameter_values(run_type: str, run_id: str) -> list[ParameterValue]:
    return (
        ParameterValue.query.filter_by(run_type=run_type, run_id=run_id)
        .order_by(ParameterValue.name)
        .all()
    )


def delete_parameter_value(run_type: str, run_id: str, name: str) -> None:
    pv = ParameterValue.query.filter_by(run_type=run_type, run_id=run_id, name=name).first()
    if pv:
        db.session.delete(pv)
        db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Hierarchical resolution
# ─────────────────────────────────────────────────────────────────────────────


def resolve(
    name: str,
    *,
    task_run=None,
    stage_run=None,
    pipeline_run=None,
    task=None,
    stage=None,
    pipeline=None,
    product=None,
) -> Any:
    """Return the value of *name* by walking the resolution chain.

    Returns the raw string value (or coerced value for typed properties).
    Returns None if not found anywhere in the chain.
    """
    # 1. Runtime overrides — most specific first
    for run_type, run_obj in [
        ("task_run", task_run),
        ("stage_run", stage_run),
        ("pipeline_run", pipeline_run),
    ]:
        if run_obj is not None:
            pv = ParameterValue.query.filter_by(
                run_type=run_type, run_id=run_obj.id, name=name
            ).first()
            if pv is not None:
                return pv.value

    # 2. Design-time properties — most specific first
    for owner_type, owner_obj in [
        ("task", task),
        ("stage", stage),
        ("pipeline", pipeline),
        ("product", product),
    ]:
        if owner_obj is not None:
            prop = Property.query.filter_by(
                owner_type=owner_type, owner_id=owner_obj.id, name=name
            ).first()
            if prop is not None:
                return prop.coerced_value()

    return None


def resolve_all(
    *,
    task_run=None,
    stage_run=None,
    pipeline_run=None,
    task=None,
    stage=None,
    pipeline=None,
    product=None,
) -> dict[str, Any]:
    """Return all resolved properties as a flat dict.

    Collects every property name visible in the chain, then resolves each
    one through the full hierarchy (so overrides take precedence).
    Secrets are included as their raw value — callers must mask if needed.
    """
    # Gather all property names visible at any level (design-time)
    names: set[str] = set()

    for owner_type, owner_obj in [
        ("task", task),
        ("stage", stage),
        ("pipeline", pipeline),
        ("product", product),
    ]:
        if owner_obj is not None:
            for prop in Property.query.filter_by(
                owner_type=owner_type, owner_id=owner_obj.id
            ).all():
                names.add(prop.name)

    # Also include any runtime overrides that aren't in design-time defs
    for run_type, run_obj in [
        ("task_run", task_run),
        ("stage_run", stage_run),
        ("pipeline_run", pipeline_run),
    ]:
        if run_obj is not None:
            for pv in ParameterValue.query.filter_by(run_type=run_type, run_id=run_obj.id).all():
                names.add(pv.name)

    return {
        name: resolve(
            name,
            task_run=task_run,
            stage_run=stage_run,
            pipeline_run=pipeline_run,
            task=task,
            stage=stage,
            pipeline=pipeline,
            product=product,
        )
        for name in sorted(names)
    }
