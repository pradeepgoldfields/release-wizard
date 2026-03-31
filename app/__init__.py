"""Conduit application factory.

Creates and configures a Flask application instance using the
application-factory pattern so that multiple instances (test, production)
can be created independently without side effects.
"""

from __future__ import annotations

import time

from flask import Flask

from app.extensions import db, migrate

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

    app.config.from_object(config or Config)

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
    from app.routes.metrics import metrics_bp
    from app.routes.compliance import compliance_bp
    from app.routes.environments import environments_bp
    from app.routes.health import health_bp
    from app.routes.main import main_bp
    from app.routes.maturity import maturity_bp
    from app.routes.pipelines import pipelines_bp
    from app.routes.plugins import plugins_bp
    from app.routes.products import products_bp
    from app.routes.properties import properties_bp
    from app.routes.releases import releases_bp
    from app.routes.runs import runs_bp
    from app.routes.framework_controls import framework_controls_bp
    from app.routes.templates import templates_bp
    from app.routes.settings import settings_bp
    from app.routes.swagger import openapi_bp, swagger_bp
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
            from flask import g, jsonify, request

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
    except Exception:
        pass  # table may not exist yet on first boot
