"""Swagger UI, OpenAPI spec, and technical documentation endpoints."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, render_template_string

SWAGGER_URL = "/api/v1/docs/swagger"
API_URL = "/api/v1/docs/openapi.json"

openapi_bp = Blueprint("openapi", __name__, url_prefix="/api/v1/docs")

# Custom Swagger UI HTML — injects JWT from localStorage automatically
_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Conduit API</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
  <style>body{margin:0}.topbar{display:none}</style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
  <script>
    const ui = SwaggerUIBundle({
      url: "/api/v1/docs/openapi.json",
      dom_id: "#swagger-ui",
      presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIStandalonePreset
      ],
      plugins: [SwaggerUIBundle.plugins.DownloadUrl],
      layout: "StandaloneLayout",
      deepLinking: true,
      persistAuthorization: true,
      onComplete: function() {
        // Auto-authorize from the app's localStorage token
        var token = localStorage.getItem("cdt_token");
        if (token) {
          ui.preauthorizeApiKey("BearerAuth", token);
          console.log("[Swagger] Pre-authorized with session token.");
        }
      }
    });
  </script>
</body>
</html>"""

swagger_bp = Blueprint("swagger", __name__, url_prefix="/api/v1/docs")


@swagger_bp.get("/swagger")
@swagger_bp.get("/swagger/")
def swagger_ui():
    """Serve the Swagger UI with auto-JWT injection."""
    return render_template_string(_SWAGGER_HTML)


@openapi_bp.get("/technical-doc")
def get_technical_doc():
    """Return the technical documentation markdown as plain text."""
    doc_path = Path(__file__).parent.parent.parent / "docs" / "technical-documentation.md"
    try:
        return (
            doc_path.read_text(encoding="utf-8"),
            200,
            {"Content-Type": "text/markdown; charset=utf-8"},
        )
    except FileNotFoundError:
        return jsonify({"error": "Documentation file not found"}), 404


@openapi_bp.get("/admin-guide")
def get_admin_guide():
    """Return the system administrator guide markdown as plain text."""
    doc_path = Path(__file__).parent.parent.parent / "docs" / "admin-guide.md"
    try:
        return (
            doc_path.read_text(encoding="utf-8"),
            200,
            {"Content-Type": "text/markdown; charset=utf-8"},
        )
    except FileNotFoundError:
        return jsonify({"error": "Admin guide not found"}), 404


@openapi_bp.get("/openapi.json")
def openapi_spec():
    """Return the OpenAPI 3.0 specification."""
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "Conduit API",
            "version": "1.0.0",
            "description": (
                "REST API for Conduit — manage products, pipelines, "
                "stages, tasks, releases, agent pools, secrets vault, webhooks, "
                "users, groups, roles, and compliance rules.\n\n"
                "**Authentication**: All endpoints (except `/auth/login` and webhook triggers) "
                "require a Bearer JWT token. Log in via the app — your session token is "
                "pre-loaded in Swagger automatically."
            ),
        },
        "servers": [{"url": "/api/v1", "description": "Current server"}],
        "security": [{"BearerAuth": []}],
        "tags": [
            {"name": "Auth", "description": "Authentication — obtain JWT token"},
            {"name": "Products", "description": "Product CRUD"},
            {"name": "Environments", "description": "Environment CRUD and product attachment"},
            {"name": "Pipelines", "description": "Pipeline and stage management"},
            {"name": "Tasks", "description": "Stage task CRUD and sandbox execution"},
            {"name": "Agent Pools", "description": "Execution environment pools"},
            {"name": "Releases", "description": "Release and pipeline attachment"},
            {"name": "Runs", "description": "Pipeline and release run lifecycle"},
            {"name": "Compliance", "description": "Admission rules and audit events"},
            {"name": "Users", "description": "User, group, role, and RBAC management"},
            {"name": "Vault", "description": "Encrypted secrets storage"},
            {"name": "Webhooks", "description": "Inbound trigger endpoints for pipeline runs"},
            {"name": "YAML", "description": "Export / import resources as YAML"},
            {"name": "Plugins", "description": "Built-in and custom plugin management"},
            {"name": "Settings", "description": "Platform-wide configuration key-value store"},
            {
                "name": "AI Chat",
                "description": "Conversational AI assistant powered by Groq / Llama",
            },
        ],
        "paths": {
            # ── Auth ──────────────────────────────────────────────────────
            "/auth/login": {
                "post": {
                    "tags": ["Auth"],
                    "summary": "Obtain a JWT token",
                    "security": [],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["username", "password"],
                                    "properties": {
                                        "username": {"type": "string", "example": "admin"},
                                        "password": {"type": "string", "example": "admin"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "JWT token + user object"},
                        "401": {"description": "Invalid credentials"},
                    },
                },
            },
            # ── Vault ─────────────────────────────────────────────────────
            "/vault": {
                "get": _op("Vault", "List secrets (values redacted)", "SecretList"),
                "post": _op("Vault", "Create a secret", "Secret", body="SecretInput", status=201),
            },
            "/vault/{secret_id}": {
                "get": _op("Vault", "Get secret metadata", "Secret", path_id="secret_id"),
                "put": _op(
                    "Vault", "Update a secret", "Secret", path_id="secret_id", body="SecretInput"
                ),
                "delete": _del("Vault", path_id="secret_id"),
            },
            "/vault/{secret_id}/reveal": {
                "post": _op("Vault", "Reveal decrypted value", "SecretValue", path_id="secret_id"),
            },
            # ── Webhooks ──────────────────────────────────────────────────
            "/webhooks": {
                "get": _op("Webhooks", "List webhooks", "WebhookList"),
                "post": _op(
                    "Webhooks", "Create a webhook", "Webhook", body="WebhookInput", status=201
                ),
            },
            "/webhooks/{webhook_id}": {
                "get": _op("Webhooks", "Get webhook", "Webhook", path_id="webhook_id"),
                "put": _op(
                    "Webhooks",
                    "Update webhook",
                    "Webhook",
                    path_id="webhook_id",
                    body="WebhookInput",
                ),
                "delete": _del("Webhooks", path_id="webhook_id"),
            },
            "/webhooks/{webhook_id}/trigger": {
                "post": {
                    "tags": ["Webhooks"],
                    "summary": "Trigger a pipeline run via webhook (public, token-authenticated)",
                    "security": [],
                    "parameters": [
                        {
                            "name": "webhook_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "X-Webhook-Token",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "commit_sha": {"type": "string"},
                                        "artifact_id": {"type": "string"},
                                        "triggered_by": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "202": {"description": "Triggered"},
                        "401": {"description": "Invalid token"},
                    },
                },
            },
            "/webhooks/{webhook_id}/deliveries": {
                "get": _op(
                    "Webhooks",
                    "List webhook deliveries",
                    "WebhookDeliveryList",
                    path_id="webhook_id",
                ),
            },
            # ── Products ──────────────────────────────────────────────────
            "/products": {
                "get": _op("Products", "List all products", "ProductList"),
                "post": _op(
                    "Products", "Create a product", "Product", body="ProductInput", status=201
                ),
            },
            "/products/{product_id}": {
                "get": _op("Products", "Get a product", "Product", path_id="product_id"),
                "put": _op(
                    "Products",
                    "Update a product",
                    "Product",
                    path_id="product_id",
                    body="ProductInput",
                ),
                "delete": _del("Products", path_id="product_id"),
            },
            # ── Environments ──────────────────────────────────────────────
            "/environments": {
                "get": _op("Environments", "List all environments", "EnvironmentList"),
                "post": _op(
                    "Environments",
                    "Create an environment",
                    "Environment",
                    body="EnvironmentInput",
                    status=201,
                ),
            },
            "/environments/{env_id}": {
                "get": _op("Environments", "Get an environment", "Environment", path_id="env_id"),
                "put": _op(
                    "Environments",
                    "Update an environment",
                    "Environment",
                    path_id="env_id",
                    body="EnvironmentInput",
                ),
                "delete": _del("Environments", path_id="env_id"),
            },
            "/products/{product_id}/environments": {
                "get": _op(
                    "Environments",
                    "List environments attached to a product",
                    "EnvironmentList",
                    path_id="product_id",
                ),
                "post": _op(
                    "Environments",
                    "Attach environment to product",
                    "AttachResult",
                    path_id="product_id",
                    body="AttachEnvironmentInput",
                ),
            },
            "/products/{product_id}/environments/{env_id}": {
                "delete": _del(
                    "Environments",
                    path_ids=["product_id", "env_id"],
                    summary="Detach environment from product",
                ),
            },
            # ── Pipelines ─────────────────────────────────────────────────
            "/products/{product_id}/pipelines": {
                "get": _op(
                    "Pipelines",
                    "List pipelines for a product",
                    "PipelineList",
                    path_id="product_id",
                ),
                "post": _op(
                    "Pipelines",
                    "Create a pipeline",
                    "Pipeline",
                    path_id="product_id",
                    body="PipelineInput",
                    status=201,
                ),
            },
            "/products/{product_id}/pipelines/{pipeline_id}": {
                "get": _op(
                    "Pipelines",
                    "Get a pipeline with stages and tasks",
                    "Pipeline",
                    path_ids=["product_id", "pipeline_id"],
                ),
                "put": _op(
                    "Pipelines",
                    "Update a pipeline",
                    "Pipeline",
                    path_ids=["product_id", "pipeline_id"],
                    body="PipelineInput",
                ),
                "delete": _del("Pipelines", path_ids=["product_id", "pipeline_id"]),
            },
            "/products/{product_id}/pipelines/{pipeline_id}/compliance": {
                "post": _op(
                    "Pipelines",
                    "Recalculate compliance score",
                    "ComplianceResult",
                    path_ids=["product_id", "pipeline_id"],
                    body="ComplianceInput",
                ),
            },
            "/products/{product_id}/pipelines/{pipeline_id}/stages": {
                "get": _op(
                    "Pipelines",
                    "List stages for a pipeline",
                    "StageList",
                    path_ids=["product_id", "pipeline_id"],
                ),
                "post": _op(
                    "Pipelines",
                    "Create a stage",
                    "Stage",
                    path_ids=["product_id", "pipeline_id"],
                    body="StageInput",
                    status=201,
                ),
            },
            "/products/{product_id}/pipelines/{pipeline_id}/stages/{stage_id}": {
                "get": _op(
                    "Pipelines",
                    "Get a stage",
                    "Stage",
                    path_ids=["product_id", "pipeline_id", "stage_id"],
                ),
                "put": _op(
                    "Pipelines",
                    "Update a stage",
                    "Stage",
                    path_ids=["product_id", "pipeline_id", "stage_id"],
                    body="StageInput",
                ),
                "delete": _del("Pipelines", path_ids=["product_id", "pipeline_id", "stage_id"]),
            },
            # ── Tasks ─────────────────────────────────────────────────────
            "/products/{product_id}/pipelines/{pipeline_id}/stages/{stage_id}/tasks": {
                "get": _op(
                    "Tasks",
                    "List tasks for a stage",
                    "TaskList",
                    path_ids=["product_id", "pipeline_id", "stage_id"],
                ),
                "post": _op(
                    "Tasks",
                    "Create a task",
                    "Task",
                    path_ids=["product_id", "pipeline_id", "stage_id"],
                    body="TaskInput",
                    status=201,
                ),
            },
            "/products/{product_id}/pipelines/{pipeline_id}/stages/{stage_id}/tasks/{task_id}": {
                "get": _op(
                    "Tasks",
                    "Get a task",
                    "Task",
                    path_ids=["product_id", "pipeline_id", "stage_id", "task_id"],
                ),
                "put": _op(
                    "Tasks",
                    "Update a task",
                    "Task",
                    path_ids=["product_id", "pipeline_id", "stage_id", "task_id"],
                    body="TaskInput",
                ),
                "delete": _del(
                    "Tasks", path_ids=["product_id", "pipeline_id", "stage_id", "task_id"]
                ),
            },
            "/products/{product_id}/pipelines/{pipeline_id}/stages/{stage_id}/tasks/{task_id}/run": {
                "post": _op(
                    "Tasks",
                    "Execute task script in sandbox (async)",
                    "TaskRun",
                    path_ids=["product_id", "pipeline_id", "stage_id", "task_id"],
                    status=202,
                ),
            },
            "/products/{product_id}/pipelines/{pipeline_id}/stages/{stage_id}/tasks/{task_id}/runs": {
                "get": _op(
                    "Tasks",
                    "List all runs for a task",
                    "TaskRunList",
                    path_ids=["product_id", "pipeline_id", "stage_id", "task_id"],
                ),
            },
            "/task-runs/{run_id}": {
                "get": _op(
                    "Tasks", "Poll a task run for status and logs", "TaskRun", path_id="run_id"
                ),
            },
            # ── Agent Pools ───────────────────────────────────────────────
            "/agent-pools": {
                "get": _op("Agent Pools", "List agent pools (seeds built-ins)", "AgentPoolList"),
                "post": _op(
                    "Agent Pools",
                    "Create a custom agent pool",
                    "AgentPool",
                    body="AgentPoolInput",
                    status=201,
                ),
            },
            "/agent-pools/{pool_id}": {
                "delete": _del("Agent Pools", path_id="pool_id"),
            },
            # ── Releases ──────────────────────────────────────────────────
            "/products/{product_id}/releases": {
                "get": _op(
                    "Releases", "List releases for a product", "ReleaseList", path_id="product_id"
                ),
                "post": _op(
                    "Releases",
                    "Create a release",
                    "Release",
                    path_id="product_id",
                    body="ReleaseInput",
                    status=201,
                ),
            },
            "/products/{product_id}/releases/{release_id}": {
                "get": _op(
                    "Releases",
                    "Get a release with attached pipelines",
                    "Release",
                    path_ids=["product_id", "release_id"],
                ),
                "put": _op(
                    "Releases",
                    "Update a release",
                    "Release",
                    path_ids=["product_id", "release_id"],
                    body="ReleaseInput",
                ),
                "delete": _del("Releases", path_ids=["product_id", "release_id"]),
            },
            "/products/{product_id}/releases/{release_id}/pipelines": {
                "post": _op(
                    "Releases",
                    "Attach pipeline to release (runs admission check)",
                    "AttachResult",
                    path_ids=["product_id", "release_id"],
                    body="AttachPipelineInput",
                ),
            },
            "/products/{product_id}/releases/{release_id}/pipelines/{pipeline_id}": {
                "delete": _del(
                    "Releases",
                    path_ids=["product_id", "release_id", "pipeline_id"],
                    summary="Detach pipeline from release",
                ),
            },
            "/products/{product_id}/releases/{release_id}/audit": {
                "get": _op(
                    "Releases",
                    "Get audit report for a release",
                    "AuditReport",
                    path_ids=["product_id", "release_id"],
                ),
            },
            "/products/{product_id}/releases/{release_id}/application-groups": {
                "get": _op(
                    "Releases",
                    "List application groups for a release",
                    "AppGroupList",
                    path_ids=["product_id", "release_id"],
                ),
                "post": _op(
                    "Releases",
                    "Add an application group to a release",
                    "AppGroup",
                    path_ids=["product_id", "release_id"],
                    body="AppGroupInput",
                    status=201,
                ),
            },
            "/products/{product_id}/releases/{release_id}/application-groups/{group_id}": {
                "delete": _del(
                    "Releases",
                    path_ids=["product_id", "release_id", "group_id"],
                    summary="Remove application group from release",
                ),
            },
            "/products/{product_id}/releases/{release_id}/export": {
                "get": _op(
                    "YAML",
                    "Export release as YAML",
                    "YamlText",
                    path_ids=["product_id", "release_id"],
                ),
            },
            # ── Runs ──────────────────────────────────────────────────────
            "/pipelines/{pipeline_id}/runs": {
                "get": _op(
                    "Runs", "List runs for a pipeline", "PipelineRunList", path_id="pipeline_id"
                ),
                "post": _op(
                    "Runs",
                    "Start a pipeline run",
                    "PipelineRun",
                    path_id="pipeline_id",
                    body="PipelineRunInput",
                    status=201,
                ),
            },
            "/pipeline-runs/{run_id}": {
                "get": _op(
                    "Runs",
                    "Get a pipeline run (includes stage and task runs)",
                    "PipelineRun",
                    path_id="run_id",
                ),
                "patch": _op(
                    "Runs",
                    "Update a pipeline run status",
                    "PipelineRun",
                    path_id="run_id",
                    body="StatusInput",
                ),
            },
            "/pipeline-runs/{run_id}/rerun": {
                "post": _op(
                    "Runs",
                    "Clone and re-run a pipeline run from the beginning",
                    "PipelineRun",
                    path_id="run_id",
                    status=202,
                ),
            },
            "/pipeline-runs/{run_id}/stages/{stage_run_id}/rerun": {
                "post": _op(
                    "Runs",
                    "Restart a pipeline run from a specific stage onwards",
                    "PipelineRun",
                    path_ids=["run_id", "stage_run_id"],
                    status=202,
                ),
            },
            "/releases/{release_id}/runs": {
                "get": _op(
                    "Runs", "List runs for a release", "ReleaseRunList", path_id="release_id"
                ),
                "post": _op(
                    "Runs",
                    "Start a release run",
                    "ReleaseRun",
                    path_id="release_id",
                    body="ReleaseRunInput",
                    status=201,
                ),
            },
            "/release-runs/{run_id}": {
                "get": _op("Runs", "Get a release run", "ReleaseRun", path_id="run_id"),
                "patch": _op(
                    "Runs",
                    "Update a release run status",
                    "ReleaseRun",
                    path_id="run_id",
                    body="StatusInput",
                ),
            },
            # ── Compliance ────────────────────────────────────────────────
            "/compliance/rules": {
                "get": _op("Compliance", "List compliance rules", "ComplianceRuleList"),
                "post": _op(
                    "Compliance",
                    "Create a compliance rule",
                    "ComplianceRule",
                    body="ComplianceRuleInput",
                    status=201,
                ),
            },
            "/compliance/rules/{rule_id}": {
                "delete": _del("Compliance", path_id="rule_id"),
            },
            "/compliance/audit-events": {
                "get": _op("Compliance", "List recent audit events", "AuditEventList"),
            },
            # ── Users ─────────────────────────────────────────────────────
            "/users": {
                "get": _op("Users", "List users", "UserList"),
                "post": _op("Users", "Create a user", "User", body="UserInput", status=201),
            },
            "/users/{user_id}": {
                "get": _op("Users", "Get a user", "User", path_id="user_id"),
                "patch": _op(
                    "Users",
                    "Update user persona or fields",
                    "User",
                    path_id="user_id",
                    body="UserPatchInput",
                ),
                "delete": _del("Users", path_id="user_id"),
            },
            "/users/import": {
                "post": {
                    "tags": ["Users"],
                    "summary": "Bulk-import users from JSON array or CSV",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/UserInput"},
                                }
                            },
                            "text/csv": {
                                "schema": {
                                    "type": "string",
                                    "description": "CSV with header: username,email,display_name,persona,password",
                                }
                            },
                        },
                    },
                    "responses": {
                        "200": {"description": "Import summary with created/skipped/errors counts"},
                        "400": {"description": "Bad request"},
                        "401": {"description": "Unauthenticated"},
                    },
                },
            },
            "/users/{user_id}/bindings": {
                "get": _op(
                    "Users", "List role bindings for a user", "RoleBindingList", path_id="user_id"
                ),
                "post": _op(
                    "Users",
                    "Add a role binding to a user",
                    "RoleBinding",
                    path_id="user_id",
                    body="RoleBindingInput",
                    status=201,
                ),
            },
            "/users/{user_id}/bindings/{binding_id}": {
                "delete": _del(
                    "Users", path_ids=["user_id", "binding_id"], summary="Remove role binding"
                ),
            },
            "/groups": {
                "get": _op("Users", "List groups", "GroupList"),
                "post": _op("Users", "Create a group", "Group", body="GroupInput", status=201),
            },
            "/groups/{group_id}": {
                "get": _op("Users", "Get a group with members", "Group", path_id="group_id"),
                "patch": _op(
                    "Users", "Update a group", "Group", path_id="group_id", body="GroupInput"
                ),
                "delete": _del("Users", path_id="group_id"),
            },
            "/groups/{group_id}/members/{user_id}": {
                "post": _op(
                    "Users", "Add member to group", "Group", path_ids=["group_id", "user_id"]
                ),
                "delete": _del(
                    "Users", path_ids=["group_id", "user_id"], summary="Remove member from group"
                ),
            },
            "/roles": {
                "get": _op("Users", "List roles", "RoleList"),
                "post": _op("Users", "Create a role", "Role", body="RoleInput", status=201),
            },
            "/roles/{role_id}": {
                "get": _op("Users", "Get a role", "Role", path_id="role_id"),
                "patch": _op("Users", "Update a role", "Role", path_id="role_id", body="RoleInput"),
                "delete": _del("Users", path_id="role_id"),
            },
            # ── Git Sync ──────────────────────────────────────────────────
            "/products/{product_id}/pipelines/{pipeline_id}/git/pull": {
                "post": _op(
                    "YAML",
                    "Pull pipeline definition from remote Git repository",
                    "ImportResult",
                    path_ids=["product_id", "pipeline_id"],
                ),
            },
            "/products/{product_id}/pipelines/{pipeline_id}/git/push": {
                "post": _op(
                    "YAML",
                    "Push pipeline definition to remote Git repository",
                    "ImportResult",
                    path_ids=["product_id", "pipeline_id"],
                    body="GitPushInput",
                ),
            },
            # ── Plugins ───────────────────────────────────────────────────
            "/plugins": {
                "get": _op("Plugins", "List all plugins (built-in + custom)", "PluginList"),
                "post": _op(
                    "Plugins", "Register a custom plugin", "Plugin", body="PluginInput", status=201
                ),
            },
            "/plugins/{plugin_id}": {
                "get": _op("Plugins", "Get plugin details", "Plugin", path_id="plugin_id"),
                "delete": _del("Plugins", path_id="plugin_id"),
            },
            "/plugins/{plugin_id}/toggle": {
                "patch": _op(
                    "Plugins", "Enable or disable a plugin", "Plugin", path_id="plugin_id"
                ),
            },
            "/plugins/{plugin_id}/configs": {
                "get": _op(
                    "Plugins", "List configs for a plugin", "PluginConfigList", path_id="plugin_id"
                ),
                "post": _op(
                    "Plugins",
                    "Create a plugin config",
                    "PluginConfig",
                    path_id="plugin_id",
                    body="PluginConfigInput",
                    status=201,
                ),
            },
            "/plugins/{plugin_id}/configs/{config_id}": {
                "put": _op(
                    "Plugins",
                    "Update a plugin config",
                    "PluginConfig",
                    path_ids=["plugin_id", "config_id"],
                    body="PluginConfigInput",
                ),
                "delete": _del("Plugins", path_ids=["plugin_id", "config_id"]),
            },
            "/plugins/{plugin_id}/configs/{config_id}/test": {
                "post": _op(
                    "Plugins",
                    "Test connectivity for a plugin configuration",
                    "PluginTestResult",
                    path_ids=["plugin_id", "config_id"],
                ),
            },
            # ── Platform Settings ─────────────────────────────────────────
            "/settings": {
                "get": _op("Settings", "List all platform settings", "SettingList"),
            },
            "/settings/{key}": {
                "put": _op(
                    "Settings",
                    "Set a platform setting value",
                    "Setting",
                    path_id="key",
                    body="SettingInput",
                ),
                "delete": _del("Settings", path_id="key", summary="Clear a platform setting"),
            },
            # ── AI Chat ───────────────────────────────────────────────────
            "/chat": {
                "post": {
                    "tags": ["AI Chat"],
                    "summary": "Send a message to the AI assistant (Llama 3.3 70B via Groq)",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["messages"],
                                    "properties": {
                                        "messages": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "role": {
                                                        "type": "string",
                                                        "enum": ["user", "assistant"],
                                                    },
                                                    "content": {"type": "string"},
                                                },
                                            },
                                        }
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "AI response message"},
                        "503": {"description": "AI service unavailable"},
                    },
                },
            },
            # ── LDAP ──────────────────────────────────────────────────────
            "/auth/ldap/config": {
                "get": _op("Auth", "Get LDAP configuration", "LdapConfig"),
            },
            "/auth/ldap/test": {
                "post": _op("Auth", "Test LDAP connection", "LdapTestResult", body="LdapTestInput"),
            },
            # ── ISO 27001 ─────────────────────────────────────────────────
            "/compliance/iso27001": {
                "get": _op("Compliance", "Get ISO 27001 compliance report", "ISO27001Report"),
            },
            # ── YAML ──────────────────────────────────────────────────────
            "/products/{product_id}/export": {
                "get": _op("YAML", "Export product as YAML", "YamlText", path_id="product_id"),
            },
            "/environments/export": {
                "get": _op("YAML", "Export all environments as YAML", "YamlText"),
            },
            "/environments/import": {
                "post": _op(
                    "YAML",
                    "Import environments from YAML",
                    "ImportResult",
                    body="YamlBody",
                    status=201,
                ),
            },
            "/products/{product_id}/pipelines/{pipeline_id}/export": {
                "get": _op(
                    "YAML",
                    "Export pipeline as YAML",
                    "YamlText",
                    path_ids=["product_id", "pipeline_id"],
                ),
            },
            "/products/{product_id}/pipelines/{pipeline_id}/import": {
                "post": _op(
                    "YAML",
                    "Import pipeline definition from YAML",
                    "ImportResult",
                    path_ids=["product_id", "pipeline_id"],
                    body="YamlBody",
                ),
            },
            "/agent-pools/export": {
                "get": _op("YAML", "Export custom agent pools as YAML", "YamlText"),
            },
            "/agent-pools/import": {
                "post": _op(
                    "YAML",
                    "Import agent pools from YAML",
                    "ImportResult",
                    body="YamlBody",
                    status=201,
                ),
            },
        },
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "JWT from POST /api/v1/auth/login. Pre-populated from your app session automatically.",
                },
            },
            "schemas": {
                # ── Inputs ────────────────────────────────────────────────
                "ProductInput": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
                },
                "EnvironmentInput": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "env_type": {
                            "type": "string",
                            "enum": ["dev", "qa", "staging", "prod", "custom"],
                        },
                        "order": {"type": "integer"},
                        "description": {"type": "string"},
                    },
                },
                "AttachEnvironmentInput": {
                    "type": "object",
                    "required": ["environment_id"],
                    "properties": {"environment_id": {"type": "string"}},
                },
                "AttachPipelineInput": {
                    "type": "object",
                    "required": ["pipeline_id"],
                    "properties": {
                        "pipeline_id": {"type": "string"},
                        "requested_by": {"type": "string"},
                    },
                },
                "PipelineInput": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "kind": {"type": "string", "enum": ["ci", "cd"]},
                        "git_repo": {"type": "string"},
                        "git_branch": {"type": "string"},
                    },
                },
                "StageInput": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "order": {"type": "integer"},
                        "run_language": {"type": "string", "enum": ["bash", "python"]},
                        "container_image": {"type": "string"},
                        "is_protected": {"type": "boolean"},
                    },
                },
                "TaskInput": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "run_language": {"type": "string", "enum": ["bash", "python"]},
                        "run_code": {"type": "string"},
                        "execution_mode": {"type": "string", "enum": ["sequential", "parallel"]},
                        "on_error": {"type": "string", "enum": ["fail", "warn", "continue"]},
                        "timeout": {"type": "integer"},
                        "order": {"type": "integer"},
                        "is_required": {"type": "boolean"},
                    },
                },
                "ReleaseInput": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "version": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
                "ComplianceInput": {
                    "type": "object",
                    "properties": {
                        "mandatory_pct": {"type": "number"},
                        "best_practice_pct": {"type": "number"},
                        "runtime_pct": {"type": "number"},
                        "metadata_pct": {"type": "number"},
                    },
                },
                "ComplianceRuleInput": {
                    "type": "object",
                    "properties": {
                        "scope": {"type": "string"},
                        "min_rating": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
                "AgentPoolInput": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "cpu_limit": {"type": "string"},
                        "memory_limit": {"type": "string"},
                        "max_agents": {"type": "integer"},
                    },
                },
                "UserInput": {
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "email": {"type": "string"},
                        "display_name": {"type": "string"},
                        "persona": {"type": "string"},
                        "ldap_dn": {"type": "string"},
                    },
                },
                "UserPatchInput": {
                    "type": "object",
                    "properties": {"persona": {"type": "string"}, "is_active": {"type": "boolean"}},
                },
                "GroupInput": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
                },
                "RoleInput": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "permissions": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "RoleBindingInput": {
                    "type": "object",
                    "properties": {
                        "role_id": {"type": "string"},
                        "scope": {"type": "string"},
                        "expires_at": {"type": "string", "format": "date-time"},
                    },
                },
                "PipelineRunInput": {
                    "type": "object",
                    "properties": {
                        "commit_sha": {"type": "string"},
                        "artifact_id": {"type": "string"},
                        "triggered_by": {"type": "string"},
                    },
                },
                "ReleaseRunInput": {
                    "type": "object",
                    "properties": {"triggered_by": {"type": "string"}},
                },
                "StatusInput": {"type": "object", "properties": {"status": {"type": "string"}}},
                "SecretInput": {
                    "type": "object",
                    "required": ["name", "value"],
                    "properties": {
                        "name": {"type": "string"},
                        "value": {"type": "string"},
                        "description": {"type": "string"},
                        "allowed_users": {"type": "string"},
                    },
                },
                "WebhookInput": {
                    "type": "object",
                    "required": ["name", "pipeline_id"],
                    "properties": {
                        "name": {"type": "string"},
                        "pipeline_id": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
                "YamlBody": {"type": "string"},
                # ── Response objects (generic) ─────────────────────────────
                "AttachResult": {"type": "object"},
                "ComplianceResult": {"type": "object"},
                "ImportResult": {"type": "object"},
                "YamlText": {"type": "string"},
                "Product": {"type": "object"},
                "ProductList": {"type": "array", "items": {"$ref": "#/components/schemas/Product"}},
                "Environment": {"type": "object"},
                "EnvironmentList": {"type": "array"},
                "Pipeline": {"type": "object"},
                "PipelineList": {"type": "array"},
                "Stage": {"type": "object"},
                "StageList": {"type": "array"},
                "Task": {"type": "object"},
                "TaskList": {"type": "array"},
                "TaskRun": {"type": "object"},
                "TaskRunList": {"type": "array"},
                "AgentPool": {"type": "object"},
                "AgentPoolList": {"type": "array"},
                "Release": {"type": "object"},
                "ReleaseList": {"type": "array"},
                "PipelineRun": {"type": "object"},
                "PipelineRunList": {"type": "array"},
                "ReleaseRun": {"type": "object"},
                "ReleaseRunList": {"type": "array"},
                "ComplianceRule": {"type": "object"},
                "ComplianceRuleList": {"type": "array"},
                "AuditEvent": {"type": "object"},
                "AuditEventList": {"type": "array"},
                "AuditReport": {"type": "object"},
                "User": {"type": "object"},
                "UserList": {"type": "array"},
                "Group": {"type": "object"},
                "GroupList": {"type": "array"},
                "Role": {"type": "object"},
                "RoleList": {"type": "array"},
                "RoleBinding": {"type": "object"},
                "RoleBindingList": {"type": "array"},
                "Secret": {"type": "object"},
                "SecretList": {"type": "array"},
                "SecretValue": {"type": "object"},
                "Webhook": {"type": "object"},
                "WebhookList": {"type": "array"},
                "WebhookDeliveryList": {"type": "array"},
                "AppGroup": {"type": "object"},
                "AppGroupList": {"type": "array"},
                "AppGroupInput": {
                    "type": "object",
                    "required": ["application_id"],
                    "properties": {
                        "application_id": {"type": "string"},
                        "execution_mode": {"type": "string", "enum": ["sequential", "parallel"]},
                        "pipeline_ids": {"type": "array", "items": {"type": "string"}},
                        "order": {"type": "integer"},
                    },
                },
                "Plugin": {"type": "object"},
                "PluginList": {"type": "array"},
                "PluginInput": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string"},
                        "display_name": {"type": "string"},
                        "description": {"type": "string"},
                        "category": {"type": "string"},
                        "version": {"type": "string"},
                        "icon": {"type": "string"},
                        "config_schema": {"type": "object"},
                    },
                },
                "PluginConfig": {"type": "object"},
                "PluginConfigList": {"type": "array"},
                "PluginConfigInput": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string"},
                        "config_data": {"type": "object"},
                        "is_default": {"type": "boolean"},
                    },
                },
                "Setting": {"type": "object"},
                "SettingList": {"type": "array"},
                "SettingInput": {
                    "type": "object",
                    "required": ["value"],
                    "properties": {"value": {"type": "string"}},
                },
                "PluginTestResult": {
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "message": {"type": "string"},
                    },
                },
                "LdapConfig": {"type": "object"},
                "LdapTestInput": {
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "password": {"type": "string"},
                    },
                },
                "LdapTestResult": {"type": "object"},
                "ISO27001Report": {"type": "object"},
                "GitPushInput": {
                    "type": "object",
                    "properties": {
                        "commit_message": {"type": "string"},
                        "branch": {"type": "string"},
                    },
                },
            },
        },
    }
    return jsonify(spec)


# ── Helper builders ───────────────────────────────────────────────────────────


def _path_params(path_ids: list[str]) -> list:
    return [
        {"name": pid, "in": "path", "required": True, "schema": {"type": "string"}}
        for pid in path_ids
    ]


def _op(
    tag: str,
    summary: str,
    response_schema: str,
    *,
    path_id: str | None = None,
    path_ids: list[str] | None = None,
    body: str | None = None,
    status: int = 200,
) -> dict:
    ids = path_ids or ([path_id] if path_id else [])
    op: dict = {
        "tags": [tag],
        "summary": summary,
        "parameters": _path_params(ids),
        "responses": {
            str(status): {
                "description": "Success",
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{response_schema}"}
                    }
                },
            },
            "400": {"description": "Bad request"},
            "401": {"description": "Unauthenticated"},
            "404": {"description": "Not found"},
        },
    }
    if body:
        op["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{body}"}}},
        }
    return op


def _del(
    tag: str,
    *,
    path_id: str | None = None,
    path_ids: list[str] | None = None,
    summary: str = "Delete resource",
) -> dict:
    ids = path_ids or ([path_id] if path_id else [])
    return {
        "tags": [tag],
        "summary": summary,
        "parameters": _path_params(ids),
        "responses": {
            "204": {"description": "Deleted"},
            "401": {"description": "Unauthenticated"},
            "404": {"description": "Not found"},
        },
    }
