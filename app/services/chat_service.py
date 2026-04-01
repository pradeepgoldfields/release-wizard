"""AI chat agent service — uses Groq (Llama 3.3 70B) to answer questions and
perform actions via the Conduit platform data and API.

The agent has two categories of tools:
  READ  — query live data (products, pipelines, runs, compliance, etc.)
  WRITE — perform actions (trigger pipeline runs, create releases, etc.)

Write tools are only executed when a current_user is provided and the action
is explicitly requested by the user.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from flask import current_app

log = logging.getLogger(__name__)

# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS: list[dict[str, Any]] = [
    # ── READ tools ──────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "list_products",
            "description": "List all products in the platform.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": "Get details of a specific product including its pipelines and releases.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_pipelines",
            "description": "List all pipelines for a product.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pipeline",
            "description": "Get full details of a pipeline including its stages and tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "pipeline_id": {"type": "string"},
                },
                "required": ["product_id", "pipeline_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_pipeline_runs",
            "description": "List recent pipeline runs for a pipeline (newest first, up to 10).",
            "parameters": {
                "type": "object",
                "properties": {"pipeline_id": {"type": "string"}},
                "required": ["pipeline_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pipeline_run",
            "description": "Get a specific pipeline run including its stage and task run details.",
            "parameters": {
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pipeline_run_context",
            "description": "Get the full execution context for a pipeline run — all CDT_ variables, resolved properties and output JSON for every task.",
            "parameters": {
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_releases",
            "description": "List all releases for a product.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_release",
            "description": "Get details of a specific release including its application groups.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "release_id": {"type": "string"},
                },
                "required": ["product_id", "release_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_environments",
            "description": "List all deployment environments.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_users",
            "description": "List all platform users and their roles.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_compliance_rules",
            "description": "List all active compliance admission rules.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_iso27001_report",
            "description": "Get the ISO 27001:2022 compliance evaluation for the platform.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_audit_report",
            "description": "Get the compliance audit report for a release.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "release_id": {"type": "string"},
                },
                "required": ["product_id", "release_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_audit_events",
            "description": "List recent audit events, optionally filtered by resource type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_type": {
                        "type": "string",
                        "description": "e.g. release, pipeline, product",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max events to return (default 20)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_applications",
            "description": "List all applications/services registered for a product.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_pipeline_properties",
            "description": "List design-time properties defined on a pipeline (and optionally its stages/tasks).",
            "parameters": {
                "type": "object",
                "properties": {"pipeline_id": {"type": "string"}},
                "required": ["pipeline_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_webhooks",
            "description": "List all configured webhooks.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_agent_pools",
            "description": "List all agent pools (execution environments).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_vault_secrets",
            "description": "List vault secrets (names and metadata only — values are never exposed).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_plugins",
            "description": "List all installed plugins and their status.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_maturity_overview",
            "description": "Get the pipeline maturity overview — scores across all products/pipelines.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    # ── WRITE / ACTION tools ─────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "trigger_pipeline_run",
            "description": "Trigger a new pipeline run. Use this when the user explicitly asks to run, execute, or trigger a pipeline.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pipeline_id": {"type": "string", "description": "The pipeline ID to run"},
                    "commit_sha": {"type": "string", "description": "Optional commit SHA"},
                    "artifact_id": {"type": "string", "description": "Optional artifact ID"},
                },
                "required": ["pipeline_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_release_run",
            "description": "Trigger a new release run. Use when the user asks to deploy or run a release.",
            "parameters": {
                "type": "object",
                "properties": {
                    "release_id": {"type": "string", "description": "The release ID to run"},
                },
                "required": ["release_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rerun_pipeline",
            "description": "Re-run a pipeline from the beginning, cloning the original run's commit/artifact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "The pipeline run ID to re-run"},
                },
                "required": ["run_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_product",
            "description": "Create a new product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_release",
            "description": "Create a new release for a product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "name": {"type": "string", "description": "Release name/version e.g. v1.2.3"},
                    "description": {"type": "string"},
                    "environment_id": {
                        "type": "string",
                        "description": "Optional target environment ID",
                    },
                },
                "required": ["product_id", "name"],
            },
        },
    },
]

# ── Tool executor ──────────────────────────────────────────────────────────────


def _execute_tool(name: str, inputs: dict, current_user: Any = None) -> Any:
    """Execute a tool by calling the service/model layer directly."""
    from app.extensions import db
    from app.models.application import ApplicationArtifact
    from app.models.auth import User
    from app.models.compliance import AuditEvent, ComplianceRule
    from app.models.environment import Environment
    from app.models.pipeline import Pipeline
    from app.models.plugin import Plugin
    from app.models.product import Product
    from app.models.property import Property
    from app.models.release import Release
    from app.models.run import PipelineRun
    from app.models.task import AgentPool
    from app.models.vault import VaultSecret
    from app.models.webhook import Webhook
    from app.services.audit_service import build_release_audit_report
    from app.services.iso27001_service import evaluate_iso27001
    from app.services.maturity_service import get_overview as get_maturity_overview

    triggered_by = current_user.username if current_user else "ai-assistant"

    try:
        # ── READ tools ────────────────────────────────────────────────────
        if name == "list_products":
            return [p.to_dict() for p in Product.query.order_by(Product.name).all()]

        elif name == "get_product":
            p = db.get_or_404(Product, inputs["product_id"])
            return p.to_dict()

        elif name == "list_pipelines":
            pipelines = Pipeline.query.filter_by(product_id=inputs["product_id"]).all()
            return [p.to_dict() for p in pipelines]

        elif name == "get_pipeline":
            pl = db.get_or_404(Pipeline, inputs["pipeline_id"])
            d = pl.to_dict(include_stages=True)
            # enrich with stage/task details
            return d

        elif name == "list_pipeline_runs":
            runs = (
                PipelineRun.query.filter_by(pipeline_id=inputs["pipeline_id"])
                .order_by(PipelineRun.started_at.desc())
                .limit(10)
                .all()
            )
            return [r.to_dict() for r in runs]

        elif name == "get_pipeline_run":
            run = db.get_or_404(PipelineRun, inputs["run_id"])
            return run.to_dict(include_stages=True)

        elif name == "get_pipeline_run_context":
            run = db.get_or_404(PipelineRun, inputs["run_id"])
            pipeline = run.pipeline
            stages_out = []
            for sr in sorted(run.stage_runs, key=lambda s: s.stage.order if s.stage else 0):
                tasks_out = []
                for tr in sorted(sr.task_runs, key=lambda t: t.task.order if t.task else 0):
                    ctx_env = {}
                    if tr.context_env:
                        try:
                            ctx_env = json.loads(tr.context_env)
                        except (ValueError, TypeError):
                            pass
                    out_json = None
                    if tr.output_json:
                        try:
                            out_json = json.loads(tr.output_json)
                        except (ValueError, TypeError):
                            out_json = tr.output_json
                    tasks_out.append(
                        {
                            "task_name": tr.task.name if tr.task else tr.task_id,
                            "status": tr.status,
                            "cdt_variables": {
                                k: v for k, v in ctx_env.items() if k.startswith("CDT_")
                            },
                            "resolved_properties": json.loads(ctx_env.get("CDT_PROPS", "{}")),
                            "output_json": out_json,
                        }
                    )
                stages_out.append(
                    {
                        "stage_name": sr.stage.name if sr.stage else sr.stage_id,
                        "status": sr.status,
                        "tasks": tasks_out,
                    }
                )
            return {
                "run_id": run.id,
                "status": run.status,
                "pipeline_name": pipeline.name if pipeline else None,
                "triggered_by": run.triggered_by,
                "commit_sha": run.commit_sha,
                "stages": stages_out,
            }

        elif name == "list_releases":
            releases = (
                Release.query.filter_by(product_id=inputs["product_id"])
                .order_by(Release.created_at.desc())
                .all()
            )
            return [r.to_dict() for r in releases]

        elif name == "get_release":
            r = Release.query.filter_by(
                id=inputs["release_id"], product_id=inputs["product_id"]
            ).first_or_404()
            return r.to_dict(include_pipelines=True)

        elif name == "list_environments":
            return [e.to_dict() for e in Environment.query.order_by(Environment.order).all()]

        elif name == "list_users":
            return [u.to_dict() for u in User.query.all()]

        elif name == "list_compliance_rules":
            return [r.to_dict() for r in ComplianceRule.query.filter_by(is_active=True).all()]

        elif name == "get_iso27001_report":
            return evaluate_iso27001()

        elif name == "get_audit_report":
            return build_release_audit_report(inputs["release_id"])

        elif name == "list_audit_events":
            q = AuditEvent.query
            if inputs.get("resource_type"):
                q = q.filter_by(resource_type=inputs["resource_type"])
            events = q.order_by(AuditEvent.timestamp.desc()).limit(inputs.get("limit", 20)).all()
            return [e.to_dict() for e in events]

        elif name == "list_applications":
            apps = ApplicationArtifact.query.filter_by(product_id=inputs["product_id"]).all()
            return [a.to_dict() for a in apps]

        elif name == "list_pipeline_properties":
            pipeline_id = inputs["pipeline_id"]
            props = Property.query.filter_by(owner_type="pipeline", owner_id=pipeline_id).all()
            result = {"pipeline": [p.to_dict() for p in props], "stages": {}, "tasks": {}}
            pl = db.session.get(Pipeline, pipeline_id)
            if pl:
                for stage in pl.stages or []:
                    sp = Property.query.filter_by(owner_type="stage", owner_id=stage.id).all()
                    result["stages"][stage.name] = [p.to_dict() for p in sp]
                    for task in stage.tasks or []:
                        tp = Property.query.filter_by(owner_type="task", owner_id=task.id).all()
                        if tp:
                            result["tasks"][task.name] = [p.to_dict() for p in tp]
            return result

        elif name == "list_webhooks":
            return [w.to_dict() for w in Webhook.query.all()]

        elif name == "list_agent_pools":
            return [p.to_dict() for p in AgentPool.query.all()]

        elif name == "list_vault_secrets":
            return [s.to_dict() for s in VaultSecret.query.all()]

        elif name == "list_plugins":
            return [p.to_dict(include_configs=True) for p in Plugin.query.all()]

        elif name == "get_maturity_overview":
            return get_maturity_overview()

        # ── WRITE / ACTION tools ──────────────────────────────────────────
        elif name == "trigger_pipeline_run":
            from app.services.run_service import start_pipeline_run

            run = start_pipeline_run(
                pipeline_id=inputs["pipeline_id"],
                commit_sha=inputs.get("commit_sha"),
                artifact_id=inputs.get("artifact_id"),
                triggered_by=triggered_by,
                app=current_app._get_current_object(),
            )
            return {
                "run_id": run.id,
                "status": run.status,
                "message": f"Pipeline run started: {run.id}",
            }

        elif name == "trigger_release_run":
            from app.services.run_service import start_release_run

            run = start_release_run(
                release_id=inputs["release_id"],
                triggered_by=triggered_by,
                app=current_app._get_current_object(),
            )
            return {
                "run_id": run.id,
                "status": run.status,
                "message": f"Release run started: {run.id}",
            }

        elif name == "rerun_pipeline":
            from app.services.run_service import start_pipeline_run

            original = db.get_or_404(PipelineRun, inputs["run_id"])
            run = start_pipeline_run(
                pipeline_id=original.pipeline_id,
                commit_sha=original.commit_sha,
                artifact_id=original.artifact_id,
                triggered_by=triggered_by,
                app=current_app._get_current_object(),
            )
            return {
                "run_id": run.id,
                "status": run.status,
                "message": f"Pipeline re-run started: {run.id}",
            }

        elif name == "create_product":
            import re

            from app.models.product import Product as _Product
            from app.services.id_service import resource_id

            slug = re.sub(r"[^a-z0-9-]", "-", inputs["name"].lower()).strip("-")
            p = _Product(
                id=resource_id("prod"),
                name=inputs["name"],
                slug=slug,
                description=inputs.get("description", ""),
            )
            db.session.add(p)
            db.session.commit()
            return {"product_id": p.id, "name": p.name, "message": f"Product '{p.name}' created"}

        elif name == "create_release":
            from app.models.release import Release as _Release
            from app.services.id_service import resource_id

            r = _Release(
                id=resource_id("rel"),
                product_id=inputs["product_id"],
                name=inputs["name"],
                description=inputs.get("description", ""),
                environment_id=inputs.get("environment_id"),
                created_by=triggered_by,
            )
            db.session.add(r)
            db.session.commit()
            return {"release_id": r.id, "name": r.name, "message": f"Release '{r.name}' created"}

        else:
            return {"error": f"Unknown tool: {name}"}

    except Exception as exc:
        log.warning("Tool %s failed: %s", name, exc)
        return {"error": str(exc)}


# ── System prompt with full platform knowledge ────────────────────────────────


def _build_system_prompt(current_user: Any) -> str:
    user_info = ""
    if current_user:
        role_names = ", ".join(
            rb.role.name for rb in (current_user.role_bindings or []) if rb.role
        ) or getattr(current_user, "persona", "unknown")
        user_info = f"\n\nThe user you are assisting is **{current_user.username}** (persona/roles: {role_names})."

    return f"""You are the **Conduit AI assistant** — an expert on this CI/CD orchestration platform and all the data it contains.

## Platform Overview
Conduit is a release engineering platform that orchestrates CI/CD pipelines across products and environments.
Core concepts:
- **Product**: top-level namespace (e.g. "Acme Platform"). Contains applications, pipelines, releases.
- **Application**: a microservice or component belonging to a product.
- **Environment**: a deployment target (dev/qa/prod) shared across products.
- **Pipeline**: an ordered sequence of **Stages**, each containing **Tasks** (bash or python scripts).
- **Release**: a versioned collection of pipelines grouped by application, ready to deploy.
- **Pipeline Run**: a single execution of a pipeline. Has stage runs → task runs.
- **Stage Run**: execution of one stage. Succeeds when all tasks succeed.
- **Task Run**: execution of one script. Captures exit code, logs, output JSON, and CDT_ context variables.
- **Agent Pool**: the sandboxed execution environment (subprocess / docker / kubernetes job).
- **Compliance Rule**: an admission policy (score threshold, required tasks, etc.) gating pipeline → release attachment.
- **Webhook**: inbound HTTP trigger for pipeline runs. Payload exposed as `$CDT_WEBHOOK_PAYLOAD`.
- **Property**: a named configuration value attached at pipeline/stage/task level, resolved hierarchically.
- **Vault Secret**: an encrypted secret accessible to task scripts.
- **Plugin**: a CI/CD tool integration (Jira, Slack, GitHub, etc.).

## CDT_ Context Variables (injected into every task script)
| Variable | Description |
|----------|-------------|
| CDT_PIPELINE_RUN_ID | Unique run ID |
| CDT_PIPELINE_NAME | Pipeline name |
| CDT_GIT_BRANCH | Git branch |
| CDT_COMMIT_SHA | Commit SHA |
| CDT_TRIGGERED_BY | Who triggered the run |
| CDT_STAGE_NAME | Current stage name |
| CDT_TASK_NAME | Current task name |
| CDT_PROPS | Resolved properties as JSON |
| CDT_WEBHOOK_PAYLOAD | Raw webhook payload JSON |
| CDT_RUNTIME | Full runtime context JSON |

## Property Resolution (most specific wins)
Task → Stage → Pipeline → Product (runtime overrides take precedence over all)

## API Base URL
All REST endpoints are at `/api/v1/`. Authentication: Bearer JWT in the `Authorization` header.

Key endpoints:
- `GET /products` — list products
- `POST /products/:id/pipelines/:id/runs` — trigger a pipeline run (body: commit_sha, artifact_id, triggered_by, runtime_properties)
- `GET /pipeline-runs/:id/context` — full execution context with CDT vars, properties, output JSON per task
- `GET /compliance/iso27001` — ISO 27001 compliance evaluation
- `GET /maturity/overview` — pipeline maturity scores
- `POST /webhooks/:id/trigger` — trigger a pipeline via webhook (header: X-Webhook-Token)

## Task Script Contract
- Exit 0 = Succeeded, exit 1 = Warning (if on_error=warn), exit 2+ = Failed
- Print a JSON object as the **last line** of stdout → captured as output_json
- Use `$CDT_PROPS` to read resolved properties: `python3 -c "import json,os; print(json.loads(os.environ['CDT_PROPS']).get('MY_PROP'))"`

## UI Navigation (what the user sees)

### Left Sidebar
Icons and links in order: Dashboard · Products · Environments · Compliance · Maturity · App Dictionary ·
Administration (collapsible: User Management, Key Management, Global Variables, System) · Docs · Tutorial.
A search button (Ctrl+K or `/`) opens a spotlight-style overlay.

### Dashboard
Shows: recent pipeline runs table, release run summary, quick-stats cards (products, pipelines, releases, runs).

### Products page (`#products`)
Grid of product cards. Each card shows name, compliance score bar, environment tags, application count.
Click a product → product detail page with tabs: Overview / Pipelines / Releases / Applications / Environments.

### Pipeline page (`#products/:pid/pipelines/:id`)
Tabs: Overview · Stages/Tasks · Properties · Webhooks · Runs · Compliance.
- **Stages/Tasks tab**: visual pipeline graph. Each stage is a card with coloured left border. Tasks appear as rows inside.
  A YAML editor on the right shows the pipeline definition and clicking a stage/task highlights it.
- **Properties tab**: hierarchy of pipeline → stage → task properties. Each property shows name, type badge, value, description.
- **Runs tab**: table of recent runs with completion bar, status badge, triggered-by, duration.

### Pipeline Run page
Shows: run header (status badge, progress bar 0–100%, triggered-by, commit SHA, duration).
Below: each stage is an expandable row. Expanding shows task rows.
Each task row has: name · status badge · duration · exit code · **Context** button · **Logs** button.
Clicking **Context** opens a tabbed panel with 3 tabs:
  - **CDT Variables**: table of all CDT_* env vars injected into this task
  - **Properties**: the resolved CDT_PROPS map (property name → value)
  - **Output JSON**: the structured JSON object printed as the last stdout line

### Compliance page (`#compliance`)
Tabs: Rules · ISO 27001 · Audit Trail.
- Rules tab: table of admission rules (type, value, action, scope).
- ISO 27001 tab: control-by-control evaluation with pass/fail/partial status.
- Audit Trail: paginated log of all platform events.

### Maturity page (`#maturity`)
Product-level maturity overview. Expandable rows per product → applications → pipelines.
Each pipeline shows: score bar, grade badge (Initiation/Developing/Defined/Managed/Optimising), dimension breakdown.

### Administration → System page
Container runner configuration card at the top: select runner type (subprocess/docker/podman), image input, Save + Test buttons.
Below: LDAP config, Agent Pools table, Plugins table, Webhooks table.

### Chat (AI assistant)
Available via the chat icon or `/chat` route. The assistant can answer questions about the platform
and trigger actions. It uses tool calls to fetch live data before answering.

## Your capabilities
You can **read** all live platform data AND **perform actions** (trigger runs, create products/releases).
Always fetch data before answering questions about specific objects.
For actions, confirm what you are about to do before executing, and report the result clearly.
Never reveal vault secret values.
Format responses with markdown. Use tables for lists. Wrap IDs in backticks.
{user_info}"""


# ── Agentic loop ───────────────────────────────────────────────────────────────


def chat(messages: list[dict], current_user: Any = None, max_iterations: int = 8) -> dict:
    """Run the agentic chat loop and return the assistant reply."""
    # Read from DB first (covers seeds that bypass the settings API)
    from app.models.setting import PlatformSetting as _PS

    _row = _PS.query.get("GROQ_API_KEY")
    api_key = (_row.value if _row and _row.value else None) or current_app.config.get(
        "GROQ_API_KEY", ""
    )
    if not api_key:
        return {
            "reply": (
                "The AI assistant is not configured. "
                "Set the `GROQ_API_KEY` in Administration → Settings to enable it."
            ),
            "tool_calls": [],
        }

    from groq import Groq

    client = Groq(api_key=api_key)
    tool_calls_made: list[str] = []

    loop_messages: list[dict] = [
        {"role": "system", "content": _build_system_prompt(current_user)}
    ] + list(messages)

    try:
        for _ in range(max_iterations):
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=loop_messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=4096,
            )

            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            if finish_reason == "stop" or not msg.tool_calls:
                return {"reply": msg.content or "", "tool_calls": tool_calls_made}

            loop_messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )

            for tc in msg.tool_calls:
                tool_calls_made.append(tc.function.name)
                try:
                    inputs = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    inputs = {}
                result = _execute_tool(tc.function.name, inputs, current_user=current_user)
                loop_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str),
                    }
                )

        return {
            "reply": "I reached the maximum number of reasoning steps. Please try a more specific question.",
            "tool_calls": tool_calls_made,
        }

    except Exception as exc:
        log.error("Chat service error: %s", exc, exc_info=True)
        err = str(exc)
        if "api_key" in err.lower() or "authentication" in err.lower() or "401" in err:
            friendly = "The Groq API key appears to be invalid. Please update it in **Administration → Settings**."
        elif "rate" in err.lower() or "429" in err:
            friendly = "The AI assistant is temporarily rate-limited. Please try again in a moment."
        elif "connect" in err.lower() or "network" in err.lower() or "timeout" in err.lower():
            friendly = "Could not reach the Groq API. Please check your network connection."
        else:
            friendly = f"The AI assistant encountered an error: {err}"
        return {"reply": friendly, "tool_calls": tool_calls_made}
