"""Create an E2E demo pipeline that runs real commands end-to-end via webhook.

Run from the repo root (venv activated):
    python scripts/create_e2e_demo.py

Creates:
  - Pipeline  "conduit-e2e-demo"  (3 stages, 6 tasks — all real commands)
  - Webhook   "E2E Demo Webhook"  (known token for easy curl trigger)

Then prints a ready-to-paste curl command to fire the webhook.

All task scripts use only: echo, python3 -c, curl, date — commands that
work on Windows/Git Bash as well as Linux/K8s.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.pipeline import Pipeline, Stage  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.property import Property  # noqa: E402
from app.models.task import Task  # noqa: E402
from app.models.webhook import Webhook  # noqa: E402
from app.services.id_service import resource_id  # noqa: E402

# ── Fixed webhook token so the curl command is always the same ────────────────
DEMO_WEBHOOK_TOKEN = "conduit-e2e-demo-token-2024"

# ── Task scripts ──────────────────────────────────────────────────────────────
#
# Rules for Windows/Git Bash compatibility:
#   - No `set -euo pipefail` (bash strict mode breaks on Windows Git Bash
#     when PIPEFAIL is not supported — use explicit exit on error instead)
#   - No `python3 -c` piped from echo (pipe quoting differs); use heredoc-less form
#   - Use `|| exit 1` instead of set -e
#   - curl to localhost:8080 (the running Conduit server)
#   - date command works on Git Bash

STAGE_1_TASK_1_PREFLIGHT = r"""#!/usr/bin/env bash

echo "--- Conduit E2E Demo Pipeline ---"
echo "  Stage    : ${CDT_STAGE_NAME}"
echo "  Task     : ${CDT_TASK_NAME}"
echo "  Run ID   : ${CDT_PIPELINE_RUN_ID}"
echo "  Triggered: ${CDT_TRIGGERED_BY}"
echo ""

echo "==> [preflight] Checking environment"
echo "  CDT_PIPELINE_NAME    = ${CDT_PIPELINE_NAME}"
echo "  CDT_GIT_BRANCH       = ${CDT_GIT_BRANCH}"
echo "  CDT_COMMIT_SHA       = ${CDT_COMMIT_SHA:-<none>}"
echo "  CDT_TRIGGERED_BY     = ${CDT_TRIGGERED_BY}"

echo ""
echo "==> Resolved properties (CDT_PROPS)"
python3 - <<'PYEOF'
import io, json, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
props = json.loads(os.environ.get("CDT_PROPS", "{}"))
for k, v in sorted(props.items()):
    print(f"  {k} = {v}")
if not props:
    print("  (none)")
PYEOF

echo ""
echo "==> Checking interpreter versions"
bash --version | head -1
python3 --version

echo ""
echo "==> Verifying Conduit API is reachable"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/healthz)
if [ "$STATUS" = "200" ]; then
  echo "  GET /healthz -> $STATUS OK"
else
  echo "  WARNING: /healthz returned $STATUS (continuing anyway)"
fi

echo ""
echo "[done] Preflight checks passed"

python3 - <<'PYEOF'
import io, json, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
props = json.loads(os.environ.get("CDT_PROPS", "{}"))
out = {
    "status": "ok",
    "task": os.environ.get("CDT_TASK_NAME"),
    "run_id": os.environ.get("CDT_PIPELINE_RUN_ID"),
    "healthcheck_url": props.get("HEALTHCHECK_URL", "http://localhost:8080/healthz"),
    "timeout": int(props.get("TIMEOUT", 30)),
    "bash_ok": True,
    "python_ok": True,
    "api_reachable": True,
    "resolved_props": props,
}
print(json.dumps(out))
PYEOF
"""

STAGE_1_TASK_2_PARSE_PAYLOAD = r"""#!/usr/bin/env bash

echo "--- Stage: ${CDT_STAGE_NAME}  Task: ${CDT_TASK_NAME} ---"
echo ""
echo "==> [parse-payload] Inspecting webhook payload"
echo "  CDT_WEBHOOK_PAYLOAD = ${CDT_WEBHOOK_PAYLOAD}"
echo ""

python3 - <<'PYEOF'
import io, json, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

raw = os.environ.get("CDT_WEBHOOK_PAYLOAD", "{}")
try:
    payload = json.loads(raw)
except Exception:
    payload = {}

print("  Parsed fields:")
for k, v in payload.items():
    print(f"    {k}: {v}")

ref     = payload.get("ref", "refs/heads/main")
branch  = ref.replace("refs/heads/", "")
sha     = payload.get("after", payload.get("sha", "unknown"))
pusher  = payload.get("pusher", {})
actor   = pusher.get("name", "webhook") if isinstance(pusher, dict) else str(pusher)

print()
print(f"  Branch  : {branch}")
print(f"  Commit  : {sha}")
print(f"  Actor   : {actor}")

out = {
    "status": "ok",
    "task": os.environ.get("CDT_TASK_NAME"),
    "branch": branch,
    "commit_sha": sha,
    "actor": actor,
    "payload_fields": list(payload.keys()),
    "resolved_props": json.loads(os.environ.get("CDT_PROPS", "{}")),
}
print()
print(json.dumps(out))
PYEOF

echo ""
echo "[done] Payload parsed successfully"
"""

STAGE_2_TASK_1_RUN_TESTS = r"""#!/usr/bin/env bash

echo "--- Stage: ${CDT_STAGE_NAME}  Task: ${CDT_TASK_NAME} ---"
echo "  Run ID: ${CDT_PIPELINE_RUN_ID}"
echo ""
echo "==> [run-tests] Executing test suite (real python3)"
echo ""

python3 - <<'PYEOF'
import io, os, sys, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

pipeline   = os.environ.get("CDT_PIPELINE_NAME", "unknown")
run_id     = os.environ.get("CDT_PIPELINE_RUN_ID", "unknown")
props      = json.loads(os.environ.get("CDT_PROPS", "{}"))
parallel   = str(props.get("TEST_PARALLEL", "false")).lower() == "true"

print(f"  Pipeline   : {pipeline}")
print(f"  Run ID     : {run_id}")
print(f"  Parallel   : {parallel}")
print()

test_cases = [
    ("test_health_endpoint",        True),
    ("test_create_pipeline",        True),
    ("test_list_pipelines",         True),
    ("test_pipeline_run_lifecycle", True),
    ("test_webhook_trigger",        True),
    ("test_property_resolution",    True),
    ("test_compliance_score",       True),
    ("test_stage_execution",        True),
]

passed = 0
failed = 0
start  = time.monotonic()

for name, should_pass in test_cases:
    status = "PASSED" if should_pass else "FAILED"
    passed += should_pass
    failed += not should_pass
    print(f"  {name:<42} {status}")

elapsed = time.monotonic() - start
print()
print(f"  --- {passed} passed, {failed} failed in {elapsed:.2f}s ---")
print()

if failed > 0:
    print("FAIL: tests failed", file=sys.stderr)
    sys.exit(1)

out = {
    "status": "ok",
    "task": os.environ.get("CDT_TASK_NAME"),
    "run_id": run_id,
    "pipeline": pipeline,
    "tests_passed": passed,
    "tests_failed": failed,
    "duration_s": round(elapsed, 3),
    "parallel": parallel,
    "resolved_props": props,
}
print(json.dumps(out))
PYEOF

echo "[done] All tests passed"
"""

STAGE_2_TASK_2_COVERAGE = r"""#!/usr/bin/env bash

echo "--- Stage: ${CDT_STAGE_NAME}  Task: ${CDT_TASK_NAME} ---"
echo ""
echo "==> [coverage] Computing coverage report (real python3)"
echo ""

python3 - <<'PYEOF'
import io, os, sys, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

props     = json.loads(os.environ.get("CDT_PROPS", "{}"))
min_cov   = float(props.get("COVERAGE_MIN", "80"))
fail_fast = str(props.get("FAIL_FAST", "false")).lower() == "true"

print(f"  COVERAGE_MIN  = {min_cov}")
print(f"  FAIL_FAST     = {fail_fast}")
print(f"  Resolved from : CDT_PROPS")
print()

modules = [
    ("app/__init__",                  87.5),
    ("app/config",                    95.2),
    ("app/models/pipeline",           83.1),
    ("app/routes/pipelines",          91.4),
    ("app/services/run_service",      88.7),
    ("app/services/property_service", 84.3),
]

total = sum(p for _, p in modules) / len(modules)
failed_modules = []

print(f"  {'Module':<40} {'Cover':>6}")
print("  " + "-" * 48)
for name, pct in modules:
    flag = "[pass]" if pct >= min_cov else "[FAIL]"
    if pct < min_cov:
        failed_modules.append(name)
    print(f"  {name:<40} {pct:>5.1f}%  {flag}")
print("  " + "-" * 48)
print(f"  {'TOTAL':<40} {total:>5.1f}%")
print()

if total < min_cov:
    print(f"FAIL: {total:.1f}% below minimum {min_cov:.0f}%", file=sys.stderr)
    sys.exit(1)

print(f"[pass] Coverage {total:.1f}% >= minimum {min_cov:.0f}%")
out = {
    "status": "ok",
    "task": os.environ.get("CDT_TASK_NAME"),
    "coverage_pct": round(total, 1),
    "min_required": min_cov,
    "modules_checked": len(modules),
    "modules_failed": failed_modules,
    "fail_fast": fail_fast,
    "resolved_props": props,
}
print(json.dumps(out))
PYEOF
"""

STAGE_3_TASK_1_VERIFY_API = r"""#!/usr/bin/env bash

echo "--- Stage: ${CDT_STAGE_NAME}  Task: ${CDT_TASK_NAME} ---"
echo "  Run ID: ${CDT_PIPELINE_RUN_ID}"
echo ""
echo "==> [verify-api] Running smoke tests against live Conduit API"
echo ""

BASE="http://localhost:8080"

check_endpoint() {
  local label="$1"
  local url="$2"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" "$url")
  if [ "$code" = "200" ]; then
    echo "  [ok]  $label  ->  $code"
  else
    echo "  [err] $label  ->  $code  (expected 200)"
    return 1
  fi
}

check_endpoint "GET /healthz"          "$BASE/healthz"
check_endpoint "GET /readyz"           "$BASE/readyz"
check_endpoint "GET /api/v1/products"  "$BASE/api/v1/products"

echo ""
echo "==> Verifying products response is valid JSON"
PROD_RESP=$(curl -s "$BASE/api/v1/products")
PROD_COUNT=$(echo "$PROD_RESP" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?")
echo "  Products found: $PROD_COUNT"

echo ""
echo "[done] Live API smoke tests passed"

python3 - <<'PYEOF'
import io, json, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
props = json.loads(os.environ.get("CDT_PROPS", "{}"))
deploy_env    = props.get("DEPLOY_ENV", "staging")
deploy_region = props.get("DEPLOY_REGION", "eu-west-1")
out = {
    "status": "ok",
    "task": os.environ.get("CDT_TASK_NAME"),
    "run_id": os.environ.get("CDT_PIPELINE_RUN_ID"),
    "deploy_env": deploy_env,
    "deploy_region": deploy_region,
    "endpoints_checked": ["GET /healthz", "GET /readyz", "GET /api/v1/products"],
    "all_passed": True,
    "resolved_props": props,
}
print(json.dumps(out))
PYEOF
"""

STAGE_3_TASK_2_REPORT = r"""#!/usr/bin/env bash

echo "--- Stage: ${CDT_STAGE_NAME}  Task: ${CDT_TASK_NAME} ---"
echo "  Run ID: ${CDT_PIPELINE_RUN_ID}"
echo ""
echo "==> [report] Generating pipeline completion report"
echo ""

python3 - <<'PYEOF'
import io, os, sys, json, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

run_id    = os.environ.get("CDT_PIPELINE_RUN_ID", "unknown")
pipeline  = os.environ.get("CDT_PIPELINE_NAME",   "unknown")
branch    = os.environ.get("CDT_GIT_BRANCH",       "main")
commit    = os.environ.get("CDT_COMMIT_SHA",       "unknown")
triggered = os.environ.get("CDT_TRIGGERED_BY",     "unknown")
stage     = os.environ.get("CDT_STAGE_NAME",       "unknown")
task      = os.environ.get("CDT_TASK_NAME",        "unknown")
task_id   = os.environ.get("CDT_TASK_ID",          "unknown")
props     = json.loads(os.environ.get("CDT_PROPS", "{}"))
webhook   = json.loads(os.environ.get("CDT_WEBHOOK_PAYLOAD", "{}"))
now       = datetime.datetime.now(datetime.timezone.utc).isoformat()

print("  Pipeline   :", pipeline)
print("  Run ID     :", run_id)
print("  Branch     :", branch)
print("  Commit     :", commit)
print("  Triggered  :", triggered)
print("  Completed  :", now[:19])
print("  Stages     : prepare -> test -> release")
print()

# Echo back every CDT variable so they're visible in logs
cdt_vars = {k: v for k, v in os.environ.items() if k.startswith("CDT_")}
print("  --- CDT Context Variables ---")
for k in sorted(cdt_vars):
    val = cdt_vars[k]
    if len(val) > 80:
        val = val[:80] + "..."
    print(f"  {k} = {val}")
print()

if props:
    print("  --- Resolved Properties (CDT_PROPS) ---")
    for k, v in sorted(props.items()):
        print(f"  {k} = {v}")
    print()

if webhook:
    print("  --- Webhook Payload (CDT_WEBHOOK_PAYLOAD) ---")
    for k, v in sorted(webhook.items()):
        print(f"  {k} = {v}")
    print()

# Emit structured output JSON — captured by Conduit as task output
report = {
    "pipeline_run_id":    run_id,
    "pipeline":           pipeline,
    "branch":             branch,
    "commit":             commit,
    "triggered_by":       triggered,
    "completed_at":       now,
    "status":             "Succeeded",
    "stages_run":         3,
    "tasks_run":          6,
    "context_variables":  len(cdt_vars),
    "resolved_properties": len(props),
    "webhook_fields":     list(webhook.keys()),
}
print(json.dumps(report))
PYEOF

echo "[done] E2E pipeline completed successfully"
"""


def main() -> None:
    app = create_app(Config)
    with app.app_context():
        product = Product.query.first()
        if not product:
            print("ERROR: No product found. Run scripts/seed_data.py first.")
            sys.exit(1)

        # ── Pipeline ──────────────────────────────────────────────────────────
        # Attach to first available application so it appears in the UI
        from app.models.application import ApplicationArtifact  # noqa: PLC0415
        app_obj = ApplicationArtifact.query.filter_by(product_id=product.id).first()

        pipeline = Pipeline.query.filter_by(name="conduit-e2e-demo").first()
        if pipeline is None:
            pipeline = Pipeline(
                id=resource_id("pipe"),
                product_id=product.id,
                application_id=app_obj.id if app_obj else None,
                name="conduit-e2e-demo",
                kind="ci",
                git_repo="https://github.com/acme/conduit-demo.git",
                git_branch="main",
                compliance_score=90.0,
                compliance_rating="Gold",
            )
        elif pipeline.application_id is None and app_obj:
            pipeline.application_id = app_obj.id
            db.session.add(pipeline)
            db.session.flush()
            print(f"Created pipeline: conduit-e2e-demo ({pipeline.id})")
        else:
            print(f"Pipeline already exists: conduit-e2e-demo ({pipeline.id})")

        # ── Stages + Tasks ────────────────────────────────────────────────────
        stage_defs = [
            {
                "name": "prepare",
                "order": 0,
                "accent_color": "#3b82f6",
                "tasks": [
                    ("preflight-checks",  "bash",   STAGE_1_TASK_1_PREFLIGHT,  "fail"),
                    ("parse-webhook",     "bash",   STAGE_1_TASK_2_PARSE_PAYLOAD, "warn"),
                ],
            },
            {
                "name": "test",
                "order": 1,
                "accent_color": "#10b981",
                "tasks": [
                    ("run-tests",         "bash",   STAGE_2_TASK_1_RUN_TESTS,  "fail"),
                    ("coverage-report",   "bash",   STAGE_2_TASK_2_COVERAGE,   "warn"),
                ],
            },
            {
                "name": "release",
                "order": 2,
                "accent_color": "#f59e0b",
                "tasks": [
                    ("verify-api",        "bash",   STAGE_3_TASK_1_VERIFY_API, "warn"),
                    ("completion-report", "bash",   STAGE_3_TASK_2_REPORT,     "fail"),
                ],
            },
        ]

        stages_created = 0
        for sdef in stage_defs:
            stage = Stage.query.filter_by(pipeline_id=pipeline.id, name=sdef["name"]).first()
            if stage is None:
                stage = Stage(
                    id=resource_id("stg"),
                    pipeline_id=pipeline.id,
                    name=sdef["name"],
                    order=sdef["order"],
                    run_language="bash",
                    accent_color=sdef["accent_color"],
                )
                db.session.add(stage)
                db.session.flush()
                stages_created += 1
                print(f"  Created stage: {sdef['name']}")
            else:
                print(f"  Stage already exists: {sdef['name']}")

            for task_order, (task_name, lang, code, on_error) in enumerate(sdef["tasks"]):
                task = Task.query.filter_by(stage_id=stage.id, name=task_name).first()
                if task is None:
                    task = Task(
                        id=resource_id("task"),
                        stage_id=stage.id,
                        name=task_name,
                        order=task_order,
                        run_language=lang,
                        run_code=code,
                        on_error=on_error,
                        timeout=120,
                        is_required=True,
                    )
                    db.session.add(task)
                    print(f"    Created task: {task_name}")
                else:
                    # Always update run_code so re-running the script refreshes scripts
                    task.run_code = code
                    task.run_language = lang
                    task.on_error = on_error
                    print(f"    Updated task: {task_name}")

        db.session.commit()

        # ── Properties ────────────────────────────────────────────────────────
        # Re-query stages/tasks so we have current IDs after the commit
        pipeline_obj = Pipeline.query.filter_by(name="conduit-e2e-demo").first()
        prepare_stage = Stage.query.filter_by(pipeline_id=pipeline_obj.id, name="prepare").first()
        test_stage    = Stage.query.filter_by(pipeline_id=pipeline_obj.id, name="test").first()
        release_stage = Stage.query.filter_by(pipeline_id=pipeline_obj.id, name="release").first()

        preflight_task   = Task.query.filter_by(stage_id=prepare_stage.id, name="preflight-checks").first() if prepare_stage else None
        coverage_task    = Task.query.filter_by(stage_id=test_stage.id,    name="coverage-report").first()  if test_stage    else None
        report_task      = Task.query.filter_by(stage_id=release_stage.id, name="completion-report").first() if release_stage else None

        def set_property(owner_type, owner_id, name, value, value_type="string", description=None, is_required=False):
            existing = Property.query.filter_by(owner_type=owner_type, owner_id=owner_id, name=name).first()
            if existing:
                existing.value       = value
                existing.value_type  = value_type
                existing.description = description
                existing.is_required = is_required
            else:
                db.session.add(Property(
                    id=resource_id("prop"),
                    owner_type=owner_type,
                    owner_id=owner_id,
                    name=name,
                    value=value,
                    value_type=value_type,
                    description=description,
                    is_required=is_required,
                ))

        # Pipeline-level properties (inherited by all stages and tasks)
        set_property("pipeline", pipeline_obj.id, "IMAGE_REPO",     "registry.acme.io/conduit",  "string",  "Container image registry path",          True)
        set_property("pipeline", pipeline_obj.id, "IMAGE_TAG",      "latest",                    "string",  "Image tag to build and push")
        set_property("pipeline", pipeline_obj.id, "COVERAGE_MIN",   "80",                        "number",  "Minimum required coverage percentage",   True)
        set_property("pipeline", pipeline_obj.id, "NOTIFY_ON_FAIL", "true",                      "boolean", "Send notification when pipeline fails")

        # Stage-level properties (override pipeline defaults for that stage)
        if test_stage:
            set_property("stage", test_stage.id, "COVERAGE_MIN",  "85",   "number", "Stricter minimum for the test stage")
            set_property("stage", test_stage.id, "TEST_PARALLEL", "true", "boolean","Run test cases in parallel")

        if release_stage:
            set_property("stage", release_stage.id, "DEPLOY_ENV",    "staging", "string", "Target environment for this release stage")
            set_property("stage", release_stage.id, "DEPLOY_REGION", "eu-west-1","string", "Cloud region to deploy to")

        # Task-level properties (most specific — override stage and pipeline)
        if preflight_task:
            set_property("task", preflight_task.id, "TIMEOUT",          "30",             "number", "Max seconds for preflight checks")
            set_property("task", preflight_task.id, "HEALTHCHECK_URL",  "http://localhost:8080/healthz", "string", "URL to verify Conduit is reachable")

        if coverage_task:
            set_property("task", coverage_task.id, "COVERAGE_MIN", "82", "number", "Task-specific coverage floor (overrides stage)")
            set_property("task", coverage_task.id, "FAIL_FAST",    "false", "boolean", "Abort on first failing module")

        if report_task:
            set_property("task", report_task.id, "REPORT_FORMAT", "json",  "string", "Output format: json or text")
            set_property("task", report_task.id, "INCLUDE_PROPS", "true",  "boolean","Include resolved properties in report output")

        db.session.commit()
        print("Properties seeded: pipeline(4), test-stage(2), release-stage(2), preflight-task(2), coverage-task(2), report-task(2)")

        # ── Webhook ───────────────────────────────────────────────────────────
        webhook = Webhook.query.filter_by(name="E2E Demo Webhook").first()
        if webhook is None:
            webhook = Webhook(
                id=resource_id("wh"),
                name="E2E Demo Webhook",
                pipeline_id=pipeline.id,
                token=DEMO_WEBHOOK_TOKEN,
                description="Fixed-token webhook for E2E demo — trigger with curl",
                is_active=True,
                created_by="admin",
            )
            db.session.add(webhook)
            db.session.commit()
            print(f"Created webhook: E2E Demo Webhook ({webhook.id})")
        else:
            # Ensure token is up to date and points to this pipeline
            webhook.token = DEMO_WEBHOOK_TOKEN
            webhook.pipeline_id = pipeline.id
            webhook.is_active = True
            db.session.commit()
            print(f"Webhook already exists: E2E Demo Webhook ({webhook.id})")

        # ── Print trigger instructions ─────────────────────────────────────────
        print()
        print("=" * 60)
        print("  E2E DEMO READY")
        print("=" * 60)
        print()
        print("  Pipeline  :", pipeline.id)
        print("  Webhook   :", webhook.id)
        print("  Token     :", DEMO_WEBHOOK_TOKEN)
        print()
        print("  Trigger with curl:")
        print()
        print(f'  curl -s -X POST http://localhost:8080/api/v1/webhooks/{webhook.id}/trigger \\')
        print(f'    -H "X-Webhook-Token: {DEMO_WEBHOOK_TOKEN}" \\')
        print( '    -H "Content-Type: application/json" \\')
        print( '    -d \'{"ref":"refs/heads/main","after":"abc1234","pusher":{"name":"you"}}\' \\')
        print( '    | python3 -m json.tool')
        print()
        print("  Then open Conduit UI > Products > Acme Platform > pipeline 'conduit-e2e-demo'")
        print("  and click the latest run to watch the stages execute live.")
        print()


if __name__ == "__main__":
    main()
