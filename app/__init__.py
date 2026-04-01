"""Conduit application factory.

Creates and configures a Flask application instance using the
application-factory pattern so that multiple instances (test, production)
can be created independently without side effects.
"""

from __future__ import annotations

import logging
import time
import uuid

from flask import Flask, g, request

from app.extensions import db, migrate
from app.logging_config import configure_logging

log = logging.getLogger(__name__)

# Startup timestamp used as cache-buster for static assets
_BOOT_TS = str(int(time.time()))


def create_app(config=None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config: An optional configuration object.  If omitted, defaults to
                :class:`app.config.Config` (reads from environment variables).

    Returns:
        A fully configured :class:`flask.Flask` application instance.
    """
    app = Flask(__name__)

    from app.config import Config

    cfg = config or Config
    app.config.from_object(cfg)

    # Configure structured JSON logging as early as possible
    configure_logging(app.config.get("LOG_LEVEL", "INFO"))

    db.init_app(app)
    migrate.init_app(app, db)

    # Register all models so Flask-Migrate can detect them
    from app.models import (  # noqa: F401
        AgentPool,
        ApplicationArtifact,
        AuditEvent,
        ComplianceRule,
        Environment,
        Group,
        ParameterValue,
        Pipeline,
        PipelineRun,
        PlatformSetting,
        Plugin,
        PluginConfig,
        Product,
        Property,
        Release,
        ReleaseRun,
        Role,
        RoleBinding,
        Stage,
        StageRun,
        Task,
        TaskRun,
        User,
        VaultSecret,
        Webhook,
        WebhookDelivery,
    )
    from app.routes.agents import agents_bp
    from app.routes.auth import _current_user, auth_bp, ensure_admin_user
    from app.routes.chat import chat_bp
    from app.routes.compliance import compliance_bp
    from app.routes.environments import environments_bp
    from app.routes.framework_controls import framework_controls_bp
    from app.routes.health import health_bp
    from app.routes.main import main_bp
    from app.routes.maturity import maturity_bp
    from app.routes.metrics import metrics_bp
    from app.routes.pipelines import pipelines_bp
    from app.routes.plugins import plugins_bp
    from app.routes.products import products_bp
    from app.routes.properties import properties_bp
    from app.routes.releases import releases_bp
    from app.routes.runs import runs_bp
    from app.routes.settings import settings_bp
    from app.routes.swagger import openapi_bp, swagger_bp
    from app.routes.templates import templates_bp
    from app.routes.users import users_bp
    from app.routes.vault import vault_bp
    from app.routes.webhook import webhook_bp
    from app.routes.yaml_io import yaml_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(framework_controls_bp)
    app.register_blueprint(templates_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(environments_bp)
    app.register_blueprint(agents_bp)
    app.register_blueprint(pipelines_bp)
    app.register_blueprint(properties_bp)
    app.register_blueprint(releases_bp)
    app.register_blueprint(runs_bp)
    app.register_blueprint(compliance_bp)
    app.register_blueprint(maturity_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(yaml_bp)
    app.register_blueprint(plugins_bp)
    app.register_blueprint(vault_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(swagger_bp)
    app.register_blueprint(openapi_bp)

    # Inject cache-buster version into all Jinja templates
    @app.context_processor
    def inject_static_version():
        return {"v": _BOOT_TS}

    # ── Request correlation ID + structured access log ────────────────────────
    @app.before_request
    def _attach_request_id() -> None:
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        g.request_start = time.perf_counter()

    @app.after_request
    def _log_request(response):
        # Skip static assets and health probes to avoid log noise
        if not request.path.startswith("/static") and request.path not in ("/healthz", "/readyz"):
            duration_ms = round(
                (time.perf_counter() - g.get("request_start", time.perf_counter())) * 1000
            )
            log.info(
                "%s %s %s",
                request.method,
                request.path,
                response.status_code,
                extra={
                    "request_id": g.get("request_id"),
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
        response.headers["X-Request-ID"] = g.get("request_id", "")
        return response

    # JWT guard — skip public paths
    _PUBLIC = {
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/healthz",
        "/readyz",
        "/metrics",
    }

    if not app.config.get("TESTING"):

        @app.before_request
        def require_auth():
            from flask import jsonify

            path = request.path
            # Allow public paths and anything under the Swagger/docs UI
            if (
                path in _PUBLIC
                or path.startswith("/api/v1/docs")
                or path.startswith("/static")
                or path.startswith("/api/v1/webhooks/")
                and path.endswith("/trigger")
            ):
                return None
            if not path.startswith("/api/v1"):
                return None  # serve HTML pages unauthenticated
            user = _current_user()
            if not user:
                return jsonify({"error": "Authentication required", "code": "UNAUTHENTICATED"}), 401
            g.current_user = user
            return None

    # Seed default admin on first boot (skip during testing)
    if not app.config.get("TESTING"):
        with app.app_context():
            db.create_all()
            _apply_schema_migrations()
            ensure_admin_user(app)
            _load_db_settings(app)

    return app


def _load_db_settings(app) -> None:
    """Load any settings stored in the DB into app.config (overrides env vars)."""
    try:
        from app.models.setting import PlatformSetting

        for row in PlatformSetting.query.all():
            if row.value:
                app.config[row.key] = row.value
    except Exception:  # noqa: BLE001 — table may not exist yet on first boot
        log.debug("DB settings not yet available (first boot)")
        pass


def _apply_schema_migrations() -> None:
    """Apply additive schema changes that db.create_all() cannot handle.

    Each migration is idempotent: check whether the column/index exists before
    running ALTER TABLE.  Works for SQLite, PostgreSQL, and Oracle.
    """
    from sqlalchemy import inspect, text  # noqa: PLC0415

    engine = db.engine
    inspector = inspect(engine)

    # ── Migration 001: stages.execution_mode ─────────────────────────────────
    stage_cols = {c["name"] for c in inspector.get_columns("stages")}
    if "execution_mode" not in stage_cols:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "ALTER TABLE stages ADD COLUMN execution_mode VARCHAR(16) DEFAULT 'sequential'"
                )
            )
            conn.commit()
        log.info("schema_migration", extra={"migration": "stages.execution_mode added"})
