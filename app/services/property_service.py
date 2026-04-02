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
  validate_runtime_properties(pipeline, runtime_properties) → list[str]  (errors)
"""

from __future__ import annotations

from typing import Any

from app.extensions import db
from app.models.property import ParameterValue, Property
from app.services.id_service import resource_id

# ── Resolution chains ─────────────────────────────────────────────────────────
# Adding a new scope (e.g. "release") requires a one-line change here only.

# Runtime run chain: (run_type, kwarg_name) ordered most-specific → least-specific.
# kwarg_name matches the keyword argument accepted by resolve() / resolve_all().
_RUNTIME_CHAIN: list[tuple[str, str]] = [
    ("task_run", "task_run"),
    ("stage_run", "stage_run"),
    ("pipeline_run", "pipeline_run"),
]

# Design-time owner chain: (owner_type, kwarg_name) ordered most-specific → least-specific.
_DESIGN_CHAIN: list[tuple[str, str]] = [
    ("task", "task"),
    ("stage", "stage"),
    ("pipeline", "pipeline"),
    ("product", "product"),
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

    Returns the coerced value for typed design-time properties, the raw
    string for untyped runtime overrides (unless the matching design-time
    property supplies a type — see _coerce_with_design_type).
    Returns None if not found anywhere in the chain.
    """
    kwargs = dict(
        task_run=task_run,
        stage_run=stage_run,
        pipeline_run=pipeline_run,
        task=task,
        stage=stage,
        pipeline=pipeline,
        product=product,
    )

    # 1. Runtime overrides — most specific first (driven by _RUNTIME_CHAIN)
    for run_type, kwarg in _RUNTIME_CHAIN:
        run_obj = kwargs.get(kwarg)
        if run_obj is not None:
            pv = ParameterValue.query.filter_by(
                run_type=run_type, run_id=run_obj.id, name=name
            ).first()
            if pv is not None:
                return _coerce_with_design_type(pv.value, name, kwargs)

    # 2. Design-time properties — most specific first (driven by _DESIGN_CHAIN)
    for owner_type, kwarg in _DESIGN_CHAIN:
        owner_obj = kwargs.get(kwarg)
        if owner_obj is not None:
            prop = Property.query.filter_by(
                owner_type=owner_type, owner_id=owner_obj.id, name=name
            ).first()
            if prop is not None:
                return prop.coerced_value()

    return None


def _coerce_with_design_type(raw_value: str | None, name: str, kwargs: dict) -> Any:
    """Coerce a runtime override value using the type of the matching design-time property.

    Walks the design chain to find the first Property definition for *name*,
    borrows its value_type, then applies the same coercion as Property.coerced_value().
    Falls back to returning *raw_value* as-is if no design-time definition exists.
    """

    for owner_type, kwarg in _DESIGN_CHAIN:
        owner_obj = kwargs.get(kwarg)
        if owner_obj is not None:
            prop = Property.query.filter_by(
                owner_type=owner_type, owner_id=owner_obj.id, name=name
            ).first()
            if prop is not None:
                # Temporarily swap value so we can reuse coerced_value()
                original = prop.value
                prop.value = raw_value
                try:
                    return prop.coerced_value()
                finally:
                    prop.value = original

    return raw_value  # no design-time definition — return raw string


def resolve_all(
    *,
    task_run=None,
    stage_run=None,
    pipeline_run=None,
    task=None,
    stage=None,
    pipeline=None,
    product=None,
    mask_secrets: bool = False,
) -> dict[str, Any]:
    """Return all resolved properties as a flat dict.

    Collects every property name visible at any level in both chains using
    two bulk queries (one per table), then resolves precedence in Python —
    O(levels) queries instead of O(names × levels).

    Args:
        mask_secrets: When True, secret-typed property values are replaced
            with "***" so the result is safe to store in logs or env vars.
    """
    kwargs = dict(
        task_run=task_run,
        stage_run=stage_run,
        pipeline_run=pipeline_run,
        task=task,
        stage=stage,
        pipeline=pipeline,
        product=product,
    )

    # ── Bulk-load all design-time properties for every owner in the chain ──────
    design_owner_ids = [
        (owner_type, kwargs[kwarg].id)
        for owner_type, kwarg in _DESIGN_CHAIN
        if kwargs.get(kwarg) is not None
    ]
    # Map (owner_type, name) → Property for fast lookup
    design_props: dict[tuple[str, str], Property] = {}
    if design_owner_ids:
        from sqlalchemy import and_, or_

        rows = Property.query.filter(
            or_(
                and_(Property.owner_type == ot, Property.owner_id == oid)
                for ot, oid in design_owner_ids
            )
        ).all()
        for prop in rows:
            design_props[(prop.owner_type, prop.name)] = design_props.get(
                (prop.owner_type, prop.name), prop
            )  # keep first (shouldn't be duplicates due to unique constraint)

    # ── Bulk-load all runtime parameter values for every run in the chain ──────
    runtime_run_ids = [
        (run_type, kwargs[kwarg].id)
        for run_type, kwarg in _RUNTIME_CHAIN
        if kwargs.get(kwarg) is not None
    ]
    # Map (run_type, name) → ParameterValue
    runtime_pvs: dict[tuple[str, str], ParameterValue] = {}
    if runtime_run_ids:
        from sqlalchemy import and_, or_

        pv_rows = ParameterValue.query.filter(
            or_(
                and_(ParameterValue.run_type == rt, ParameterValue.run_id == rid)
                for rt, rid in runtime_run_ids
            )
        ).all()
        for pv in pv_rows:
            runtime_pvs[(pv.run_type, pv.name)] = runtime_pvs.get((pv.run_type, pv.name), pv)

    # ── Collect all visible property names ────────────────────────────────────
    names: set[str] = set()
    for _, name in design_props:
        names.add(name)
    for _, name in runtime_pvs:
        names.add(name)

    # ── Resolve each name using in-memory precedence ──────────────────────────
    result: dict[str, Any] = {}
    for name in sorted(names):
        value = _resolve_from_cache(name, kwargs, design_props, runtime_pvs)
        if mask_secrets:
            value = _maybe_mask(name, value, design_props)
        result[name] = value
    return result


def _resolve_from_cache(
    name: str,
    kwargs: dict,
    design_props: dict[tuple[str, str], Property],
    runtime_pvs: dict[tuple[str, str], ParameterValue],
) -> Any:
    """Resolve a single name using pre-fetched in-memory caches."""

    # 1. Runtime overrides — most specific first
    for run_type, kwarg in _RUNTIME_CHAIN:
        run_obj = kwargs.get(kwarg)
        if run_obj is not None:
            pv = runtime_pvs.get((run_type, name))
            if pv is not None and pv.run_id == run_obj.id:
                return _coerce_with_design_type(pv.value, name, kwargs)

    # 2. Design-time — most specific first
    for owner_type, kwarg in _DESIGN_CHAIN:
        owner_obj = kwargs.get(kwarg)
        if owner_obj is not None:
            prop = design_props.get((owner_type, name))
            if prop is not None and prop.owner_id == owner_obj.id:
                return prop.coerced_value()

    return None


def _maybe_mask(
    name: str,
    value: Any,
    design_props: dict[tuple[str, str], Property],
) -> Any:
    """Return '***' if any design-time definition of *name* is a secret."""
    for (_, prop_name), prop in design_props.items():
        if prop_name == name and prop.value_type == "secret":
            return "***"
    return value


# ─────────────────────────────────────────────────────────────────────────────
# Run-trigger validation
# ─────────────────────────────────────────────────────────────────────────────


def validate_runtime_properties(pipeline, runtime_props: dict) -> list[str]:
    """Validate *runtime_props* against the pipeline's design-time property definitions.

    Checks performed:
      1. Unknown keys — keys in runtime_props that have no matching Property defined
         anywhere in the pipeline → product hierarchy.
      2. Missing required — Property records with is_required=True that are absent
         from runtime_props AND have no default value.

    Returns a (possibly empty) list of human-readable error strings.
    Callers should reject the trigger request when the list is non-empty.
    """
    from sqlalchemy import and_, or_

    product = pipeline.product if pipeline else None

    # Collect owner ids for this pipeline's hierarchy
    owner_pairs: list[tuple[str, str]] = [("pipeline", pipeline.id)]
    if product:
        owner_pairs.append(("product", product.id))

    # Include all stages and tasks under this pipeline
    for stage in pipeline.stages or []:
        owner_pairs.append(("stage", stage.id))
        for task in stage.tasks or []:
            owner_pairs.append(("task", task.id))

    defined_props: list[Property] = Property.query.filter(
        or_(and_(Property.owner_type == ot, Property.owner_id == oid) for ot, oid in owner_pairs)
    ).all()

    defined_names = {p.name for p in defined_props}
    errors: list[str] = []

    # 1. Unknown keys
    for key in runtime_props:
        if key not in defined_names:
            errors.append(f"Unknown property '{key}': not defined on this pipeline.")

    # 2. Missing required properties (only at pipeline + product level — stage/task
    #    required properties are validated at task execution time, not trigger time)
    trigger_owner_pairs = [("pipeline", pipeline.id)]
    if product:
        trigger_owner_pairs.append(("product", product.id))

    for prop in defined_props:
        if (
            prop.is_required
            and prop.value is None
            and prop.owner_type in ("pipeline", "product")
            and (prop.owner_type, prop.owner_id) in {(ot, oid) for ot, oid in trigger_owner_pairs}
            and prop.name not in runtime_props
        ):
            errors.append(
                f"Required property '{prop.name}' (defined on {prop.owner_type}) "
                f"must be supplied in runtime_properties."
            )

    return errors
