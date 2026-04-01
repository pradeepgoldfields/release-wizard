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
        ApprovalDecision,
        FeatureToggle,
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
    from app.routes.feature_toggles import feature_toggles_bp
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
    app.register_blueprint(feature_toggles_bp)
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
            _ensure_builtin_roles()
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

    # ── Migration 002: roles.is_builtin ──────────────────────────────────────
    role_cols = {c["name"] for c in inspector.get_columns("roles")}
    if "is_builtin" not in role_cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE roles ADD COLUMN is_builtin BOOLEAN DEFAULT 0 NOT NULL"))
            conn.commit()
        log.info("schema_migration", extra={"migration": "roles.is_builtin added"})

    # ── Migration 003: users.is_builtin ──────────────────────────────────────
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "is_builtin" not in user_cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_builtin BOOLEAN DEFAULT 0 NOT NULL"))
            conn.commit()
        log.info("schema_migration", extra={"migration": "users.is_builtin added"})

    # ── Migration 004: tasks.execution_mode ──────────────────────────────────
    task_cols = {c["name"] for c in inspector.get_columns("tasks")}
    if "execution_mode" not in task_cols:
        with engine.connect() as conn:
            conn.execute(
                text("ALTER TABLE tasks ADD COLUMN execution_mode VARCHAR(32) DEFAULT 'sequential'")
            )
            conn.commit()
        log.info("schema_migration", extra={"migration": "tasks.execution_mode added"})

    # ── Migration 006: tasks — kind, gate, approval, run_condition ───────────
    task_cols = {c["name"] for c in inspector.get_columns("tasks")}
    new_task_cols = {
        "kind":                    "VARCHAR(32) DEFAULT 'script'",
        "gate_script":             "TEXT DEFAULT ''",
        "gate_language":           "VARCHAR(32) DEFAULT 'bash'",
        "approval_approvers":      "TEXT DEFAULT '[]'",
        "approval_required_count": "INTEGER DEFAULT 0",
        "approval_timeout":        "INTEGER DEFAULT 0",
        "run_condition":           "VARCHAR(32) DEFAULT 'always'",
    }
    for col, col_def in new_task_cols.items():
        if col not in task_cols:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE tasks ADD COLUMN {col} {col_def}"))
                conn.commit()
            log.info("schema_migration", extra={"migration": f"tasks.{col} added"})

    # ── Migration 007: stages — entry_gate, exit_gate, run_condition ─────────
    stage_cols_all = {c["name"] for c in inspector.get_columns("stages")}
    new_stage_cols = {
        "entry_gate":    "TEXT DEFAULT '{}'",
        "exit_gate":     "TEXT DEFAULT '{}'",
        "run_condition": "VARCHAR(32) DEFAULT 'always'",
    }
    for col, col_def in new_stage_cols.items():
        if col not in stage_cols_all:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE stages ADD COLUMN {col} {col_def}"))
                conn.commit()
            log.info("schema_migration", extra={"migration": f"stages.{col} added"})

    # ── Migration 008: approval_decisions table ───────────────────────────────
    existing_tables = set(inspector.get_table_names())
    if "approval_decisions" not in existing_tables:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE approval_decisions (
                    id VARCHAR(64) PRIMARY KEY,
                    task_run_id VARCHAR(64) NOT NULL REFERENCES task_runs(id),
                    user_id VARCHAR(64) NOT NULL REFERENCES users(id),
                    decision VARCHAR(16) NOT NULL,
                    comment TEXT,
                    decided_at DATETIME
                )
            """))
            conn.commit()
        log.info("schema_migration", extra={"migration": "approval_decisions table created"})

    # ── Migration 009: feature_toggles table ─────────────────────────────────
    existing_tables = set(inspector.get_table_names())
    if "feature_toggles" not in existing_tables:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE feature_toggles (
                    id VARCHAR(64) PRIMARY KEY,
                    key VARCHAR(128) UNIQUE NOT NULL,
                    label VARCHAR(256) NOT NULL,
                    description TEXT,
                    category VARCHAR(64) DEFAULT 'general',
                    enabled BOOLEAN DEFAULT 0 NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))
            conn.commit()
        log.info("schema_migration", extra={"migration": "feature_toggles table created"})

    # ── Migration 005: users.persona (orphaned — nulled out, not dropped) ────
    # The persona column is no longer used by the application.  SQLite <3.35
    # does not support DROP COLUMN, so we leave the column in place but clear
    # any stale values so they don't cause confusion if someone inspects the DB.
    user_cols_now = {c["name"] for c in inspector.get_columns("users")}
    if "persona" in user_cols_now:
        with engine.connect() as conn:
            conn.execute(text("UPDATE users SET persona = NULL WHERE persona IS NOT NULL"))
            conn.commit()
        log.info("schema_migration", extra={"migration": "users.persona nulled (deprecated)"})


def _ensure_builtin_roles() -> None:
    """Upsert the two built-in roles on every startup.

    This makes fresh installs work without running seed_data.py.
    Existing roles are updated to reflect the current permission set.
    """
    from app.models.auth import Role  # noqa: PLC0415
    from app.services.id_service import resource_id  # noqa: PLC0415

    _ALL_PERMS = [
        "products:view","products:create","products:edit","products:delete",
        "applications:view","applications:create","applications:edit","applications:delete",
        "pipelines:view","pipelines:create","pipelines:edit","pipelines:delete","pipelines:execute","pipelines:run",
        "releases:view","releases:create","releases:edit","releases:delete","releases:execute","releases:approve",
        "tasks:view","tasks:create","tasks:edit","tasks:delete","tasks:execute",
        "stages:view","stages:create","stages:edit","stages:delete","stages:execute",
        "environments:view","environments:create","environments:edit","environments:delete",
        "templates:view","templates:create","templates:edit","templates:delete",
        "webhooks:view","webhooks:create","webhooks:edit","webhooks:delete",
        "plugins:view","plugins:install","plugins:configure","plugins:delete",
        "agent-pools:view","agent-pools:create","agent-pools:edit","agent-pools:delete",
        "vault:view","vault:create","vault:reveal","vault:delete",
        "compliance:view","compliance:edit","compliance:approve",
        "app-dictionary:view","app-dictionary:edit",
        "monitoring:view","monitoring:configure",
        "users:view","users:create","users:edit","users:delete",
        "groups:view","groups:create","groups:edit","groups:delete",
        "roles:view","roles:create","roles:edit","roles:delete",
        "permissions:view","permissions:grant","permissions:revoke","permissions:change",
        "global-vars:view","global-vars:edit",
    ]

    _PRODUCT_ADMIN_PERMS = [
        "products:view","products:create","products:edit","products:delete",
        "applications:view","applications:create","applications:edit","applications:delete",
        "pipelines:view","pipelines:create","pipelines:edit","pipelines:delete","pipelines:execute","pipelines:run",
        "releases:view","releases:create","releases:edit","releases:delete","releases:execute","releases:approve",
        "tasks:view","tasks:create","tasks:edit","tasks:delete","tasks:execute",
        "stages:view","stages:create","stages:edit","stages:delete","stages:execute",
        "environments:view","templates:view","templates:create","templates:edit",
        "webhooks:view","webhooks:create","webhooks:edit",
        "vault:view","compliance:view","compliance:edit",
        "monitoring:view","global-vars:view",
        "permissions:view","permissions:grant","permissions:revoke","permissions:change",
        "users:view","groups:view","roles:view","roles:create","roles:edit",
    ]

    builtin_specs = [
        {
            "name": "system-administrator",
            "permissions": _ALL_PERMS,
            "description": "Built-in system administrator — full access to all resources and features",
        },
        {
            "name": "product-admin",
            "permissions": _PRODUCT_ADMIN_PERMS,
            "description": "Built-in product super-user — full control over all product resources and member access",
        },
    ]

    for spec in builtin_specs:
        role = Role.query.filter_by(name=spec["name"]).first()
        if role:
            role.permissions = ",".join(spec["permissions"])
            role.is_builtin = True
        else:
            role = Role(
                id=resource_id("role"),
                name=spec["name"],
                permissions=",".join(spec["permissions"]),
                description=spec["description"],
                is_builtin=True,
            )
            db.session.add(role)

    try:
        db.session.commit()
        log.info("builtin_roles_ensured")
    except Exception:  # noqa: BLE001
        db.session.rollback()
        log.warning("builtin_roles_upsert_failed")
        return

    # Ensure the built-in admin user has a system-administrator binding so that
    # the ISO 27001 compliance check (A.5.15) can detect RBAC is active.
    from app.models.auth import RoleBinding, User  # noqa: PLC0415

    admin_user = User.query.filter_by(username="admin").first()
    sys_admin_role = Role.query.filter_by(name="system-administrator").first()
    if admin_user and sys_admin_role:
        existing_binding = RoleBinding.query.filter_by(
            user_id=admin_user.id,
            role_id=sys_admin_role.id,
            scope="organization",
        ).first()
        if not existing_binding:
            binding = RoleBinding(
                id=resource_id("rb"),
                role_id=sys_admin_role.id,
                user_id=admin_user.id,
                scope="organization",
            )
            db.session.add(binding)
            try:
                db.session.commit()
                log.info("admin_system_binding_created")
            except Exception:  # noqa: BLE001
                db.session.rollback()
                log.warning("admin_system_binding_failed")
