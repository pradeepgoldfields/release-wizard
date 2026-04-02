"""
mcp_server.py — MCP server for Conduit

Exposes Products, Pipelines, Stages, Tasks, and Pipeline Runs as MCP tools
and resources so Claude and other AI assistants can inspect and interact with
the platform.

Run standalone (stdio transport — for Claude Desktop / Claude Code):
    python app/mcp_server.py

Run with SSE transport (for remote / HTTP clients):
    python app/mcp_server.py --transport sse --port 8081
"""

import json

# ── Flask app context ─────────────────────────────────────────────────────────
# Import after fastmcp so the app factory is available before any model import
import os
import sys

from fastmcp import FastMCP

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app  # noqa: E402
from app.models.backlog import BacklogItem  # noqa: E402
from app.models.pipeline import Pipeline, Stage  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.run import PipelineRun, StageRun  # noqa: E402
from app.models.task import Task, TaskRun  # noqa: E402

flask_app = create_app()

# ── MCP server ────────────────────────────────────────────────────────────────
mcp = FastMCP(
    name="Conduit",
    instructions=(
        "You are connected to Conduit, a CI/CD orchestration platform. "
        "Use the tools to inspect products, pipelines, stages, tasks, and run history. "
        "All IDs are string ULIDs. Use list_products to discover product IDs first."
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(description="List all products in the platform.")
def list_products() -> str:
    with flask_app.app_context():
        products = Product.query.order_by(Product.name).all()
        if not products:
            return "No products found."
        rows = [f"- {p.name} (id: {p.id})  {p.description or ''}" for p in products]
        return f"Found {len(products)} product(s):\n" + "\n".join(rows)


@mcp.tool(
    description="Get detailed information about a single product including pipeline and release counts."
)
def get_product(product_id: str) -> str:
    with flask_app.app_context():
        p = Product.query.get(product_id)
        if not p:
            return f"Product '{product_id}' not found."
        pipeline_count = Pipeline.query.filter_by(product_id=product_id).count()
        return (
            f"Product: {p.name}\n"
            f"ID: {p.id}\n"
            f"Description: {p.description or '—'}\n"
            f"Pipelines: {pipeline_count}\n"
            f"Created: {p.created_at.isoformat() if p.created_at else '—'}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINES
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(description="List all pipelines for a product.")
def list_pipelines(product_id: str) -> str:
    with flask_app.app_context():
        pipelines = Pipeline.query.filter_by(product_id=product_id).order_by(Pipeline.name).all()
        if not pipelines:
            return f"No pipelines found for product '{product_id}'."
        rows = [
            f"- {pl.name} (id: {pl.id})  kind={pl.kind}  compliance={pl.compliance_rating}"
            for pl in pipelines
        ]
        return f"Found {len(pipelines)} pipeline(s):\n" + "\n".join(rows)


@mcp.tool(
    description="Get detailed information about a pipeline including stages, git config, and compliance score."
)
def get_pipeline(product_id: str, pipeline_id: str) -> str:
    with flask_app.app_context():
        pl = Pipeline.query.filter_by(id=pipeline_id, product_id=product_id).first()
        if not pl:
            return f"Pipeline '{pipeline_id}' not found in product '{product_id}'."
        stage_count = Stage.query.filter_by(pipeline_id=pipeline_id).count()
        latest_run = (
            PipelineRun.query.filter_by(pipeline_id=pipeline_id)
            .order_by(PipelineRun.created_at.desc())
            .first()
        )
        return (
            f"Pipeline: {pl.name}\n"
            f"ID: {pl.id}\n"
            f"Kind: {pl.kind}\n"
            f"Git repo: {pl.git_repo or '—'}  branch: {pl.git_branch or 'main'}\n"
            f"Stages: {stage_count}\n"
            f"Compliance: {pl.compliance_rating} ({pl.compliance_score:.0f}%)\n"
            f"Latest run: {latest_run.status if latest_run else 'never run'} "
            f"({latest_run.id if latest_run else '—'})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# STAGES
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(
    description="List all stages in a pipeline with their order, execution mode, and task counts."
)
def list_stages(pipeline_id: str) -> str:
    with flask_app.app_context():
        stages = Stage.query.filter_by(pipeline_id=pipeline_id).order_by(Stage.order).all()
        if not stages:
            return f"No stages found for pipeline '{pipeline_id}'."
        rows = []
        for s in stages:
            task_count = Task.query.filter_by(stage_id=s.id).count()
            protected = " 🔒" if s.is_protected else ""
            rows.append(
                f"  [{s.order}] {s.name} (id: {s.id})  "
                f"mode={s.execution_mode}  lang={s.run_language or 'bash'}  "
                f"tasks={task_count}{protected}"
            )
        return f"Found {len(stages)} stage(s) in pipeline '{pipeline_id}':\n" + "\n".join(rows)


@mcp.tool(description="Get full details of a single stage including gates and run condition.")
def get_stage(pipeline_id: str, stage_id: str) -> str:
    with flask_app.app_context():
        s = Stage.query.filter_by(id=stage_id, pipeline_id=pipeline_id).first()
        if not s:
            return f"Stage '{stage_id}' not found."
        tasks = Task.query.filter_by(stage_id=stage_id).order_by(Task.order).all()
        task_names = ", ".join(t.name for t in tasks) or "—"
        eg = s.entry_gate or {}
        xg = s.exit_gate or {}
        return (
            f"Stage: {s.name}\n"
            f"ID: {s.id}\n"
            f"Order: {s.order}\n"
            f"Execution mode: {s.execution_mode}\n"
            f"Run condition: {s.run_condition or 'always'}\n"
            f"Language: {s.run_language or 'bash'}\n"
            f"Container: {s.container_image or '—'}\n"
            f"Protected: {s.is_protected}\n"
            f"Entry gate: {'enabled' if eg.get('enabled') else 'disabled'}\n"
            f"Exit gate: {'enabled' if xg.get('enabled') else 'disabled'}\n"
            f"Tasks ({len(tasks)}): {task_names}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TASKS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(description="List all tasks in a stage.")
def list_tasks(stage_id: str) -> str:
    with flask_app.app_context():
        tasks = Task.query.filter_by(stage_id=stage_id).order_by(Task.order).all()
        if not tasks:
            return f"No tasks found for stage '{stage_id}'."
        rows = [
            f"  [{t.order}] {t.name} (id: {t.id})  kind={t.kind}  on_error={t.on_error}  timeout={t.timeout}s"
            for t in tasks
        ]
        return f"Found {len(tasks)} task(s):\n" + "\n".join(rows)


@mcp.tool(
    description="Get full details of a task including its script code, gate script, or approval config."
)
def get_task(task_id: str) -> str:
    with flask_app.app_context():
        t = Task.query.get(task_id)
        if not t:
            return f"Task '{task_id}' not found."
        detail = (
            f"Task: {t.name}\n"
            f"ID: {t.id}\n"
            f"Kind: {t.kind}\n"
            f"Description: {t.description or '—'}\n"
            f"Order: {t.order}\n"
            f"Language: {t.run_language or 'bash'}\n"
            f"On error: {t.on_error}\n"
            f"Timeout: {t.timeout}s\n"
            f"Required: {t.is_required}\n"
            f"Run condition: {t.run_condition or 'always'}\n"
        )
        if t.kind == "script" and t.run_code:
            code_preview = t.run_code[:500] + ("…" if len(t.run_code) > 500 else "")
            detail += f"Script ({t.run_language}):\n```\n{code_preview}\n```"
        elif t.kind == "gate" and t.gate_script:
            detail += f"Gate script:\n```\n{t.gate_script[:500]}\n```"
        elif t.kind == "approval":
            try:
                approvers = json.loads(t.approval_approvers or "[]")
            except Exception:
                approvers = []
            detail += (
                f"Approvers: {', '.join(approvers) or '—'}\n"
                f"Required approvals: {t.approval_required_count}\n"
                f"Approval timeout: {t.approval_timeout}s"
            )
        return detail


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE RUNS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(
    description="List recent pipeline runs for a pipeline. Returns up to 20 most recent runs."
)
def list_pipeline_runs(pipeline_id: str, limit: int | None = 20) -> str:
    with flask_app.app_context():
        runs = (
            PipelineRun.query.filter_by(pipeline_id=pipeline_id)
            .order_by(PipelineRun.created_at.desc())
            .limit(min(limit or 20, 50))
            .all()
        )
        if not runs:
            return f"No runs found for pipeline '{pipeline_id}'."
        rows = [
            f"  - {r.id}  status={r.status}  triggered_by={r.triggered_by or 'manual'}  "
            f"created={r.created_at.isoformat() if r.created_at else '—'}"
            for r in runs
        ]
        return f"Found {len(runs)} run(s):\n" + "\n".join(rows)


@mcp.tool(
    description="Get full details of a pipeline run including all stage and task run statuses."
)
def get_pipeline_run(run_id: str) -> str:
    with flask_app.app_context():
        run = PipelineRun.query.get(run_id)
        if not run:
            return f"Pipeline run '{run_id}' not found."

        stage_runs = (
            StageRun.query.filter_by(pipeline_run_id=run_id).order_by(StageRun.started_at).all()
        )

        lines = [
            f"Run: {run.id}",
            f"Pipeline: {run.pipeline_id}",
            f"Status: {run.status}",
            f"Triggered by: {run.triggered_by or 'manual'}",
            f"Created: {run.created_at.isoformat() if run.created_at else '—'}",
            f"Stage runs ({len(stage_runs)}):",
        ]
        for sr in stage_runs:
            task_runs = (
                TaskRun.query.filter_by(stage_run_id=sr.id).order_by(TaskRun.started_at).all()
            )
            lines.append(f"  [{sr.status}] {sr.stage_name or sr.stage_id}")
            for tr in task_runs:
                lines.append(f"      [{tr.status}] {tr.task_name or tr.task_id}")

        return "\n".join(lines)


@mcp.tool(
    description="Get a summary of all pipeline run statuses across a product — useful for health checks."
)
def product_run_summary(product_id: str) -> str:
    with flask_app.app_context():
        pipelines = Pipeline.query.filter_by(product_id=product_id).all()
        if not pipelines:
            return f"No pipelines found for product '{product_id}'."

        lines = [f"Run summary for product '{product_id}':"]
        for pl in pipelines:
            latest = (
                PipelineRun.query.filter_by(pipeline_id=pl.id)
                .order_by(PipelineRun.created_at.desc())
                .first()
            )
            status = latest.status if latest else "never run"
            created = latest.created_at.isoformat() if latest and latest.created_at else "—"
            lines.append(f"  {pl.name}: {status} ({created})")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# RESOURCES  (read-only, URI-addressable)
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.resource("release-wizard://products")
def resource_all_products() -> str:
    """All products as a JSON list."""
    with flask_app.app_context():
        products = Product.query.order_by(Product.name).all()
        return json.dumps([p.to_dict() for p in products], indent=2, default=str)


@mcp.resource("release-wizard://products/{product_id}/pipelines")
def resource_product_pipelines(product_id: str) -> str:
    """All pipelines for a product as JSON."""
    with flask_app.app_context():
        pipelines = Pipeline.query.filter_by(product_id=product_id).order_by(Pipeline.name).all()
        return json.dumps([pl.to_dict() for pl in pipelines], indent=2, default=str)


@mcp.resource("release-wizard://pipelines/{pipeline_id}/stages")
def resource_pipeline_stages(pipeline_id: str) -> str:
    """All stages for a pipeline as JSON."""
    with flask_app.app_context():
        stages = Stage.query.filter_by(pipeline_id=pipeline_id).order_by(Stage.order).all()
        return json.dumps([s.to_dict() for s in stages], indent=2, default=str)


@mcp.resource("release-wizard://pipelines/{pipeline_id}/runs/latest")
def resource_latest_run(pipeline_id: str) -> str:
    """Latest pipeline run as JSON."""
    with flask_app.app_context():
        run = (
            PipelineRun.query.filter_by(pipeline_id=pipeline_id)
            .order_by(PipelineRun.created_at.desc())
            .first()
        )
        if not run:
            return json.dumps({"error": "No runs found"})
        return json.dumps(run.to_dict(include_stages=True), indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════════════════
# BACKLOG
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(description="List backlog items for a product. Filter by status, priority, or item_type.")
def list_backlog(product_id: str, status: str | None = None, priority: str | None = None) -> str:
    with flask_app.app_context():
        q = BacklogItem.query.filter_by(product_id=product_id)
        if status:
            q = q.filter(BacklogItem.status == status)
        if priority:
            q = q.filter(BacklogItem.priority == priority)
        items = q.order_by(BacklogItem.created_at.desc()).all()
        if not items:
            return f"No backlog items found for product '{product_id}'."
        rows = [
            f"  - [{i.priority.upper()}] {i.title} (id: {i.id})  "
            f"type={i.item_type}  status={i.status}  effort={i.effort or 0}pt"
            for i in items
        ]
        return f"Found {len(items)} backlog item(s):\n" + "\n".join(rows)


@mcp.tool(description="Create a new backlog item for a product.")
def create_backlog_item(
    product_id: str,
    title: str,
    description: str = "",
    item_type: str = "feature",
    priority: str = "medium",
    effort: int = 0,
) -> str:
    with flask_app.app_context():
        from app.services.id_service import resource_id  # noqa: PLC0415

        item = BacklogItem(
            id=resource_id("backlog"),
            product_id=product_id,
            title=title,
            description=description,
            item_type=item_type,
            priority=priority,
            effort=effort,
            status="open",
            labels="[]",
        )
        from app.extensions import db  # noqa: PLC0415

        db.session.add(item)
        db.session.commit()
        return f"Created backlog item '{title}' (id: {item.id}) in product '{product_id}'."


@mcp.tool(description="Update a backlog item's status, priority, or other fields.")
def update_backlog_item(
    item_id: str,
    status: str | None = None,
    priority: str | None = None,
    title: str | None = None,
    description: str | None = None,
) -> str:
    with flask_app.app_context():
        item = BacklogItem.query.get(item_id)
        if not item:
            return f"Backlog item '{item_id}' not found."
        if status is not None:
            item.status = status
        if priority is not None:
            item.priority = priority
        if title is not None:
            item.title = title
        if description is not None:
            item.description = description
        from app.extensions import db  # noqa: PLC0415

        db.session.commit()
        return (
            f"Updated backlog item '{item.title}' (id: {item.id})  "
            f"status={item.status}  priority={item.priority}."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Conduit MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8081,
        help="Port for SSE transport (default: 8081)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE transport (default: 127.0.0.1)",
    )
    args = parser.parse_args()

    if args.transport == "sse":
        print(
            f"Starting MCP server on http://{args.host}:{args.port} (SSE transport)",
            file=sys.stderr,
        )
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        print("Starting MCP server on stdio transport", file=sys.stderr)
        mcp.run(transport="stdio")
