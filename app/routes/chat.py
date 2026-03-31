"""AI chat agent endpoint."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

chat_bp = Blueprint("chat", __name__, url_prefix="/api/v1/chat")


@chat_bp.post("")
def chat_endpoint():
    """Send a message to the AI assistant and get a reply.

    Body:
        messages: list of {role, content} — full conversation history
    """
    data = request.get_json(silent=True) or {}
    messages = data.get("messages") or []

    if not messages:
        return jsonify({"error": "messages is required"}), 400

    from app.services.chat_service import chat

    current_user = getattr(g, "current_user", None)
    result = chat(messages, current_user=current_user)
    return jsonify(result)
