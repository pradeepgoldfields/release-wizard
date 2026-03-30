"""Release Wizard application factory.

Creates and configures a Flask application instance using the
application-factory pattern so that multiple instances (test, production)
can be created independently without side effects.
"""

from __future__ import annotations

from flask import Flask

from app.extensions import db, migrate


def create_app(config=None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config: An optional configuration object.  If omitted, defaults to
                :class:`app.config.Config` (reads from environment variables).

    Returns:
        A fully configured :class:`flask.Flask` application instance.
    """
    app = Flask(__name__)

    if config:
        app.config.from_object(config)

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
        Pipeline,
        PipelineRun,
        Plugin,
        PluginConfig,
        Product,
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
    from app.routes.compliance import compliance_bp
    from app.routes.environments import environments_bp
    from app.routes.health import health_bp
    from app.routes.main import main_bp
    from app.routes.pipelines import pipelines_bp
    from app.routes.plugins import plugins_bp
    from app.routes.products import products_bp
    from app.routes.releases import releases_bp
    from app.routes.runs import runs_bp
    from app.routes.swagger import openapi_bp, swagger_bp
    from app.routes.users import users_bp
    from app.routes.vault import vault_bp
    from app.routes.webhook import webhook_bp
    from app.routes.yaml_io import yaml_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(environments_bp)
    app.register_blueprint(agents_bp)
    app.register_blueprint(pipelines_bp)
    app.register_blueprint(releases_bp)
    app.register_blueprint(runs_bp)
    app.register_blueprint(compliance_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(yaml_bp)
    app.register_blueprint(plugins_bp)
    app.register_blueprint(vault_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(swagger_bp)
    app.register_blueprint(openapi_bp)

    # JWT guard — skip public paths
    _PUBLIC = {
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/healthz",
        "/readyz",
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

    return app
