"""HTTP handlers for Plugin and PluginConfig resources."""

from __future__ import annotations

import json
from urllib.parse import urljoin

import requests as _requests
from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.plugin import Plugin, PluginConfig
from app.services import cache_service
from app.services.id_service import resource_id

_PLUGINS_CACHE_KEY = "plugins:list"

plugins_bp = Blueprint("plugins", __name__, url_prefix="/api/v1/plugins")

# ── Built-in plugin definitions ───────────────────────────────────────────────

BUILTIN_PLUGINS = [
    {
        "name": "gitlab-ci",
        "display_name": "GitLab CI",
        "description": (
            "Trigger and monitor GitLab CI/CD pipelines. "
            "Supports pipeline triggers, job status polling, and artifact download."
        ),
        "version": "1.0.0",
        "category": "ci",
        "icon": "🦊",
        "author": "Conduit",
        "config_schema": json.dumps(
            {
                "fields": [
                    {
                        "key": "tool_url",
                        "label": "GitLab URL",
                        "type": "url",
                        "required": True,
                        "placeholder": "https://gitlab.example.com",
                    },
                    {
                        "key": "private_token",
                        "label": "Private Token",
                        "type": "password",
                        "required": True,
                    },
                    {
                        "key": "project_id",
                        "label": "Default Project ID",
                        "type": "text",
                        "required": False,
                    },
                ]
            }
        ),
    },
    {
        "name": "jenkins",
        "display_name": "Jenkins",
        "description": (
            "Integrate with Jenkins CI. Trigger builds, poll build status, "
            "retrieve build logs, and download artifacts via the Jenkins REST API."
        ),
        "version": "1.0.0",
        "category": "ci",
        "icon": "🤖",
        "author": "Conduit",
        "config_schema": json.dumps(
            {
                "fields": [
                    {
                        "key": "tool_url",
                        "label": "Jenkins URL",
                        "type": "url",
                        "required": True,
                        "placeholder": "https://jenkins.example.com",
                    },
                    {"key": "username", "label": "Username", "type": "text", "required": True},
                    {
                        "key": "api_token",
                        "label": "API Token",
                        "type": "password",
                        "required": True,
                    },
                    {
                        "key": "job_name",
                        "label": "Default Job Name",
                        "type": "text",
                        "required": False,
                    },
                ]
            }
        ),
    },
    {
        "name": "bitbucket-pipelines",
        "display_name": "Bitbucket Pipelines",
        "description": (
            "Run and monitor Bitbucket Pipelines. "
            "Supports pipeline triggers on branches or tags and status webhooks."
        ),
        "version": "1.0.0",
        "category": "ci",
        "icon": "🪣",
        "author": "Conduit",
        "config_schema": json.dumps(
            {
                "fields": [
                    {"key": "workspace", "label": "Workspace", "type": "text", "required": True},
                    {
                        "key": "repo_slug",
                        "label": "Repository Slug",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "key": "username",
                        "label": "Username / App Password User",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "key": "app_password",
                        "label": "App Password",
                        "type": "password",
                        "required": True,
                    },
                ]
            }
        ),
    },
    {
        "name": "cloudbees-ci",
        "display_name": "CloudBees CI",
        "description": (
            "Enterprise Jenkins integration via CloudBees CI. "
            "Supports managed controllers, Pipelines-as-Code, and RBAC."
        ),
        "version": "1.0.0",
        "category": "ci",
        "icon": "☁️",
        "author": "Conduit",
        "config_schema": json.dumps(
            {
                "fields": [
                    {
                        "key": "tool_url",
                        "label": "CloudBees CI URL",
                        "type": "url",
                        "required": True,
                        "placeholder": "https://cloudbees.example.com/cjoc",
                    },
                    {"key": "username", "label": "Username", "type": "text", "required": True},
                    {
                        "key": "api_token",
                        "label": "API Token",
                        "type": "password",
                        "required": True,
                    },
                    {
                        "key": "controller",
                        "label": "Controller Name",
                        "type": "text",
                        "required": False,
                    },
                ]
            }
        ),
    },
]


def ensure_builtin_plugins() -> None:
    """Seed built-in plugins if they don't exist."""
    for spec in BUILTIN_PLUGINS:
        if not Plugin.query.filter_by(name=spec["name"]).first():
            plugin = Plugin(
                id=resource_id("plg"),
                is_builtin=True,
                **spec,
            )
            db.session.add(plugin)
    db.session.commit()


# ── Plugin CRUD ───────────────────────────────────────────────────────────────


@plugins_bp.get("")
def list_plugins():
    """List all plugins (seeds builtins first)."""
    cached = cache_service.get(_PLUGINS_CACHE_KEY)
    if cached is not None:
        return jsonify(cached)
    ensure_builtin_plugins()
    plugins = Plugin.query.order_by(Plugin.category, Plugin.display_name).all()
    data = [p.to_dict() for p in plugins]
    cache_service.set(_PLUGINS_CACHE_KEY, data, ttl=30)
    return jsonify(data)


@plugins_bp.get("/<plugin_id>")
def get_plugin(plugin_id: str):
    """Get a single plugin with its configurations."""
    plugin = db.get_or_404(Plugin, plugin_id)
    return jsonify(plugin.to_dict(include_configs=True))


@plugins_bp.post("")
def upload_plugin():
    """Register a custom plugin (user-uploaded).

    Required body: ``name``, ``display_name``
    Optional: ``description``, ``version``, ``category``, ``icon``, ``author``,
              ``homepage``, ``config_schema``
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip().lower().replace(" ", "-")
    display_name = (data.get("display_name") or "").strip()
    if not name or not display_name:
        return jsonify({"error": "name and display_name are required"}), 400
    if Plugin.query.filter_by(name=name).first():
        return jsonify({"error": f"Plugin '{name}' already registered"}), 409
    plugin = Plugin(
        id=resource_id("plg"),
        name=name,
        display_name=display_name,
        description=data.get("description"),
        version=data.get("version", "0.1.0"),
        plugin_type="custom",
        category=data.get("category", "custom"),
        icon=data.get("icon", "🔌"),
        is_builtin=False,
        author=data.get("author"),
        homepage=data.get("homepage"),
        config_schema=json.dumps(data.get("config_schema", {})),
    )
    db.session.add(plugin)
    db.session.commit()
    cache_service.invalidate(_PLUGINS_CACHE_KEY)
    return jsonify(plugin.to_dict()), 201


@plugins_bp.patch("/<plugin_id>/toggle")
def toggle_plugin(plugin_id: str):
    """Enable or disable a plugin."""
    plugin = db.get_or_404(Plugin, plugin_id)
    plugin.is_enabled = not plugin.is_enabled
    db.session.commit()
    cache_service.invalidate(_PLUGINS_CACHE_KEY)
    return jsonify({"id": plugin.id, "is_enabled": plugin.is_enabled})


@plugins_bp.delete("/<plugin_id>")
def delete_plugin(plugin_id: str):
    """Delete a custom plugin. Built-in plugins cannot be deleted."""
    plugin = db.get_or_404(Plugin, plugin_id)
    if plugin.is_builtin:
        return jsonify({"error": "Cannot delete built-in plugins"}), 400
    db.session.delete(plugin)
    db.session.commit()
    cache_service.invalidate(_PLUGINS_CACHE_KEY)
    return "", 204


# ── Plugin Config CRUD ────────────────────────────────────────────────────────


@plugins_bp.get("/<plugin_id>/configs")
def list_configs(plugin_id: str):
    """List all configuration instances for a plugin."""
    db.get_or_404(Plugin, plugin_id)
    configs = PluginConfig.query.filter_by(plugin_id=plugin_id).all()
    return jsonify([c.to_dict() for c in configs])


@plugins_bp.post("/<plugin_id>/configs")
def create_config(plugin_id: str):
    """Create a plugin configuration instance.

    Required body: ``config_name``
    Optional: ``tool_url``, ``credentials`` (dict), ``extra_config`` (dict)
    """
    db.get_or_404(Plugin, plugin_id)
    data = request.get_json(silent=True) or {}
    config_name = (data.get("config_name") or "").strip()
    if not config_name:
        return jsonify({"error": "config_name is required"}), 400
    cfg = PluginConfig(
        id=resource_id("pcfg"),
        plugin_id=plugin_id,
        config_name=config_name,
        tool_url=data.get("tool_url"),
        credentials=json.dumps(data.get("credentials", {})),
        extra_config=json.dumps(data.get("extra_config", {})),
    )
    db.session.add(cfg)
    db.session.commit()
    return jsonify(cfg.to_dict()), 201


@plugins_bp.put("/<plugin_id>/configs/<config_id>")
def update_config(plugin_id: str, config_id: str):
    """Update a plugin configuration instance."""
    db.get_or_404(Plugin, plugin_id)
    cfg = PluginConfig.query.filter_by(id=config_id, plugin_id=plugin_id).first_or_404()
    data = request.get_json(silent=True) or {}
    if "config_name" in data:
        cfg.config_name = (data["config_name"] or "").strip() or cfg.config_name
    if "tool_url" in data:
        cfg.tool_url = data["tool_url"]
    if "credentials" in data:
        cfg.credentials = json.dumps(data["credentials"])
    if "extra_config" in data:
        cfg.extra_config = json.dumps(data["extra_config"])
    if "is_active" in data:
        cfg.is_active = bool(data["is_active"])
    db.session.commit()
    return jsonify(cfg.to_dict())


@plugins_bp.delete("/<plugin_id>/configs/<config_id>")
def delete_config(plugin_id: str, config_id: str):
    """Delete a plugin configuration instance."""
    cfg = PluginConfig.query.filter_by(id=config_id, plugin_id=plugin_id).first_or_404()
    db.session.delete(cfg)
    db.session.commit()
    return "", 204


@plugins_bp.post("/<plugin_id>/configs/<config_id>/test")
def test_config(plugin_id: str, config_id: str):
    """Test connectivity for a plugin configuration.

    Performs a basic authenticated HTTP request to the tool URL and returns
    ``{"ok": true/false, "message": "..."}`` — never raises an error status
    so the UI can always display the result.
    """
    plugin = db.get_or_404(Plugin, plugin_id)
    cfg = PluginConfig.query.filter_by(id=config_id, plugin_id=plugin_id).first_or_404()

    tool_url = (cfg.tool_url or "").strip()
    if not tool_url:
        return jsonify({"ok": False, "message": "No tool URL configured"})

    creds: dict = {}
    if cfg.credentials:
        try:
            creds = json.loads(cfg.credentials)
        except (ValueError, TypeError):
            creds = {}

    # Build auth depending on plugin type
    auth = None
    headers: dict[str, str] = {"User-Agent": "ReleaseWizard/1.0"}
    plugin_name = plugin.name or ""

    if plugin_name in ("gitlab-ci",):
        token = creds.get("private_token", "")
        if token:
            headers["PRIVATE-TOKEN"] = token
        probe_url = urljoin(tool_url.rstrip("/") + "/", "api/v4/version")
    elif plugin_name in ("jenkins", "cloudbees-ci"):
        username = creds.get("username", "")
        api_token = creds.get("api_token", "")
        if username and api_token:
            auth = (username, api_token)
        probe_url = tool_url.rstrip("/") + "/api/json?tree=mode"
    elif plugin_name == "bitbucket-pipelines":
        username = creds.get("username", "")
        app_password = creds.get("app_password", "")
        if username and app_password:
            auth = (username, app_password)
        workspace = creds.get("workspace", "")
        probe_url = (
            f"https://api.bitbucket.org/2.0/workspaces/{workspace}"
            if workspace
            else "https://api.bitbucket.org/2.0/user"
        )
    else:
        # Generic: just probe the tool URL
        probe_url = tool_url

    try:
        resp = _requests.get(probe_url, auth=auth, headers=headers, timeout=8, verify=False)  # noqa: S501
        if resp.status_code < 400:
            return jsonify({"ok": True, "message": f"Connected — HTTP {resp.status_code}"})
        return jsonify({"ok": False, "message": f"Server returned HTTP {resp.status_code}"})
    except _requests.exceptions.ConnectionError as exc:
        return jsonify({"ok": False, "message": f"Connection refused: {exc}"})
    except _requests.exceptions.Timeout:
        return jsonify({"ok": False, "message": "Connection timed out after 8 seconds"})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "message": str(exc)})
