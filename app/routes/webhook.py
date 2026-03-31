"""Webhook API — inbound trigger endpoints for pipeline runs.

Public trigger endpoint (no JWT required):
  POST /api/v1/webhooks/<webhook_id>/trigger
      Header: X-Webhook-Token: <token>
      Body:   any JSON payload

Management endpoints (JWT required):
  GET/POST    /api/v1/webhooks
  GET/PUT/DEL /api/v1/webhooks/<id>
  GET         /api/v1/webhooks/<id>/deliveries
"""

from __future__ import annotations

import json
import secrets

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models.pipeline import Pipeline
from app.models.webhook import Webhook, WebhookDelivery
from app.services.id_service import resource_id
from app.services.run_service import start_pipeline_run

webhook_bp = Blueprint("webhook", __name__, url_prefix="/api/v1/webhooks")


def _current_username() -> str:
    user = getattr(g, "current_user", None)
    return user.username if user else "system"


def _require_admin():
    user = getattr(g, "current_user", None)
    if not user or getattr(user, "persona", None) != "PlatformAdmin":
        return jsonify({"error": "Admin required"}), 403
    return None


@webhook_bp.get("")
def list_webhooks():
    items = Webhook.query.order_by(Webhook.name).all()
    return jsonify([w.to_dict() for w in items])


@webhook_bp.post("")
def create_webhook():
    err = _require_admin()
    if err:
        return err
    data = request.get_json(force=True) or {}
    pipeline_id = (data.get("pipeline_id") or "").strip()
    name = (data.get("name") or "").strip()
    if not pipeline_id or not name:
        return jsonify({"error": "pipeline_id and name are required"}), 400
    db.get_or_404(Pipeline, pipeline_id)
    token = data.get("token") or secrets.token_hex(32)
    w = Webhook(
        id=resource_id("wh"),
        name=name,
        pipeline_id=pipeline_id,
        token=token,
        description=data.get("description", ""),
        is_active=True,
        created_by=_current_username(),
    )
    db.session.add(w)
    db.session.commit()
    result = w.to_dict()
    result["token"] = token  # expose token only on creation
    return jsonify(result), 201


@webhook_bp.get("/<webhook_id>")
def get_webhook(webhook_id: str):
    w = db.get_or_404(Webhook, webhook_id)
    return jsonify(w.to_dict())


@webhook_bp.put("/<webhook_id>")
def update_webhook(webhook_id: str):
    err = _require_admin()
    if err:
        return err
    w = db.get_or_404(Webhook, webhook_id)
    data = request.get_json(force=True) or {}
    if "name" in data:
        w.name = data["name"]
    if "description" in data:
        w.description = data["description"]
    if "is_active" in data:
        w.is_active = bool(data["is_active"])
    if data.get("regenerate_token"):
        w.token = secrets.token_hex(32)
    db.session.commit()
    result = w.to_dict()
    if data.get("regenerate_token"):
        result["token"] = w.token
    return jsonify(result)


@webhook_bp.delete("/<webhook_id>")
def delete_webhook(webhook_id: str):
    err = _require_admin()
    if err:
        return err
    w = db.get_or_404(Webhook, webhook_id)
    db.session.delete(w)
    db.session.commit()
    return jsonify({"deleted": webhook_id})


@webhook_bp.get("/<webhook_id>/deliveries")
def list_deliveries(webhook_id: str):
    db.get_or_404(Webhook, webhook_id)
    deliveries = (
        WebhookDelivery.query.filter_by(webhook_id=webhook_id)
        .order_by(WebhookDelivery.triggered_at.desc())
        .limit(50)
        .all()
    )
    return jsonify([d.to_dict() for d in deliveries])


@webhook_bp.get("/<webhook_id>/token")
def reveal_token(webhook_id: str):
    """Return the webhook token — admin only."""
    err = _require_admin()
    if err:
        return err
    w = db.get_or_404(Webhook, webhook_id)
    return jsonify({"token": w.token})


@webhook_bp.post("/<webhook_id>/trigger")
def trigger_webhook(webhook_id: str):
    """Public endpoint — authenticated by X-Webhook-Token header."""
    w = db.get_or_404(Webhook, webhook_id)
    if not w.is_active:
        return jsonify({"error": "Webhook is disabled"}), 403

    token = request.headers.get("X-Webhook-Token", "")
    if not secrets.compare_digest(token, w.token):
        return jsonify({"error": "Invalid token"}), 401

    payload = request.get_json(silent=True) or {}
    payload_json = json.dumps(payload)

    # Extract common CI fields from payload for pipeline run
    commit_sha = payload.get("after") or payload.get("commit_sha") or payload.get("sha")
    artifact_id = payload.get("artifact_id")
    triggered_by = (
        payload.get("pusher", {}).get("name")
        if isinstance(payload.get("pusher"), dict)
        else payload.get("triggered_by", "webhook")
    )

    try:
        from flask import current_app  # noqa: PLC0415

        run = start_pipeline_run(
            pipeline_id=w.pipeline_id,
            commit_sha=commit_sha,
            artifact_id=artifact_id,
            triggered_by=triggered_by or "webhook",
            runtime_properties={"webhook": {"payload": payload}},
            app=current_app._get_current_object(),
        )
        pipeline_run_id = run.id
        status = "triggered"
    except Exception as exc:
        pipeline_run_id = None
        status = f"error: {exc}"

    delivery = WebhookDelivery(
        id=resource_id("whdel"),
        webhook_id=webhook_id,
        pipeline_run_id=pipeline_run_id,
        payload=payload_json,
        status=status,
    )
    db.session.add(delivery)
    db.session.commit()

    if pipeline_run_id:
        return jsonify(
            {"delivery_id": delivery.id, "pipeline_run_id": pipeline_run_id, "status": "triggered"}
        ), 202
    return jsonify({"delivery_id": delivery.id, "status": status}), 500
