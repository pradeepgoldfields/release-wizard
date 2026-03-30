"""Redis-backed caching service.

Provides a thin wrapper around redis-py with graceful degradation:
if Redis is unavailable the application continues to work without caching.

Cache keys and TTLs:
  products            30 s
  environments        30 s
  agent_pools         30 s
  plugins             30 s
  compliance_rules    60 s

Call ``invalidate(key)`` (or ``invalidate_prefix(prefix)``) from mutating
routes to keep the cache coherent.
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)

_redis = None  # module-level connection; initialised lazily


def _client():
    """Return the Redis client, connecting on first call.  Returns None on failure."""
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis  # noqa: PLC0415
        from flask import current_app  # noqa: PLC0415

        url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        _redis = redis.Redis.from_url(
            url, socket_connect_timeout=1, socket_timeout=1, decode_responses=True
        )
        _redis.ping()  # fail fast
        log.debug("Redis connected at %s", url)
    except Exception as exc:
        log.debug("Redis unavailable (%s) — caching disabled", exc)
        _redis = None
    return _redis


def get(key: str) -> Any | None:
    """Return the cached value for *key*, or None if missing / Redis down."""
    try:
        client = _client()
        if client is None:
            return None
        raw = client.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        log.debug("cache.get(%s) error: %s", key, exc)
        return None


def set(key: str, value: Any, ttl: int = 30) -> None:
    """Store *value* under *key* with a TTL in seconds."""
    try:
        client = _client()
        if client is None:
            return
        client.setex(key, ttl, json.dumps(value))
    except Exception as exc:
        log.debug("cache.set(%s) error: %s", key, exc)


def invalidate(key: str) -> None:
    """Delete a single cache key."""
    try:
        client = _client()
        if client:
            client.delete(key)
    except Exception as exc:
        log.debug("cache.invalidate(%s) error: %s", key, exc)


def invalidate_prefix(prefix: str) -> None:
    """Delete all keys that start with *prefix* (uses SCAN, not KEYS)."""
    try:
        client = _client()
        if client is None:
            return
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match=f"{prefix}*", count=100)
            if keys:
                client.delete(*keys)
            if cursor == 0:
                break
    except Exception as exc:
        log.debug("cache.invalidate_prefix(%s) error: %s", prefix, exc)
