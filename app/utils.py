"""Shared utilities used across route handlers."""

from __future__ import annotations

from flask import request


def paginate(query, default_limit: int = 50, max_limit: int = 200):
    """Apply limit/offset pagination from query-string params to a SQLAlchemy query.

    Query params:
        limit  — number of items to return (default 50, max 200)
        offset — number of items to skip   (default 0)

    Returns:
        (items, meta) where meta = {"total": int, "limit": int, "offset": int}
    """
    try:
        limit = min(int(request.args.get("limit", default_limit)), max_limit)
    except (TypeError, ValueError):
        limit = default_limit
    try:
        offset = max(int(request.args.get("offset", 0)), 0)
    except (TypeError, ValueError):
        offset = 0

    total = query.count()
    items = query.limit(limit).offset(offset).all()
    return items, {"total": total, "limit": limit, "offset": offset}
