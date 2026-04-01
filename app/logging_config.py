"""Centralised logging configuration for Conduit.

Call ``configure_logging(log_level)`` once at application startup (inside
``create_app``).  Every module that does ``logging.getLogger(__name__)`` will
automatically inherit the JSON formatter and the correct level.

JSON log format (one object per line, suitable for ELK / Splunk / Cloud Logging):

    {
      "timestamp": "2025-04-01T12:00:00.000Z",
      "level": "INFO",
      "logger": "app.routes.products",
      "message": "GET /api/v1/products 200",
      "request_id": "01HZ...",   # present on request-scoped log records
      "method": "GET",
      "path": "/api/v1/products",
      "status": 200,
      "duration_ms": 12
    }
"""

from __future__ import annotations

import logging
import sys

from pythonjsonlogger.json import JsonFormatter


class _ConduitFormatter(JsonFormatter):
    """Adds a human-friendly ``timestamp`` key and renames ``levelname`` → ``level``."""

    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
        super().add_fields(log_record, record, message_dict)
        # Rename for readability
        log_record["timestamp"] = log_record.pop("asctime", None) or self.formatTime(record)
        log_record["level"] = log_record.pop("levelname", record.levelname)
        log_record["logger"] = log_record.pop("name", record.name)
        # Drop noisy default keys already captured above
        log_record.pop("taskName", None)


def configure_logging(log_level: str = "INFO") -> None:
    """Configure the root logger with a JSON handler on stdout.

    Safe to call multiple times — re-entrant guard prevents duplicate handlers.
    """
    root = logging.getLogger()

    # Avoid adding duplicate handlers if called more than once (e.g. in tests)
    if any(isinstance(h, logging.StreamHandler) and h.stream is sys.stdout for h in root.handlers):
        root.setLevel(log_level.upper())
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _ConduitFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(log_level.upper())

    # Silence noisy third-party loggers
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
