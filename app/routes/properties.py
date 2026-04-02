"""Property & ParameterValue API endpoints.

Design-time properties (CRUD on definition objects):
  GET    /api/v1/properties/{owner_type}/{owner_id}
  POST   /api/v1/properties/{owner_type}/{owner_id}
  PUT    /api/v1/properties/{owner_type}/{owner_id}/{name}
  DELETE /api/v1/properties/{owner_type}/{owner_id}/{name}

htmx partial fragments (return HTML for direct DOM swap):
  GET    /api/v1/properties/{owner_type}/{owner_id}/partial          — list of cards
  PUT    /api/v1/properties/{owner_type}/{owner_id}/{name}/partial   — single updated card
  DELETE /api/v1/properties/{owner_type}/{owner_id}/{name}/partial   — empty 204

Runtime parameter values (overrides on execution objects):
  GET    /api/v1/parameter-values/{run_type}/{run_id}
  POST   /api/v1/parameter-values/{run_type}/{run_id}
  DELETE /api/v1/parameter-values/{run_type}/{run_id}/{name}

Resolved view (full hierarchy for a pipeline run + optional stage/task context):
  GET    /api/v1/properties/resolve/pipeline-run/{pipeline_run_id}
  GET    /api/v1/properties/resolve/pipeline-run/{pipeline_run_id}/stage-run/{stage_run_id}
  GET    /api/v1/properties/resolve/pipeline-run/{pipeline_run_id}/stage-run/{stage_run_id}/task-run/{task_run_id}
"""

from __future__ import annotations

import html
import json

from flask import Blueprint, jsonify, make_response, request

properties_bp = Blueprint("properties", __name__, url_prefix="/api/v1")

_VALID_OWNER_TYPES = {"product", "pipeline", "stage", "task"}
_VALID_RUN_TYPES = {"pipeline_run", "stage_run", "task_run"}

_TYPE_COLOR: dict[str, str] = {
    "string": "#3b82f6",
    "number": "#10b981",
    "boolean": "#f59e0b",
    "secret": "#8b5cf6",
    "json": "#ec4899",
}
_TYPE_ICON: dict[str, str] = {
    "string": "Aa",
    "number": "12",
    "boolean": "✓✗",
    "secret": "🔒",
    "json": "{}",
}


def _prop_card_html(p_dict: dict, scope_key: str, inherited: dict) -> str:
    """Return the Alpine-powered HTML card for a single property dict.

    This mirrors the _propCard() JS function so htmx PUT can return the
    refreshed card directly and swap it in-place without a JS re-render.
    """
    name = p_dict["name"]
    value_type = p_dict.get("value_type", "string")
    value = p_dict.get("value") or ""
    description = p_dict.get("description") or ""
    is_required = bool(p_dict.get("is_required", False))

    color = _TYPE_COLOR.get(value_type, "#6366f1")
    icon = _TYPE_ICON.get(value_type, "Aa")

    inherited_info = inherited.get(name)
    inherited_html = ""
    if inherited_info:
        ival = (
            "••••••••"
            if inherited_info.get("value_type") == "secret"
            else html.escape(str(inherited_info.get("value") or "not set"))
        )
        inherited_html = (
            f'<div style="font-size:11px;color:#9ca3af;margin-bottom:4px">'
            f"overrides ← {html.escape(inherited_info['source_label'])}: "
            f'<code style="font-size:11px;background:#f3f4f6;padding:1px 5px;border-radius:3px">{ival}</code>'
            f"</div>"
        )

    required_badge = (
        '<span style="font-size:10px;font-weight:600;color:#dc2626;background:#fef2f2;'
        'padding:1px 6px;border-radius:8px;border:1px solid #fecaca">required</span>'
        if is_required
        else ""
    )

    # Displayed value in view mode
    if value_type == "secret":
        display_val = (
            '<span style="font-family:monospace;color:#8b5cf6;font-size:13px">••••••••</span>'
        )
    elif value_type == "boolean":
        bool_color = "#16a34a" if value == "true" else "#9ca3af"
        display_val = f'<span style="font-family:monospace;font-size:13px;font-weight:600;color:{bool_color}">{html.escape(str(value))}</span>'
    elif value_type == "json":
        display_val = f'<pre style="margin:0;font-size:11px;background:#f3f4f6;padding:4px 8px;border-radius:4px;overflow-x:auto;white-space:pre-wrap">{html.escape(str(value))}</pre>'
    elif value_type == "number":
        display_val = f'<span style="font-family:monospace;font-size:13px;color:#10b981">{html.escape(str(value))}</span>'
    else:
        display_val = f'<span style="font-family:monospace;font-size:13px;color:#1f2937">{html.escape(str(value))}</span>'

    init_data = json.dumps(
        {
            "editing": False,
            "saving": False,
            "showSecret": False,
            "valueType": value_type,
            "value": value,
            "description": description,
            "required": is_required,
        }
    ).replace("'", "&#39;")

    safe_scope = scope_key.replace("'", "\\'")
    safe_name = name.replace("'", "\\'")
    h_name = html.escape(name)

    return f"""
<div id="prop-card-{html.escape(scope_key)}-{h_name}"
     x-data='{init_data}'
     @keydown.escape.window="editing = false"
     style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;border-left:3px solid {color};overflow:hidden;transition:box-shadow .15s"
     :style="editing ? 'box-shadow:0 0 0 2px {color}55' : ''">

  <!-- view row -->
  <div x-show="!editing" style="display:flex;align-items:flex-start;gap:12px;padding:12px 14px">
    <div style="width:28px;height:28px;border-radius:6px;background:{color}18;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:{color};flex-shrink:0;margin-top:1px">{icon}</div>
    <div style="flex:1;min-width:0">
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:2px">
        <strong style="font-family:monospace;font-size:13px;color:#1f2937">{h_name}</strong>
        <span x-text="valueType" style="font-size:10px;font-weight:600;color:{color};background:{color}18;padding:1px 7px;border-radius:8px;text-transform:uppercase;letter-spacing:.3px"></span>
        {required_badge}
      </div>
      {inherited_html}
      <div x-show="description" x-text="description" style="font-size:12px;color:#6b7280;margin-bottom:4px"></div>
      <div>{display_val}</div>
    </div>
    <div style="display:flex;gap:4px;flex-shrink:0">
      <button class="btn btn-secondary btn-sm" style="padding:3px 8px;font-size:11px"
        @click="editing = true" title="Edit">✏</button>
      <button class="btn btn-danger btn-sm" style="padding:3px 8px;font-size:11px"
        hx-delete="/api/v1/properties/{html.escape(scope_key.split(":")[0])}/{html.escape(scope_key.split(":")[1] if ":" in scope_key else "")}/{html.escape(name)}/partial"
        hx-target="closest [x-data]"
        hx-swap="outerHTML"
        hx-confirm="Delete property &quot;{h_name}&quot;?"
        title="Delete">✕</button>
    </div>
  </div>

  <!-- edit form -->
  <div x-show="editing" x-cloak
       style="padding:14px;background:#f9fafb;border-top:1px solid #f3f4f6">

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">
      <div class="form-group" style="margin:0">
        <label style="font-size:11px;font-weight:600;color:#4b5563;display:block;margin-bottom:4px">Type</label>
        <select x-model="valueType" class="form-control form-control-sm">
          <option value="string">string</option>
          <option value="number">number</option>
          <option value="boolean">boolean</option>
          <option value="secret">secret</option>
          <option value="json">json</option>
        </select>
      </div>
      <div class="form-group" style="margin:0">
        <label style="font-size:11px;font-weight:600;color:#4b5563;display:block;margin-bottom:4px">Required</label>
        <select x-model="required" class="form-control form-control-sm">
          <option :value="false">No</option>
          <option :value="true">Yes</option>
        </select>
      </div>
    </div>

    <div class="form-group" style="margin-bottom:10px">
      <label style="font-size:11px;font-weight:600;color:#4b5563;display:block;margin-bottom:4px">Value</label>
      <template x-if="valueType === 'string'">
        <input type="text" x-model="value" class="form-control form-control-sm" placeholder="e.g. production">
      </template>
      <template x-if="valueType === 'number'">
        <input type="number" x-model="value" class="form-control form-control-sm">
      </template>
      <template x-if="valueType === 'boolean'">
        <label style="display:inline-flex;align-items:center;gap:10px;cursor:pointer;padding:5px 0">
          <input type="checkbox"
            :checked="value === 'true'"
            @change="value = $event.target.checked ? 'true' : 'false'"
            style="width:16px;height:16px;accent-color:var(--primary)">
          <span x-text="value === 'true' ? 'true' : 'false'"
            style="font-family:monospace;font-size:13px;color:#374151"></span>
        </label>
      </template>
      <template x-if="valueType === 'secret'">
        <div style="position:relative">
          <input :type="showSecret ? 'text' : 'password'"
            x-model="value" class="form-control form-control-sm"
            placeholder="Enter secret value" style="padding-right:36px">
          <button type="button" @click="showSecret = !showSecret"
            style="position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;font-size:13px;color:#9ca3af"
            :title="showSecret ? 'Hide' : 'Show'" x-text="showSecret ? '🙈' : '👁'"></button>
        </div>
      </template>
      <template x-if="valueType === 'json'">
        <textarea x-model="value" class="form-control form-control-sm" rows="3"
          style="font-family:monospace;font-size:12px;resize:vertical"
          placeholder='{{"key": "value"}}'></textarea>
      </template>
    </div>

    <div class="form-group" style="margin-bottom:12px">
      <label style="font-size:11px;font-weight:600;color:#4b5563;display:block;margin-bottom:4px">Description</label>
      <input type="text" x-model="description" class="form-control form-control-sm"
        placeholder="What does this property control?">
    </div>

    <div style="display:flex;gap:8px;align-items:center">
      <button class="btn btn-primary btn-sm" :disabled="saving"
        @click="saving=true; $dispatch('prop-htmx-save', {{scope:'{safe_scope}', name:'{safe_name}', data:$data}})">
        <span x-text="saving ? 'Saving…' : '✓ Save'"></span>
      </button>
      <button class="btn btn-secondary btn-sm" @click="editing = false">✗ Cancel</button>
    </div>
  </div>
</div>"""


def _prop_card_list_html(props: list[dict], scope_key: str, inherited: dict) -> str:
    cards = "".join(_prop_card_html(p, scope_key, inherited) for p in props)
    return (
        f'<div id="prop-card-list" style="display:flex;flex-direction:column;gap:8px">{cards}</div>'
    )


# ── Design-time property endpoints ───────────────────────────────────────────


@properties_bp.get("/properties/<owner_type>/<owner_id>")
def list_properties(owner_type: str, owner_id: str):
    if owner_type not in _VALID_OWNER_TYPES:
        return jsonify({"error": f"Invalid owner_type: {owner_type}"}), 400
    from app.services.property_service import list_properties as _list

    return jsonify([p.to_dict() for p in _list(owner_type, owner_id)])


@properties_bp.post("/properties/<owner_type>/<owner_id>")
def create_property(owner_type: str, owner_id: str):
    if owner_type not in _VALID_OWNER_TYPES:
        return jsonify({"error": f"Invalid owner_type: {owner_type}"}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    from app.services.property_service import set_property

    prop = set_property(
        owner_type,
        owner_id,
        name,
        data.get("value"),
        value_type=data.get("value_type", "string"),
        description=data.get("description"),
        is_required=bool(data.get("is_required", False)),
    )
    return jsonify(prop.to_dict()), 201


@properties_bp.put("/properties/<owner_type>/<owner_id>/<path:name>")
def update_property(owner_type: str, owner_id: str, name: str):
    if owner_type not in _VALID_OWNER_TYPES:
        return jsonify({"error": f"Invalid owner_type: {owner_type}"}), 400
    data = request.get_json(silent=True) or {}
    from app.services.property_service import set_property

    prop = set_property(
        owner_type,
        owner_id,
        name,
        data.get("value"),
        value_type=data.get("value_type", "string"),
        description=data.get("description"),
        is_required=bool(data.get("is_required", False)),
    )
    return jsonify(prop.to_dict())


@properties_bp.delete("/properties/<owner_type>/<owner_id>/<path:name>")
def delete_property(owner_type: str, owner_id: str, name: str):
    if owner_type not in _VALID_OWNER_TYPES:
        return jsonify({"error": f"Invalid owner_type: {owner_type}"}), 400
    from app.services.property_service import delete_property as _del

    _del(owner_type, owner_id, name)
    return "", 204


# ── Runtime parameter value endpoints ────────────────────────────────────────


@properties_bp.get("/parameter-values/<run_type>/<run_id>")
def list_param_values(run_type: str, run_id: str):
    if run_type not in _VALID_RUN_TYPES:
        return jsonify({"error": f"Invalid run_type: {run_type}"}), 400
    from app.services.property_service import list_parameter_values

    return jsonify([pv.to_dict() for pv in list_parameter_values(run_type, run_id)])


@properties_bp.post("/parameter-values/<run_type>/<run_id>")
def set_param_value(run_type: str, run_id: str):
    if run_type not in _VALID_RUN_TYPES:
        return jsonify({"error": f"Invalid run_type: {run_type}"}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    from app.services.property_service import set_parameter_value

    pv = set_parameter_value(run_type, run_id, name, data.get("value"))
    return jsonify(pv.to_dict()), 201


@properties_bp.delete("/parameter-values/<run_type>/<run_id>/<path:name>")
def delete_param_value(run_type: str, run_id: str, name: str):
    if run_type not in _VALID_RUN_TYPES:
        return jsonify({"error": f"Invalid run_type: {run_type}"}), 400
    from app.services.property_service import delete_parameter_value

    delete_parameter_value(run_type, run_id, name)
    return "", 204


# ── Resolved view ─────────────────────────────────────────────────────────────


@properties_bp.get("/properties/resolve/pipeline-run/<pipeline_run_id>")
def resolve_for_pipeline_run(pipeline_run_id: str):
    """Return all resolved properties for a pipeline run (pipeline + product scope)."""
    from app.models.run import PipelineRun
    from app.services.property_service import resolve_all

    run = PipelineRun.query.get_or_404(pipeline_run_id)
    pipeline = run.pipeline
    product = pipeline.product if pipeline else None
    resolved = resolve_all(pipeline_run=run, pipeline=pipeline, product=product)
    return jsonify({"pipeline_run_id": pipeline_run_id, "properties": resolved})


@properties_bp.get("/properties/resolve/pipeline-run/<pipeline_run_id>/stage-run/<stage_run_id>")
def resolve_for_stage_run(pipeline_run_id: str, stage_run_id: str):
    """Return all resolved properties in stage context (task+stage+pipeline+product)."""
    from app.models.run import PipelineRun, StageRun
    from app.services.property_service import resolve_all

    run = PipelineRun.query.get_or_404(pipeline_run_id)
    sr = StageRun.query.get_or_404(stage_run_id)
    pipeline = run.pipeline
    stage = sr.stage
    product = pipeline.product if pipeline else None
    resolved = resolve_all(
        pipeline_run=run,
        stage_run=sr,
        pipeline=pipeline,
        stage=stage,
        product=product,
    )
    return jsonify(
        {
            "pipeline_run_id": pipeline_run_id,
            "stage_run_id": stage_run_id,
            "properties": resolved,
        }
    )


@properties_bp.get(
    "/properties/resolve/pipeline-run/<pipeline_run_id>"
    "/stage-run/<stage_run_id>"
    "/task-run/<task_run_id>"
)
def resolve_for_task_run(pipeline_run_id: str, stage_run_id: str, task_run_id: str):
    """Return all resolved properties at full task-run scope (task+stage+pipeline+product
    with runtime ParameterValue overrides at every level).

    This is the deepest resolution scope and reflects exactly what a task script
    sees in $CDT_PROPS at execution time (secrets masked).
    """
    from app.models.run import PipelineRun, StageRun
    from app.models.task import TaskRun
    from app.services.property_service import resolve_all

    run = PipelineRun.query.get_or_404(pipeline_run_id)
    sr = StageRun.query.get_or_404(stage_run_id)
    tr = TaskRun.query.get_or_404(task_run_id)
    pipeline = run.pipeline
    stage = sr.stage
    task = tr.task
    product = pipeline.product if pipeline else None
    resolved = resolve_all(
        pipeline_run=run,
        stage_run=sr,
        task_run=tr,
        pipeline=pipeline,
        stage=stage,
        task=task,
        product=product,
        mask_secrets=True,
    )
    return jsonify(
        {
            "pipeline_run_id": pipeline_run_id,
            "stage_run_id": stage_run_id,
            "task_run_id": task_run_id,
            "properties": resolved,
        }
    )


# ── htmx partial fragment endpoints ──────────────────────────────────────────
# These return HTML (not JSON) so htmx can swap them directly into the DOM.
# The JS layer calls these when hx-put / hx-delete attributes fire.


def _html_response(body: str, status: int = 200):
    resp = make_response(body, status)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


@properties_bp.get("/properties/<owner_type>/<owner_id>/partial")
def list_properties_partial(owner_type: str, owner_id: str):
    """Return the full card list as an HTML fragment for the given scope."""
    if owner_type not in _VALID_OWNER_TYPES:
        return _html_response(
            f'<div class="alert alert-danger">Invalid owner_type: {html.escape(owner_type)}</div>',
            400,
        )
    from app.services.property_service import list_properties as _list

    scope_key = f"{owner_type}:{owner_id}"
    props = [p.to_dict() for p in _list(owner_type, owner_id)]
    return _html_response(_prop_card_list_html(props, scope_key, {}))


@properties_bp.put("/properties/<owner_type>/<owner_id>/<path:name>/partial")
def update_property_partial(owner_type: str, owner_id: str, name: str):
    """Save a property and return the refreshed card HTML for htmx swap."""
    if owner_type not in _VALID_OWNER_TYPES:
        return _html_response(
            f'<div class="alert alert-danger">Invalid owner_type: {html.escape(owner_type)}</div>',
            400,
        )
    data = request.get_json(silent=True) or {}
    from app.services.property_service import set_property

    prop = set_property(
        owner_type,
        owner_id,
        name,
        data.get("value"),
        value_type=data.get("value_type", "string"),
        description=data.get("description"),
        is_required=bool(data.get("is_required", False)),
    )
    scope_key = f"{owner_type}:{owner_id}"
    return _html_response(_prop_card_html(prop.to_dict(), scope_key, {}))


@properties_bp.delete("/properties/<owner_type>/<owner_id>/<path:name>/partial")
def delete_property_partial(owner_type: str, owner_id: str, name: str):
    """Delete a property; return empty so htmx removes the card from the DOM."""
    if owner_type not in _VALID_OWNER_TYPES:
        return _html_response(
            f'<div class="alert alert-danger">Invalid owner_type: {html.escape(owner_type)}</div>',
            400,
        )
    from app.services.property_service import delete_property as _del

    _del(owner_type, owner_id, name)
    return _html_response("", 200)
