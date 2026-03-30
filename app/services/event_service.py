"""Pipeline event publishing service.

Publishes structured events to Kafka or NATS when pipeline/stage/task
runs change state. Degrades gracefully when neither broker is configured.

Configuration (environment variables):
  KAFKA_BOOTSTRAP_SERVERS  e.g. ``kafka:9092``           → uses kafka-python
  NATS_URL                 e.g. ``nats://nats:4222``     → uses nats-py
  EVENT_TOPIC              Kafka topic / NATS subject prefix (default: ``release-wizard``)

If both are set, Kafka takes precedence. If neither is set, publish() is a no-op.

Event envelope (JSON):
  {
    "event":      "pipeline.run.started" | "pipeline.run.finished" | ...,
    "timestamp":  "2026-03-30T12:00:00Z",
    "source":     "release-wizard",
    "data":       { ...resource-specific fields... }
  }
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger(__name__)

_TOPIC = os.getenv("EVENT_TOPIC", "release-wizard")

# ── Lazy broker clients ───────────────────────────────────────────────────────

_kafka_producer = None
_nats_connected = False


def _get_kafka_producer():
    global _kafka_producer
    if _kafka_producer is not None:
        return _kafka_producer
    servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
    if not servers:
        return None
    try:
        from kafka import KafkaProducer  # noqa: PLC0415

        _kafka_producer = KafkaProducer(
            bootstrap_servers=servers.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            request_timeout_ms=5000,
            retries=3,
        )
        log.info("Kafka producer connected to %s", servers)
        return _kafka_producer
    except ImportError:
        log.warning("kafka-python not installed — Kafka publishing disabled")
    except Exception as exc:
        log.warning("Kafka connection failed (%s) — events will be dropped", exc)
    return None


def _publish_kafka(event_type: str, data: dict) -> bool:
    producer = _get_kafka_producer()
    if not producer:
        return False
    topic = f"{_TOPIC}.{event_type}"
    envelope = _build_envelope(event_type, data)
    try:
        producer.send(topic, envelope)
        producer.flush(timeout=5)
        log.debug("Kafka event sent: %s", topic)
        return True
    except Exception as exc:
        log.warning("Kafka publish error (%s): %s", topic, exc)
        return False


async def _publish_nats_async(event_type: str, data: dict) -> bool:
    """Async NATS publish — called via asyncio.run() from the sync wrapper."""
    nats_url = os.getenv("NATS_URL", "")
    if not nats_url:
        return False
    try:
        import nats  # noqa: PLC0415

        subject = f"{_TOPIC}.{event_type}"
        envelope = _build_envelope(event_type, data)
        nc = await nats.connect(nats_url, connect_timeout=5)
        await nc.publish(subject, json.dumps(envelope).encode("utf-8"))
        await nc.flush()
        await nc.close()
        log.debug("NATS event sent: %s", subject)
        return True
    except ImportError:
        log.warning("nats-py not installed — NATS publishing disabled")
    except Exception as exc:
        log.warning("NATS publish error: %s", exc)
    return False


def _publish_nats(event_type: str, data: dict) -> bool:
    import asyncio  # noqa: PLC0415

    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(_publish_nats_async(event_type, data))
    finally:
        loop.close()


def _build_envelope(event_type: str, data: dict) -> dict:
    return {
        "event": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "source": "release-wizard",
        "data": data,
    }


# ── Public API ────────────────────────────────────────────────────────────────


def publish(event_type: str, data: dict[str, Any]) -> None:
    """Publish an event to Kafka or NATS (fire-and-forget, never raises).

    Args:
        event_type: Dot-separated event name, e.g. ``pipeline.run.started``.
        data:       Resource-specific payload dict.
    """
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
    nats_url = os.getenv("NATS_URL", "")

    if kafka_servers:
        _publish_kafka(event_type, data)
    elif nats_url:
        _publish_nats(event_type, data)
    else:
        log.debug("No event broker configured — dropping event: %s", event_type)


# ── Convenience event builders ────────────────────────────────────────────────


def pipeline_run_started(pipeline_run) -> None:
    publish(
        "pipeline.run.started",
        {
            "pipeline_run_id": pipeline_run.id,
            "pipeline_id": pipeline_run.pipeline_id,
            "product_id": pipeline_run.product_id if hasattr(pipeline_run, "product_id") else None,
            "status": pipeline_run.status,
            "triggered_by": pipeline_run.triggered_by,
            "commit_sha": pipeline_run.commit_sha,
        },
    )


def pipeline_run_finished(pipeline_run) -> None:
    publish(
        "pipeline.run.finished",
        {
            "pipeline_run_id": pipeline_run.id,
            "pipeline_id": pipeline_run.pipeline_id,
            "product_id": pipeline_run.product_id if hasattr(pipeline_run, "product_id") else None,
            "status": pipeline_run.status,
            "compliance_rating": pipeline_run.compliance_rating,
            "started_at": pipeline_run.started_at.isoformat() if pipeline_run.started_at else None,
            "finished_at": pipeline_run.finished_at.isoformat()
            if pipeline_run.finished_at
            else None,
        },
    )


def stage_run_finished(stage_run) -> None:
    publish(
        "stage.run.finished",
        {
            "stage_run_id": stage_run.id,
            "pipeline_run_id": stage_run.pipeline_run_id,
            "stage_id": stage_run.stage_id,
            "stage_name": stage_run.stage.name if stage_run.stage else None,
            "status": stage_run.status,
        },
    )


def task_run_finished(task_run) -> None:
    publish(
        "task.run.finished",
        {
            "task_run_id": task_run.id,
            "task_id": task_run.task_id,
            "stage_run_id": task_run.stage_run_id,
            "status": task_run.status,
            "return_code": task_run.return_code,
        },
    )
