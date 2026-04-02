from __future__ import annotations

import json

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.backlog import BacklogItem
from app.routes._authz import current_user_id, require_product_access
from app.services.id_service import resource_id

backlog_bp = Blueprint("backlog", __name__, url_prefix="/api/v1/products/<product_id>/backlog")


@backlog_bp.get("")
def list_backlog(product_id: str):
    uid = current_user_id()
    err = require_product_access(uid, product_id, "backlog:view")
    if err:
        return err

    q = BacklogItem.query.filter_by(product_id=product_id)

    status = request.args.get("status")
    if status:
        q = q.filter(BacklogItem.status == status)

    priority = request.args.get("priority")
    if priority:
        q = q.filter(BacklogItem.priority == priority)

    item_type = request.args.get("item_type")
    if item_type:
        q = q.filter(BacklogItem.item_type == item_type)

    assigned_to = request.args.get("assigned_to")
    if assigned_to:
        q = q.filter(BacklogItem.assigned_to == assigned_to)

    release_id = request.args.get("release_id")
    if release_id:
        q = q.filter(BacklogItem.release_id == release_id)

    search = request.args.get("q", "").strip()
    if search:
        q = q.filter(BacklogItem.title.ilike(f"%{search}%"))

    items = q.order_by(BacklogItem.created_at.desc()).all()
    return jsonify({"items": [i.to_dict() for i in items], "total": len(items)})


@backlog_bp.post("")
def create_backlog(product_id: str):
    uid = current_user_id()
    err = require_product_access(uid, product_id, "backlog:create")
    if err:
        return err

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    labels = data.get("labels", [])
    if isinstance(labels, list):
        labels = json.dumps(labels)

    item = BacklogItem(
        id=resource_id("backlog"),
        product_id=product_id,
        title=title,
        description=data.get("description", ""),
        item_type=data.get("item_type", "feature"),
        status=data.get("status", "open"),
        priority=data.get("priority", "medium"),
        effort=data.get("effort", 0),
        assigned_to=data.get("assigned_to"),
        release_id=data.get("release_id"),
        pipeline_id=data.get("pipeline_id"),
        labels=labels,
        acceptance_criteria=data.get("acceptance_criteria", ""),
        notes=data.get("notes", ""),
        created_by=uid,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@backlog_bp.get("/<item_id>")
def get_backlog_item(product_id: str, item_id: str):
    uid = current_user_id()
    err = require_product_access(uid, product_id, "backlog:view")
    if err:
        return err

    item = BacklogItem.query.filter_by(id=item_id, product_id=product_id).first_or_404()
    return jsonify(item.to_dict())


@backlog_bp.put("/<item_id>")
def update_backlog_item(product_id: str, item_id: str):
    uid = current_user_id()
    err = require_product_access(uid, product_id, "backlog:edit")
    if err:
        return err

    item = BacklogItem.query.filter_by(id=item_id, product_id=product_id).first_or_404()
    data = request.get_json(silent=True) or {}

    for field in (
        "title",
        "description",
        "item_type",
        "status",
        "priority",
        "effort",
        "assigned_to",
        "release_id",
        "pipeline_id",
        "acceptance_criteria",
        "notes",
    ):
        if field in data:
            setattr(item, field, data[field])

    if "labels" in data:
        labels = data["labels"]
        item.labels = json.dumps(labels) if isinstance(labels, list) else labels

    db.session.commit()
    return jsonify(item.to_dict())


@backlog_bp.delete("/<item_id>")
def delete_backlog_item(product_id: str, item_id: str):
    uid = current_user_id()
    err = require_product_access(uid, product_id, "backlog:delete")
    if err:
        return err

    item = BacklogItem.query.filter_by(id=item_id, product_id=product_id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@backlog_bp.patch("/<item_id>/status")
def patch_backlog_status(product_id: str, item_id: str):
    uid = current_user_id()
    err = require_product_access(uid, product_id, "backlog:edit")
    if err:
        return err

    item = BacklogItem.query.filter_by(id=item_id, product_id=product_id).first_or_404()
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip()
    if not status:
        return jsonify({"error": "status is required"}), 400

    item.status = status
    db.session.commit()
    return jsonify(item.to_dict())
