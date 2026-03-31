"""Seed script — creates realistic test data in the running app's database.

Run from the repo root (with venv activated):
    python scripts/seed_data.py

Creates data for every model:
  - 1 Product ("Acme Platform")
  - 3 Environments (dev, staging, prod)
  - 4 Applications (API Service, Frontend, Worker, Data Pipeline)
  - 10 Pipelines spread across applications (ci + cd per app)
  - 5 Stages per pipeline with 2-3 Tasks each
  - 2 Releases with application groups
  - 3 Users (admin, alice, bob) + 2 Groups + 3 Roles + RoleBindings
  - 3 ComplianceRules + sample AuditEvents
  - 3 VaultSecrets
  - 2 Webhooks
  - 3 AgentPools
  - 3 Plugins + PluginConfigs
  - Sample PipelineRuns / StageRuns / TaskRuns

The script is idempotent — re-running will skip objects that already exist.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt  # noqa: E402

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.domain.enums import ArtifactType, ComplianceRating, EnvironmentType  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.application import ApplicationArtifact  # noqa: E402
from app.models.auth import Group, Role, RoleBinding, User  # noqa: E402
from app.models.compliance import AuditEvent, ComplianceRule  # noqa: E402
from app.models.environment import Environment  # noqa: E402
from app.models.pipeline import Pipeline, Stage  # noqa: E402
from app.models.plugin import Plugin, PluginConfig  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.release import Release, ReleaseApplicationGroup  # noqa: E402
from app.models.run import PipelineRun, ReleaseRun, StageRun  # noqa: E402
from app.models.task import AgentPool, Task, TaskRun  # noqa: E402
from app.models.vault import VaultSecret  # noqa: E402
from app.models.webhook import Webhook  # noqa: E402
from app.services.id_service import pipeline_run_id, release_run_id, resource_id  # noqa: E402
from app.services.vault_service import encrypt  # noqa: E402

# ── Bash/Python task scripts ──────────────────────────────────────────────────

BASH_SCRIPTS = {
    "checkout": """\
#!/usr/bin/env bash
set -euo pipefail

# ── Conduit context ──────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pipeline : ${CDT_PIPELINE_NAME}"
echo "  Run ID   : ${CDT_PIPELINE_RUN_ID}"
echo "  Commit   : ${CDT_COMMIT_SHA:-<none>}"
echo "  Branch   : ${CDT_GIT_BRANCH}"
echo "  Triggered: ${CDT_TRIGGERED_BY}"
echo "  Stage    : ${CDT_STAGE_NAME}"
echo "  Task     : ${CDT_TASK_NAME}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "==> [checkout] Cloning repository"
REPO="${CDT_GIT_REPO:-https://github.com/acme/api-service.git}"
BRANCH="${CDT_GIT_BRANCH:-main}"
echo "  Repo  : $REPO"
echo "  Branch: $BRANCH"
echo "  Commit: ${CDT_COMMIT_SHA:-HEAD}"
echo ""

# Simulate clone output
echo "Cloning into '/workspace/src'..."
echo "remote: Enumerating objects: 847, done."
echo "remote: Counting objects: 100% (847/847), done."
echo "remote: Compressing objects: 100% (412/412), done."
echo "Receiving objects: 100% (847/847), 1.23 MiB | 8.41 MiB/s, done."
echo ""
echo "HEAD: ${CDT_COMMIT_SHA:-a1b2c3d}"
echo "Branch: $BRANCH"
echo ""
echo "✓ Checkout complete"
""",

    "lint": """\
#!/usr/bin/env bash
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pipeline : ${CDT_PIPELINE_NAME}"
echo "  Stage    : ${CDT_STAGE_NAME}  |  Task: ${CDT_TASK_NAME}"
echo "  Commit   : ${CDT_COMMIT_SHA:-<none>}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "==> [lint] Running ruff + format check"
echo "  ruff check . --output-format=github"
echo ""
echo "Checking 42 files..."
echo "app/__init__.py ... ok"
echo "app/config.py ... ok"
echo "app/models/pipeline.py ... ok"
echo "app/routes/pipelines.py ... ok"
echo "app/services/run_service.py ... ok"
echo "... (37 more files)"
echo ""
echo "ruff format --check ."
echo "42 files already formatted"
echo ""
echo "✓ Lint passed — 0 issues found"
""",

    "unit_test": """\
#!/usr/bin/env bash
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pipeline : ${CDT_PIPELINE_NAME}"
echo "  Stage    : ${CDT_STAGE_NAME}  |  Task: ${CDT_TASK_NAME}"
echo "  Run ID   : ${CDT_PIPELINE_RUN_ID}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "==> [unit-tests] Running pytest"
echo ""
echo "collected 40 items"
echo ""
echo "tests/unit/test_health.py::test_healthz PASSED           [  2%]"
echo "tests/unit/test_health.py::test_readyz PASSED            [  5%]"
echo "tests/unit/test_pipelines.py::test_create_pipeline PASSED [ 10%]"
echo "tests/unit/test_pipelines.py::test_list_pipelines PASSED [ 12%]"
echo "tests/unit/test_pipelines.py::test_delete_pipeline PASSED [ 15%]"
echo "tests/unit/test_runs.py::test_create_run PASSED          [ 17%]"
echo "tests/unit/test_runs.py::test_run_status PASSED          [ 20%]"
echo "tests/unit/test_products.py::test_create_product PASSED  [ 22%]"
echo "tests/unit/test_products.py::test_list_products PASSED   [ 25%]"
echo "... (31 more)"
echo ""
echo "━━━ 40 passed in 12.3s ━━━"
echo ""
echo "✓ All unit tests passed"
""",

    "build_image": """\
#!/usr/bin/env bash
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pipeline : ${CDT_PIPELINE_NAME}"
echo "  Stage    : ${CDT_STAGE_NAME}  |  Task: ${CDT_TASK_NAME}"
echo "  Commit   : ${CDT_COMMIT_SHA:-latest}"
echo "  Triggered: ${CDT_TRIGGERED_BY}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Read properties from CDT_PROPS
IMAGE_REPO=$(echo "${CDT_PROPS:-{}}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('IMAGE_REPO','registry.acme.internal/api'))" 2>/dev/null || echo "registry.acme.internal/api")
IMAGE_TAG="${IMAGE_REPO}:${CDT_COMMIT_SHA:-latest}"

echo "==> [build-image] Building container image"
echo "  Image : $IMAGE_TAG"
echo "  Repo  : ${CDT_GIT_REPO}"
echo ""
echo "STEP 1/8  FROM ubi9/python-312:latest"
echo "STEP 2/8  WORKDIR /app"
echo "STEP 3/8  COPY requirements.txt ."
echo "STEP 4/8  RUN pip install -r requirements.txt"
echo "          --> Installing 23 packages..."
echo "STEP 5/8  COPY . ."
echo "STEP 6/8  RUN ruff check ."
echo "STEP 7/8  EXPOSE 8080"
echo "STEP 8/8  CMD [\"gunicorn\", \"wsgi:app\"]"
echo ""
echo "Successfully built $IMAGE_TAG"
echo "Pushing $IMAGE_TAG ..."
echo "  Layer 1/6: digest sha256:a1b2c3 pushed"
echo "  Layer 2/6: digest sha256:d4e5f6 pushed"
echo "  Layer 3/6: digest sha256:b7c8d9 pushed"
echo "  Layer 4/6: already exists"
echo "  Layer 5/6: already exists"
echo "  Layer 6/6: digest sha256:e1f2a3 pushed"
echo ""
echo "✓ Image pushed: $IMAGE_TAG"
""",

    "deploy": """\
#!/usr/bin/env bash
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pipeline : ${CDT_PIPELINE_NAME}"
echo "  Stage    : ${CDT_STAGE_NAME}  |  Task: ${CDT_TASK_NAME}"
echo "  Run ID   : ${CDT_PIPELINE_RUN_ID}"
echo "  Triggered: ${CDT_TRIGGERED_BY}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

NAMESPACE=$(echo "${CDT_PROPS:-{}}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('NAMESPACE','acme-dev'))" 2>/dev/null || echo "acme-dev")
IMAGE_REPO=$(echo "${CDT_PROPS:-{}}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('IMAGE_REPO','registry.acme.internal/api'))" 2>/dev/null || echo "registry.acme.internal/api")
IMAGE_TAG="${IMAGE_REPO}:${CDT_COMMIT_SHA:-latest}"

echo "==> [deploy] Deploying to Kubernetes"
echo "  Namespace : $NAMESPACE"
echo "  Image     : $IMAGE_TAG"
echo "  Branch    : ${CDT_GIT_BRANCH}"
echo ""
echo "Applying manifests..."
echo "  deployment.apps/api-service configured"
echo "  service/api-service unchanged"
echo "  configmap/api-config configured"
echo ""
echo "Waiting for rollout..."
echo "  Waiting for deployment \"api-service\" rollout to finish: 0 of 3 updated..."
echo "  Waiting for deployment \"api-service\" rollout to finish: 1 of 3 updated..."
echo "  Waiting for deployment \"api-service\" rollout to finish: 2 of 3 updated..."
echo "  deployment \"api-service\" successfully rolled out"
echo ""
echo "✓ Deploy complete → $NAMESPACE"
""",

    "smoke_test": """\
#!/usr/bin/env bash
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pipeline : ${CDT_PIPELINE_NAME}"
echo "  Stage    : ${CDT_STAGE_NAME}  |  Task: ${CDT_TASK_NAME}"
echo "  Run ID   : ${CDT_PIPELINE_RUN_ID}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

BASE_URL="${APP_URL:-http://localhost:8080}"
echo "==> [smoke-test] Running smoke tests"
echo "  Target: $BASE_URL"
echo ""
echo "  GET $BASE_URL/healthz ... 200 OK  {\"status\":\"ok\"}"
echo "  GET $BASE_URL/readyz  ... 200 OK  {\"status\":\"ok\"}"
echo "  GET $BASE_URL/api/v1/products ... 200 OK  (3 products)"
echo ""
echo "✓ All smoke tests passed (3/3)"
""",

    "cleanup": """\
#!/usr/bin/env bash
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pipeline : ${CDT_PIPELINE_NAME}"
echo "  Task     : ${CDT_TASK_NAME}  |  Run: ${CDT_PIPELINE_RUN_ID}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "==> [cleanup] Purging workspace"
echo "  Removing /workspace/src ..."
echo "  Removing /workspace/artifacts ..."
echo "  Removing /tmp/conduit-* ..."
echo ""
echo "  Freed: 847 MB"
echo ""
echo "✓ Workspace clean"
""",

    "tag_release": """\
#!/usr/bin/env bash
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pipeline : ${CDT_PIPELINE_NAME}"
echo "  Stage    : ${CDT_STAGE_NAME}  |  Task: ${CDT_TASK_NAME}"
echo "  Commit   : ${CDT_COMMIT_SHA}"
echo "  Triggered: ${CDT_TRIGGERED_BY}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

TAG="v$(date +%Y.%m.%d)-${CDT_COMMIT_SHA:0:7}"
echo "==> [tag-release] Creating release tag"
echo "  Tag    : $TAG"
echo "  Commit : ${CDT_COMMIT_SHA}"
echo "  Branch : ${CDT_GIT_BRANCH}"
echo "  Author : ${CDT_TRIGGERED_BY}"
echo ""
echo "  git tag -a \"$TAG\" ${CDT_COMMIT_SHA} -m \"Release $TAG — run ${CDT_PIPELINE_RUN_ID}\""
echo "  git push origin \"$TAG\""
echo ""
echo "✓ Tag $TAG pushed to origin"
""",

    "notify": """\
#!/usr/bin/env bash
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pipeline : ${CDT_PIPELINE_NAME}"
echo "  Stage    : ${CDT_STAGE_NAME}  |  Task: ${CDT_TASK_NAME}"
echo "  Run ID   : ${CDT_PIPELINE_RUN_ID}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

CHANNEL=$(echo "${CDT_PROPS:-{}}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('SLACK_CHANNEL','#ci-cd'))" 2>/dev/null || echo "#ci-cd")

echo "==> [notify] Sending pipeline notification"
echo "  Channel  : $CHANNEL"
echo "  Pipeline : ${CDT_PIPELINE_NAME}"
echo "  Commit   : ${CDT_COMMIT_SHA}"
echo "  Branch   : ${CDT_GIT_BRANCH}"
echo "  Run ID   : ${CDT_PIPELINE_RUN_ID}"
echo ""
echo "  Payload: {\"channel\":\"$CHANNEL\",\"text\":\"✓ *${CDT_PIPELINE_NAME}* passed · ${CDT_COMMIT_SHA} · triggered by ${CDT_TRIGGERED_BY}\"}"
echo "  HTTP 200 OK"
echo ""
echo "✓ Notification sent to $CHANNEL"
""",
}

PYTHON_SCRIPTS = {
    "collect_metrics": """\
#!/usr/bin/env python3
\"\"\"Collect test coverage metrics — uses CDT_* context variables.\"\"\"
import json, os, sys

# ── Conduit context ──────────────────────────────────────────────────────────
pipeline  = os.environ.get("CDT_PIPELINE_NAME", "unknown")
run_id    = os.environ.get("CDT_PIPELINE_RUN_ID", "unknown")
stage     = os.environ.get("CDT_STAGE_NAME", "unknown")
task      = os.environ.get("CDT_TASK_NAME", "unknown")
commit    = os.environ.get("CDT_COMMIT_SHA", "unknown")
props     = json.loads(os.environ.get("CDT_PROPS", "{}"))

print("━" * 48)
print(f"  Pipeline : {pipeline}")
print(f"  Stage    : {stage}  |  Task: {task}")
print(f"  Commit   : {commit}")
print("━" * 48)
print()

coverage_min = float(props.get("COVERAGE_MIN", 80))
print(f"==> [collect-metrics] Running coverage analysis")
print(f"  Minimum required: {coverage_min:.0f}%")
print()

# Simulate coverage output
modules = [
    ("app/__init__",       98.0),
    ("app/config",         95.0),
    ("app/models/pipeline",87.5),
    ("app/models/task",    91.2),
    ("app/routes/pipelines",83.4),
    ("app/routes/runs",    79.8),
    ("app/services/run_service", 88.1),
    ("app/services/property_service", 92.3),
]
total = sum(p for _, p in modules) / len(modules)

print(f"{'Module':<45} {'Cover':>6}")
print("-" * 53)
for name, pct in modules:
    bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
    flag = "  ✓" if pct >= coverage_min else "  ✗"
    print(f"  {name:<43} {pct:>5.1f}%{flag}")
print("-" * 53)
print(f"  {'TOTAL':<43} {total:>5.1f}%")
print()

if total < coverage_min:
    print(f"FAIL: coverage {total:.1f}% is below minimum {coverage_min:.0f}%", file=sys.stderr)
    sys.exit(1)

print(f"✓ Coverage {total:.1f}% meets minimum {coverage_min:.0f}%")
print(f"  run_id={run_id}")
""",

    "security_scan": """\
#!/usr/bin/env python3
\"\"\"SAST security scan — uses CDT_* context variables.\"\"\"
import json, os, sys

# ── Conduit context ──────────────────────────────────────────────────────────
pipeline = os.environ.get("CDT_PIPELINE_NAME", "unknown")
stage    = os.environ.get("CDT_STAGE_NAME", "unknown")
task     = os.environ.get("CDT_TASK_NAME", "unknown")
commit   = os.environ.get("CDT_COMMIT_SHA", "unknown")
run_id   = os.environ.get("CDT_PIPELINE_RUN_ID", "unknown")
props    = json.loads(os.environ.get("CDT_PROPS", "{}"))

print("━" * 48)
print(f"  Pipeline : {pipeline}")
print(f"  Stage    : {stage}  |  Task: {task}")
print(f"  Commit   : {commit}")
print("━" * 48)
print()

fail_on_high = str(props.get("FAIL_ON_HIGH", "true")).lower() == "true"
print(f"==> [security-scan] Running SAST analysis")
print(f"  Tool         : bandit 1.7.x")
print(f"  Scope        : app/")
print(f"  Fail on HIGH : {fail_on_high}")
print()

# Simulate scan findings
findings = [
    ("LOW",    "app/config.py:18",        "B105", "Possible hardcoded password string"),
    ("MEDIUM", "app/routes/auth.py:47",   "B608", "Possible SQL injection via string format"),
    ("LOW",    "app/services/run_service.py:112", "B603", "subprocess call without shell=True"),
]
highs = [f for f in findings if f[0] == "HIGH"]
mediums = [f for f in findings if f[0] == "MEDIUM"]
lows = [f for f in findings if f[0] == "LOW"]

for sev, loc, code, msg in findings:
    icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵"}.get(sev, "⚪")
    print(f"  {icon} [{sev}] {code} @ {loc}")
    print(f"       {msg}")
print()
print(f"  Summary: HIGH={len(highs)}  MEDIUM={len(mediums)}  LOW={len(lows)}")
print()

if highs and fail_on_high:
    print(f"FAIL: {len(highs)} HIGH severity finding(s)", file=sys.stderr)
    sys.exit(1)

print(f"✓ Security scan complete — no blocking issues")
print(f"  run_id={run_id}")
""",

    "integration_test": """\
#!/usr/bin/env python3
\"\"\"Integration test suite — uses CDT_* context variables.\"\"\"
import json, os, sys

# ── Conduit context ──────────────────────────────────────────────────────────
pipeline = os.environ.get("CDT_PIPELINE_NAME", "unknown")
stage    = os.environ.get("CDT_STAGE_NAME", "unknown")
task     = os.environ.get("CDT_TASK_NAME", "unknown")
commit   = os.environ.get("CDT_COMMIT_SHA", "unknown")
run_id   = os.environ.get("CDT_PIPELINE_RUN_ID", "unknown")
git_repo = os.environ.get("CDT_GIT_REPO", "unknown")

print("━" * 48)
print(f"  Pipeline : {pipeline}")
print(f"  Stage    : {stage}  |  Task: {task}")
print(f"  Commit   : {commit}")
print(f"  Repo     : {git_repo}")
print("━" * 48)
print()

base_url = os.environ.get("APP_URL", "http://localhost:8080")
print(f"==> [integration-tests] Running against {base_url}")
print()

# Simulate test suite
tests = [
    ("test_api_health",              "PASSED", 0.12),
    ("test_product_crud",            "PASSED", 0.84),
    ("test_pipeline_create_run",     "PASSED", 1.23),
    ("test_pipeline_run_status",     "PASSED", 0.55),
    ("test_stage_ordering",          "PASSED", 0.33),
    ("test_compliance_rule_gate",    "PASSED", 0.91),
    ("test_webhook_trigger",         "PASSED", 0.47),
    ("test_user_rbac_enforcement",   "PASSED", 0.62),
    ("test_vault_secret_inject",     "PASSED", 0.38),
    ("test_audit_event_recorded",    "PASSED", 0.29),
]
for name, result, dur in tests:
    icon = "✓" if result == "PASSED" else "✗"
    print(f"  {icon} {name:<42} {dur:.2f}s")

passed = sum(1 for _, r, _ in tests if r == "PASSED")
total  = len(tests)
print()
print(f"━━━ {passed}/{total} passed in {sum(d for _,_,d in tests):.2f}s ━━━")
print()
print(f"✓ Integration tests passed  run_id={run_id}")
""",

    "validate_manifest": """\
#!/usr/bin/env python3
\"\"\"Validate Kubernetes manifests — uses CDT_* context variables.\"\"\"
import json, os, sys

# ── Conduit context ──────────────────────────────────────────────────────────
pipeline = os.environ.get("CDT_PIPELINE_NAME", "unknown")
stage    = os.environ.get("CDT_STAGE_NAME", "unknown")
task     = os.environ.get("CDT_TASK_NAME", "unknown")
commit   = os.environ.get("CDT_COMMIT_SHA", "unknown")
run_id   = os.environ.get("CDT_PIPELINE_RUN_ID", "unknown")

print("━" * 48)
print(f"  Pipeline : {pipeline}")
print(f"  Stage    : {stage}  |  Task: {task}")
print(f"  Commit   : {commit}")
print("━" * 48)
print()

print("==> [validate-k8s] Validating Kubernetes manifests")
print()

manifests = [
    ("k8s/deployment.yaml",  "apps/v1",  "Deployment",            "✓ valid"),
    ("k8s/service.yaml",     "v1",       "Service",               "✓ valid"),
    ("k8s/configmap.yaml",   "v1",       "ConfigMap",             "✓ valid"),
    ("k8s/ingress.yaml",     "networking.k8s.io/v1", "Ingress",   "✓ valid"),
    ("helm/conduit/Chart.yaml", "—",     "HelmChart",             "✓ valid"),
]
for path, api, kind, status in manifests:
    print(f"  {status}  {path:<38} [{api} / {kind}]")

print()
print(f"✓ All {len(manifests)} manifests valid  run_id={run_id}")
""",

    "generate_sbom": """\
#!/usr/bin/env python3
\"\"\"Generate Software Bill of Materials — uses CDT_* context variables.\"\"\"
import json, os, sys

# ── Conduit context ──────────────────────────────────────────────────────────
pipeline = os.environ.get("CDT_PIPELINE_NAME", "unknown")
stage    = os.environ.get("CDT_STAGE_NAME", "unknown")
task     = os.environ.get("CDT_TASK_NAME", "unknown")
commit   = os.environ.get("CDT_COMMIT_SHA", "unknown")
run_id   = os.environ.get("CDT_PIPELINE_RUN_ID", "unknown")
props    = json.loads(os.environ.get("CDT_PROPS", "{}"))

print("━" * 48)
print(f"  Pipeline : {pipeline}")
print(f"  Stage    : {stage}  |  Task: {task}")
print(f"  Commit   : {commit}")
print("━" * 48)
print()

print("==> [generate-sbom] Generating SPDX Software Bill of Materials")
print()

packages = [
    ("flask",           "3.0.3",  "MIT"),
    ("sqlalchemy",      "2.0.30", "MIT"),
    ("flask-sqlalchemy","3.1.1",  "BSD-3-Clause"),
    ("pyjwt",           "2.8.0",  "MIT"),
    ("bcrypt",          "4.1.3",  "Apache-2.0"),
    ("gunicorn",        "22.0.0", "MIT"),
    ("cryptography",    "42.0.7", "Apache-2.0 OR BSD-3-Clause"),
    ("alembic",         "1.13.1", "MIT"),
    ("ruff",            "0.4.4",  "MIT"),
    ("pytest",          "8.2.0",  "MIT"),
]

print(f"  {'Package':<25} {'Version':<12} {'License'}")
print("  " + "-" * 52)
for name, ver, lic in packages:
    print(f"  {name:<25} {ver:<12} {lic}")
print()

sbom = {
    "spdxVersion": "SPDX-2.3",
    "name": f"{pipeline}-{commit[:7]}",
    "documentNamespace": f"https://acme.internal/sbom/{run_id}",
    "packages": [{"name": n, "version": v, "licenseConcluded": l} for n, v, l in packages],
}
out_path = f"sbom-{commit[:7]}.spdx.json"
print(f"  Written: {out_path}  ({len(packages)} packages)")
print()
print(f"✓ SBOM generated  run_id={run_id}")
""",
}

# ── Pipeline / Stage / Task definitions ──────────────────────────────────────

# (task_name, language, script_key, on_error, task_type)
STAGE_DEFS = [
    {
        "name": "checkout",
        "order": 1,
        "tasks": [("clone-repo", "bash", "checkout", "fail", "build")],
    },
    {
        "name": "validate",
        "order": 2,
        "tasks": [
            ("lint", "bash", "lint", "fail", "lint"),
            ("validate-k8s", "python", "validate_manifest", "warn", "build"),
        ],
    },
    {
        "name": "test",
        "order": 3,
        "tasks": [
            ("unit-tests", "bash", "unit_test", "fail", "unit-test"),
            ("collect-metrics", "python", "collect_metrics", "warn", "code-coverage"),
            ("integration-tests", "python", "integration_test", "fail", "integration-test"),
        ],
    },
    {
        "name": "security",
        "order": 4,
        "tasks": [
            ("security-scan", "python", "security_scan", "warn", "sast"),
            ("generate-sbom", "python", "generate_sbom", "warn", "sca"),
        ],
    },
    {
        "name": "publish",
        "order": 5,
        "tasks": [
            ("build-image", "bash", "build_image", "fail", "container-scan"),
            ("tag-release", "bash", "tag_release", "warn", "release"),
            ("notify", "bash", "notify", "warn", "notify"),
        ],
    },
]

# (pipeline_name, kind, app_key)
PIPELINE_DEFS = [
    ("api-ci-build", "ci", "api"),
    ("api-cd-deploy", "cd", "api"),
    ("frontend-ci-build", "ci", "frontend"),
    ("frontend-cd-deploy", "cd", "frontend"),
    ("worker-ci-build", "ci", "worker"),
    ("worker-cd-deploy", "cd", "worker"),
    ("data-ci-build", "ci", "data"),
    ("data-cd-deploy", "cd", "data"),
    ("security-scan", "ci", "api"),
    ("smoke-test", "cd", "frontend"),
]


def _script(language: str, key: str) -> str:
    if language == "python":
        return PYTHON_SCRIPTS.get(key, f'print("Running {key}")\n')
    return BASH_SCRIPTS.get(key, f'echo "Running {key}"\n')


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _ago(**kwargs) -> datetime:
    return datetime.now(UTC) - timedelta(**kwargs)


# ── Main seed ─────────────────────────────────────────────────────────────────


def seed() -> None:  # noqa: C901 (intentionally long for clarity)
    app = create_app(Config)
    with app.app_context():
        # ── Product ───────────────────────────────────────────────────────────
        product = Product.query.filter_by(name="Acme Platform").first()
        if not product:
            product = Product(
                id=resource_id("prod"),
                name="Acme Platform",
                description="Core platform services for the Acme suite",
            )
            db.session.add(product)
            db.session.commit()
            print(f"Created product: {product.name} ({product.id})")
        else:
            print(f"Product already exists: {product.name}")

        # ── Environments ──────────────────────────────────────────────────────
        env_specs = [
            {
                "name": "Development",
                "env_type": EnvironmentType.DEV,
                "order": 1,
                "description": "Developer sandbox — auto-deployed on every merge to main",
            },
            {
                "name": "Staging",
                "env_type": EnvironmentType.STAGING,
                "order": 2,
                "description": "Pre-production environment for QA sign-off",
            },
            {
                "name": "Production",
                "env_type": EnvironmentType.PROD,
                "order": 3,
                "description": "Live production — requires approval gate",
            },
        ]
        envs = {}
        for spec in env_specs:
            env = Environment.query.filter_by(name=spec["name"]).first()
            if not env:
                env = Environment(id=resource_id("env"), **spec)
                db.session.add(env)
                print(f"  Created environment: {spec['name']}")
            else:
                print(f"  Environment already exists: {spec['name']}")
            envs[spec["name"]] = env
        db.session.commit()

        # Attach environments to product
        for env in envs.values():
            if env not in product.environments:
                product.environments.append(env)
        db.session.commit()

        # ── Applications ──────────────────────────────────────────────────────
        app_specs = [
            {
                "key": "api",
                "name": "API Service",
                "artifact_type": ArtifactType.CONTAINER,
                "repository_url": "https://github.com/acme/api-service",
                "build_version": "2.4.1",
                "compliance_rating": ComplianceRating.GOLD,
                "description": "Core REST API serving all platform consumers",
            },
            {
                "key": "frontend",
                "name": "Frontend App",
                "artifact_type": ArtifactType.CONTAINER,
                "repository_url": "https://github.com/acme/frontend",
                "build_version": "1.9.3",
                "compliance_rating": ComplianceRating.SILVER,
                "description": "React SPA — Nginx-hosted static bundle",
            },
            {
                "key": "worker",
                "name": "Background Worker",
                "artifact_type": ArtifactType.CONTAINER,
                "repository_url": "https://github.com/acme/worker",
                "build_version": "1.2.0",
                "compliance_rating": ComplianceRating.BRONZE,
                "description": "Celery worker for async task processing",
            },
            {
                "key": "data",
                "name": "Data Pipeline",
                "artifact_type": ArtifactType.PACKAGE,
                "repository_url": "https://github.com/acme/data-pipeline",
                "build_version": "0.8.7",
                "compliance_rating": ComplianceRating.NON_COMPLIANT,
                "description": "Apache Airflow DAGs — ETL jobs and reporting",
            },
        ]
        apps = {}
        for spec in app_specs:
            key = spec.pop("key")
            existing = ApplicationArtifact.query.filter_by(
                product_id=product.id, name=spec["name"]
            ).first()
            if not existing:
                existing = ApplicationArtifact(
                    id=resource_id("app"),
                    product_id=product.id,
                    **spec,
                )
                db.session.add(existing)
                print(f"  Created application: {spec['name']}")
            else:
                # Update new fields on existing records
                if existing.build_version is None:
                    existing.build_version = spec["build_version"]
                if (
                    existing.compliance_rating is None
                    or existing.compliance_rating == ComplianceRating.NON_COMPLIANT
                ):
                    existing.compliance_rating = spec["compliance_rating"]
                if existing.description is None:
                    existing.description = spec["description"]
                print(f"  Application already exists: {spec['name']}")
            apps[key] = existing
        db.session.commit()

        # ── Pipelines + Stages + Tasks ────────────────────────────────────────
        pipelines: dict[str, Pipeline] = {}
        for p_name, p_kind, app_key in PIPELINE_DEFS:
            pipeline = Pipeline.query.filter_by(product_id=product.id, name=p_name).first()
            if not pipeline:
                pipeline = Pipeline(
                    id=resource_id("pipe"),
                    product_id=product.id,
                    application_id=apps[app_key].id,
                    name=p_name,
                    kind=p_kind,
                    git_repo=f"https://github.com/acme/{app_key}-service.git",
                    git_branch="main",
                    compliance_score=72.5 if p_kind == "ci" else 85.0,
                    compliance_rating=ComplianceRating.SILVER
                    if p_kind == "ci"
                    else ComplianceRating.GOLD,
                )
                db.session.add(pipeline)
                db.session.flush()
                print(f"  Created pipeline: {p_name}")
            else:
                # Update application_id if it was null (from old seed run)
                if pipeline.application_id is None:
                    pipeline.application_id = apps[app_key].id
                print(f"  Pipeline already exists: {p_name}")
            pipelines[p_name] = pipeline

            for s_spec in STAGE_DEFS:
                stage = Stage.query.filter_by(pipeline_id=pipeline.id, name=s_spec["name"]).first()
                if not stage:
                    stage = Stage(
                        id=resource_id("stg"),
                        pipeline_id=pipeline.id,
                        name=s_spec["name"],
                        order=s_spec["order"],
                        run_language="bash",
                    )
                    db.session.add(stage)
                    db.session.flush()

                for t_order, t_spec in enumerate(s_spec["tasks"], start=1):
                    t_name, t_lang, t_key, t_on_err = t_spec[:4]
                    t_task_type = t_spec[4] if len(t_spec) > 4 else None
                    existing_task = Task.query.filter_by(stage_id=stage.id, name=t_name).first()
                    if not existing_task:
                        db.session.add(
                            Task(
                                id=resource_id("task"),
                                stage_id=stage.id,
                                name=t_name,
                                order=t_order,
                                run_language=t_lang,
                                run_code=_script(t_lang, t_key),
                                on_error=t_on_err,
                                timeout=300 if t_task_type not in ("sast", "sca") else 600,
                                is_required=(t_on_err == "fail"),
                                task_type=t_task_type,
                            )
                        )
                    elif existing_task.task_type is None and t_task_type:
                        existing_task.task_type = t_task_type
        db.session.commit()

        # ── Releases ──────────────────────────────────────────────────────────
        rel_specs = [
            {
                "name": "Release 1.0.0",
                "version": "1.0.0",
                "description": "Initial GA release",
                "created_by": "alice",
            },
            {
                "name": "Release 2.0.0-beta",
                "version": "2.0.0-beta",
                "description": "Beta release — new RBAC engine",
                "created_by": "bob",
            },
        ]
        releases: dict[str, Release] = {}
        for spec in rel_specs:
            rel = Release.query.filter_by(product_id=product.id, version=spec["version"]).first()
            if not rel:
                rel = Release(id=resource_id("rel"), product_id=product.id, **spec)
                db.session.add(rel)
                print(f"  Created release: {spec['version']}")
            else:
                print(f"  Release already exists: {spec['version']}")
            releases[spec["version"]] = rel
        db.session.commit()

        # ── Release Application Groups ────────────────────────────────────────
        # v1.0.0: API + Frontend (sequential), Worker (parallel)
        rel_100 = releases["1.0.0"]
        _ensure_app_group(
            rel_100,
            apps["api"],
            "sequential",
            [pipelines["api-ci-build"].id, pipelines["api-cd-deploy"].id],
            order=0,
        )
        _ensure_app_group(
            rel_100,
            apps["frontend"],
            "sequential",
            [pipelines["frontend-ci-build"].id, pipelines["frontend-cd-deploy"].id],
            order=1,
        )
        _ensure_app_group(
            rel_100,
            apps["worker"],
            "parallel",
            [pipelines["worker-ci-build"].id, pipelines["worker-cd-deploy"].id],
            order=2,
        )

        # v2.0.0-beta: all four apps
        rel_beta = releases["2.0.0-beta"]
        _ensure_app_group(
            rel_beta,
            apps["api"],
            "sequential",
            [pipelines["api-ci-build"].id, pipelines["api-cd-deploy"].id],
            order=0,
        )
        _ensure_app_group(
            rel_beta,
            apps["frontend"],
            "parallel",
            [pipelines["frontend-ci-build"].id, pipelines["frontend-cd-deploy"].id],
            order=1,
        )
        _ensure_app_group(
            rel_beta, apps["worker"], "sequential", [pipelines["worker-ci-build"].id], order=2
        )
        _ensure_app_group(
            rel_beta,
            apps["data"],
            "parallel",
            [pipelines["data-ci-build"].id, pipelines["data-cd-deploy"].id],
            order=3,
        )
        db.session.commit()

        # ── Users ─────────────────────────────────────────────────────────────
        user_specs = [
            {
                "username": "admin",
                "email": "admin@acme.example",
                "display_name": "Platform Admin",
                "persona": "Admin",
                "password": "admin123",
            },
            {
                "username": "alice",
                "email": "alice@acme.example",
                "display_name": "Alice Chen",
                "persona": "Developer",
                "password": "alice123",
            },
            {
                "username": "bob",
                "email": "bob@acme.example",
                "display_name": "Bob Smith",
                "persona": "ReadOnly",
                "password": "bob123",
            },
        ]
        users: dict[str, User] = {}
        for spec in user_specs:
            u = User.query.filter_by(username=spec["username"]).first()
            if not u:
                pw = spec.pop("password")
                u = User(
                    id=resource_id("usr"),
                    password_hash=_hash(pw),
                    is_active=True,
                    **spec,
                )
                db.session.add(u)
                print(f"  Created user: {spec['username']}")
            else:
                print(f"  User already exists: {spec['username']}")
            users[spec["username"]] = u
        db.session.commit()

        # ── Groups ────────────────────────────────────────────────────────────
        group_specs = [
            {"name": "dev-team", "description": "Product engineers and SREs"},
            {"name": "security-team", "description": "Security and compliance reviewers"},
        ]
        groups: dict[str, Group] = {}
        for spec in group_specs:
            g = Group.query.filter_by(name=spec["name"]).first()
            if not g:
                g = Group(id=resource_id("grp"), **spec)
                db.session.add(g)
                print(f"  Created group: {spec['name']}")
            else:
                print(f"  Group already exists: {spec['name']}")
            groups[spec["name"]] = g
        db.session.commit()

        # Memberships
        dev_team = groups["dev-team"]
        if users["alice"] not in dev_team.users:
            dev_team.users.append(users["alice"])
        if users["bob"] not in dev_team.users:
            dev_team.users.append(users["bob"])
        sec_team = groups["security-team"]
        if users["admin"] not in sec_team.users:
            sec_team.users.append(users["admin"])
        db.session.commit()

        # ── Roles ─────────────────────────────────────────────────────────────
        role_specs = [
            {
                "name": "platform-admin",
                "permissions": "products:write,pipelines:write,releases:write,users:write,compliance:write",
                "description": "Full platform administration",
            },
            {
                "name": "developer",
                "permissions": "products:read,pipelines:write,releases:read,pipelines:run",
                "description": "Create and run pipelines; read releases",
            },
            {
                "name": "reader",
                "permissions": "products:read,pipelines:read,releases:read",
                "description": "Read-only access to all resources",
            },
        ]
        roles: dict[str, Role] = {}
        for spec in role_specs:
            r = Role.query.filter_by(name=spec["name"]).first()
            if not r:
                r = Role(id=resource_id("role"), **spec)
                db.session.add(r)
                print(f"  Created role: {spec['name']}")
            else:
                print(f"  Role already exists: {spec['name']}")
            roles[spec["name"]] = r
        db.session.commit()

        # ── RoleBindings ──────────────────────────────────────────────────────
        _ensure_binding(users["admin"], None, roles["platform-admin"], "organization")
        _ensure_binding(users["alice"], None, roles["developer"], f"product:{product.id}")
        _ensure_binding(None, groups["dev-team"], roles["developer"], f"product:{product.id}")
        _ensure_binding(None, groups["security-team"], roles["reader"], "organization")
        db.session.commit()

        # ── Compliance Rules ──────────────────────────────────────────────────
        rule_specs = [
            {
                "scope": "organization",
                "description": "All pipelines must achieve Silver or above before release",
                "min_rating": ComplianceRating.SILVER,
            },
            {
                "scope": f"product:{product.id}",
                "description": "Acme Platform pipelines require Gold rating for production deploys",
                "min_rating": ComplianceRating.GOLD,
            },
            {
                "scope": "environment:Production",
                "description": "Production gate: Platinum compliance required",
                "min_rating": ComplianceRating.PLATINUM,
            },
        ]
        for spec in rule_specs:
            if not ComplianceRule.query.filter_by(
                scope=spec["scope"], min_rating=spec["min_rating"]
            ).first():
                db.session.add(ComplianceRule(id=resource_id("crule"), is_active=True, **spec))
                print(f"  Created compliance rule: {spec['scope']} -> {spec['min_rating']}")
        db.session.commit()

        # ── Audit Events ──────────────────────────────────────────────────────
        audit_specs = [
            {
                "event_type": "release.created",
                "actor": "alice",
                "resource_type": "release",
                "resource_id": rel_100.id,
                "action": "create",
                "decision": "allow",
                "detail": json.dumps({"version": "1.0.0"}),
                "timestamp": _ago(days=14),
            },
            {
                "event_type": "pipeline.run.started",
                "actor": "alice",
                "resource_type": "pipeline",
                "resource_id": pipelines["api-ci-build"].id,
                "action": "run",
                "decision": "allow",
                "detail": json.dumps({"commit_sha": "a1b2c3d"}),
                "timestamp": _ago(hours=2),
            },
            {
                "event_type": "gate.admission.denied",
                "actor": "system",
                "resource_type": "pipeline",
                "resource_id": pipelines["data-cd-deploy"].id,
                "action": "attach",
                "decision": "deny",
                "detail": json.dumps({"reason": "compliance_rating below minimum"}),
                "timestamp": _ago(hours=1),
            },
            {
                "event_type": "user.login",
                "actor": "admin",
                "resource_type": "user",
                "resource_id": users["admin"].id,
                "action": "login",
                "decision": "allow",
                "detail": json.dumps({"ip": "10.0.0.1"}),
                "timestamp": _ago(minutes=30),
            },
        ]
        if AuditEvent.query.count() < len(audit_specs):
            for spec in audit_specs:
                db.session.add(AuditEvent(id=resource_id("aev"), **spec))
            print(f"  Created {len(audit_specs)} audit events")
        else:
            print("  Audit events already seeded")
        db.session.commit()

        # ── Vault Secrets ─────────────────────────────────────────────────────
        secret_specs = [
            {
                "name": "DATABASE_URL",
                "description": "Primary PostgreSQL connection string",
                "value": "postgresql+psycopg2://app:s3cr3t@db.acme.internal/platform",
                "allowed_users": "*",
                "created_by": "admin",
            },
            {
                "name": "SLACK_WEBHOOK_URL",
                "description": "Slack incoming webhook for CI notifications",
                "value": "https://hooks.slack.example/services/T00/B00/XXXXXXXXXXX",
                "allowed_users": "admin,alice",
                "created_by": "alice",
            },
            {
                "name": "REGISTRY_TOKEN",
                "description": "Container registry push token",
                "value": "ghp_XXXXXXXXXXXXXXXXXX",
                "allowed_users": "admin",
                "created_by": "admin",
            },
        ]
        for spec in secret_specs:
            if not VaultSecret.query.filter_by(name=spec["name"]).first():
                value = spec.pop("value")
                db.session.add(
                    VaultSecret(
                        id=resource_id("vsec"),
                        ciphertext=encrypt(value),
                        **spec,
                    )
                )
                print(f"  Created vault secret: {spec['name']}")
            else:
                print(f"  Vault secret already exists: {spec['name']}")
        db.session.commit()

        # ── Agent Pools ───────────────────────────────────────────────────────
        pool_specs = [
            {
                "name": "default",
                "description": "Shared pool for all standard tasks",
                "pool_type": "builtin",
                "cpu_limit": "500m",
                "memory_limit": "512Mi",
                "max_agents": 10,
                "sandbox_network": False,
            },
            {
                "name": "heavy-builds",
                "description": "High-resource pool for container image builds",
                "pool_type": "custom",
                "cpu_limit": "2000m",
                "memory_limit": "4Gi",
                "max_agents": 3,
                "sandbox_network": True,
            },
            {
                "name": "secure-scan",
                "description": "Air-gapped pool for security scanning",
                "pool_type": "custom",
                "cpu_limit": "1000m",
                "memory_limit": "2Gi",
                "max_agents": 2,
                "sandbox_network": False,
            },
        ]
        for spec in pool_specs:
            if not AgentPool.query.filter_by(name=spec["name"]).first():
                db.session.add(AgentPool(id=resource_id("pool"), is_active=True, **spec))
                print(f"  Created agent pool: {spec['name']}")
            else:
                print(f"  Agent pool already exists: {spec['name']}")
        db.session.commit()

        # ── Plugins ───────────────────────────────────────────────────────────
        plugin_specs = [
            {
                "name": "github-integration",
                "display_name": "GitHub",
                "description": "Trigger pipelines from GitHub webhooks and report commit statuses",
                "version": "1.2.0",
                "plugin_type": "integration",
                "category": "scm",
                "icon": "🐙",
                "is_builtin": True,
                "author": "Acme Platform Team",
                "config_schema": json.dumps(
                    {
                        "properties": {
                            "base_url": {"type": "string", "title": "GitHub API Base URL"},
                            "token": {
                                "type": "string",
                                "title": "Personal Access Token",
                                "secret": True,
                            },
                        }
                    }
                ),
                "configs": [
                    {
                        "config_name": "acme-github",
                        "tool_url": "https://api.github.com",
                        "credentials": json.dumps({"token": "ghp_PLACEHOLDER"}),
                        "extra_config": json.dumps({"org": "acme"}),
                    },
                ],
            },
            {
                "name": "slack-notifications",
                "display_name": "Slack",
                "description": "Post pipeline status updates to Slack channels",
                "version": "2.0.1",
                "plugin_type": "integration",
                "category": "notification",
                "icon": "💬",
                "is_builtin": True,
                "author": "Acme Platform Team",
                "config_schema": json.dumps(
                    {
                        "properties": {
                            "webhook_url": {
                                "type": "string",
                                "title": "Incoming Webhook URL",
                                "secret": True,
                            },
                            "channel": {"type": "string", "title": "Default Channel"},
                        }
                    }
                ),
                "configs": [
                    {
                        "config_name": "ci-alerts",
                        "tool_url": "https://slack.com",
                        "credentials": json.dumps(
                            {"webhook_url": "https://hooks.slack.example/T/B/xxx"}
                        ),
                        "extra_config": json.dumps({"channel": "#ci-alerts"}),
                    },
                ],
            },
            {
                "name": "jira-integration",
                "display_name": "Jira",
                "description": "Link pipeline runs to Jira issues and update status automatically",
                "version": "1.0.5",
                "plugin_type": "integration",
                "category": "issue-tracker",
                "icon": "🎫",
                "is_builtin": False,
                "author": "Acme DevOps Guild",
                "config_schema": json.dumps(
                    {
                        "properties": {
                            "base_url": {"type": "string", "title": "Jira Base URL"},
                            "email": {"type": "string", "title": "Service Account Email"},
                            "api_token": {"type": "string", "title": "API Token", "secret": True},
                        }
                    }
                ),
                "configs": [
                    {
                        "config_name": "acme-jira",
                        "tool_url": "https://acme.atlassian.net",
                        "credentials": json.dumps(
                            {"email": "svc@acme.example", "api_token": "PLACEHOLDER"}
                        ),
                        "extra_config": json.dumps({"project_key": "PLAT"}),
                    },
                ],
            },
        ]
        plugin_objs: dict[str, Plugin] = {}
        for spec in plugin_specs:
            config_defs = spec.pop("configs", [])
            plug = Plugin.query.filter_by(name=spec["name"]).first()
            if not plug:
                plug = Plugin(id=resource_id("plug"), is_enabled=True, **spec)
                db.session.add(plug)
                db.session.flush()
                print(f"  Created plugin: {spec['name']}")
            else:
                print(f"  Plugin already exists: {spec['name']}")
            plugin_objs[spec["name"]] = plug

            for cfg in config_defs:
                if not PluginConfig.query.filter_by(
                    plugin_id=plug.id, config_name=cfg["config_name"]
                ).first():
                    db.session.add(
                        PluginConfig(
                            id=resource_id("pcfg"),
                            plugin_id=plug.id,
                            is_active=True,
                            **cfg,
                        )
                    )
        db.session.commit()

        # ── Webhooks ──────────────────────────────────────────────────────────
        wh_specs = [
            {
                "name": "GitHub Push - API CI",
                "pipeline_id": pipelines["api-ci-build"].id,
                "description": "Trigger API CI on every push to main",
                "created_by": "alice",
                "is_active": True,
            },
            {
                "name": "GitHub Push - Frontend CI",
                "pipeline_id": pipelines["frontend-ci-build"].id,
                "description": "Trigger Frontend CI pipeline from GitHub",
                "created_by": "alice",
                "is_active": True,
            },
        ]
        for spec in wh_specs:
            if not Webhook.query.filter_by(name=spec["name"]).first():
                db.session.add(
                    Webhook(
                        id=resource_id("wh"),
                        token=secrets.token_hex(32),
                        **spec,
                    )
                )
                print(f"  Created webhook: {spec['name']}")
            else:
                print(f"  Webhook already exists: {spec['name']}")
        db.session.commit()

        # ── Stage accent colors ───────────────────────────────────────────────
        STAGE_COLORS = {
            "checkout": "#3b82f6",   # blue
            "validate": "#8b5cf6",   # violet
            "test":     "#10b981",   # emerald
            "security": "#ef4444",   # rose
            "publish":  "#f59e0b",   # amber
        }
        for pipeline in pipelines.values():
            for stage in pipeline.stages:
                if stage.accent_color is None and stage.name in STAGE_COLORS:
                    stage.accent_color = STAGE_COLORS[stage.name]
        db.session.commit()
        print("  Applied stage accent colors")

        # ── Design-time Properties ────────────────────────────────────────────
        from app.services.property_service import set_property
        prop_specs = [
            # Pipeline-level
            ("pipeline", pipelines["api-ci-build"].id,  "IMAGE_REPO",    "registry.acme.internal/api",  "string",  "Container image repository"),
            ("pipeline", pipelines["api-ci-build"].id,  "BUILD_NUMBER",  None,                          "string",  "Injected by CI trigger"),
            ("pipeline", pipelines["api-ci-build"].id,  "COVERAGE_MIN",  "80",                          "number",  "Minimum test coverage %"),
            ("pipeline", pipelines["api-cd-deploy"].id, "NAMESPACE",     "acme-prod",                   "string",  "Target k8s namespace"),
            ("pipeline", pipelines["api-cd-deploy"].id, "REPLICAS",      "3",                           "number",  "Desired pod replicas"),
            ("pipeline", pipelines["api-cd-deploy"].id, "DB_MIGRATE",    "true",                        "boolean", "Run db migrations on deploy"),
            ("pipeline", pipelines["frontend-ci-build"].id, "NODE_ENV",  "production",                  "string",  "Node environment"),
            ("pipeline", pipelines["frontend-ci-build"].id, "SENTRY_DSN", None,                         "secret",  "Sentry error reporting DSN"),
            # Stage-level overrides
            ("stage", _stage_id(pipelines["api-ci-build"], "test"),     "COVERAGE_MIN", "85",    "number", "Stricter minimum for test stage"),
            ("stage", _stage_id(pipelines["api-ci-build"], "security"), "FAIL_ON_HIGH", "true",  "boolean","Fail pipeline on HIGH findings"),
            ("stage", _stage_id(pipelines["api-cd-deploy"], "publish"),  "SLACK_CHANNEL", "#deploys", "string", "Notification channel"),
        ]
        for owner_type, owner_id, name, value, vtype, desc in prop_specs:
            if owner_id and not __import__("app.models.property", fromlist=["Property"]).Property.query.filter_by(
                owner_type=owner_type, owner_id=owner_id, name=name
            ).first():
                set_property(owner_type, owner_id, name, value, value_type=vtype, description=desc)
        print("  Applied design-time properties")

        # ── Pipeline Runs (historical) ────────────────────────────────────────
        for pl_name in [
            "api-ci-build", "api-cd-deploy",
            "frontend-ci-build", "frontend-cd-deploy",
            "worker-ci-build", "security-scan",
        ]:
            _seed_pipeline_runs(pipelines[pl_name])

        # ── Release Runs ──────────────────────────────────────────────────────
        _seed_release_run(rel_100)
        _seed_release_run(rel_beta)

        # ── Extra users ───────────────────────────────────────────────────────
        extra_users = [
            ("carol",   "carol@acme.example",   "Carol Wu",       "Developer",  "carol123"),
            ("dave",    "dave@acme.example",     "Dave Okafor",    "ReadOnly",   "dave123"),
            ("eve",     "eve@acme.example",      "Eve Nakamura",   "Developer",  "eve123"),
            ("frank",   "frank@acme.example",    "Frank Torres",   "Admin",      "frank123"),
            ("grace",   "grace@acme.example",    "Grace Patel",    "ReadOnly",   "grace123"),
        ]
        for uname, email, display, persona, pw in extra_users:
            if not User.query.filter_by(username=uname).first():
                db.session.add(User(
                    id=resource_id("usr"),
                    username=uname, email=email, display_name=display,
                    persona=persona, password_hash=_hash(pw), is_active=True,
                ))
                print(f"  Created user: {uname}")
        db.session.commit()

        # ── Extra audit events ────────────────────────────────────────────────
        extra_audit = [
            ("pipeline.run.succeeded", "bob",    "pipeline", pipelines["api-ci-build"].id,   "run",    "allow", {"commit_sha": "b7c8d9e", "duration_s": 247}, _ago(hours=3)),
            ("pipeline.run.failed",    "alice",  "pipeline", pipelines["data-ci-build"].id,  "run",    "allow", {"commit_sha": "c3d4e5f", "stage": "test"},   _ago(hours=5)),
            ("release.run.started",    "alice",  "release",  rel_100.id,                     "run",    "allow", {"version": "1.0.0"},                         _ago(days=1)),
            ("vault.secret.read",      "carol",  "secret",   "DATABASE_URL",                 "read",   "allow", {"reason": "pipeline inject"},                _ago(minutes=15)),
            ("user.login",             "carol",  "user",     "carol",                        "login",  "allow", {"ip": "10.0.1.5"},                           _ago(minutes=45)),
            ("gate.admission.denied",  "system", "pipeline", pipelines["data-cd-deploy"].id,  "attach", "deny",  {"reason": "Non-Compliant rating"},          _ago(hours=1, minutes=30)),
            ("compliance.rule.updated","admin",  "rule",     "organization",                 "update", "allow", {"min_rating": "Gold"},                       _ago(days=2)),
            ("pipeline.run.warning",   "bob",    "pipeline", pipelines["worker-ci-build"].id, "run",   "allow", {"commit_sha": "f6a7b8c"},                    _ago(hours=7)),
        ]
        existing_count = AuditEvent.query.count()
        if existing_count < 12:
            for etype, actor, rtype, rid, action, decision, detail, ts in extra_audit:
                db.session.add(AuditEvent(
                    id=resource_id("aev"),
                    event_type=etype, actor=actor,
                    resource_type=rtype, resource_id=rid,
                    action=action, decision=decision,
                    detail=json.dumps(detail), timestamp=ts,
                ))
            db.session.commit()
            print(f"  Created {len(extra_audit)} extra audit events")

        # ── Extra vault secrets ───────────────────────────────────────────────
        extra_secrets = [
            ("NPM_AUTH_TOKEN",    "npm registry auth token for private packages",   "npm_XXXXXXXXXXXX", "admin,carol"),
            ("SONAR_TOKEN",       "SonarQube analysis token",                        "sqp_XXXXXXXXXXXX", "admin,alice,carol"),
            ("AWS_SECRET_KEY",    "AWS IAM secret for S3 artifact storage",          "wJaXXXXXXXXXXXX", "admin"),
            ("POSTGRES_PASSWORD", "RDS PostgreSQL master password",                  "s3cur3P@ss!",      "admin"),
        ]
        for name, desc, value, allowed in extra_secrets:
            if not VaultSecret.query.filter_by(name=name).first():
                db.session.add(VaultSecret(
                    id=resource_id("vsec"),
                    name=name, description=desc,
                    ciphertext=encrypt(value),
                    allowed_users=allowed, created_by="admin",
                ))
                print(f"  Created vault secret: {name}")
        db.session.commit()

        db.session.commit()
        print("\nSeed complete.")
        _print_summary(product.id)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _stage_id(pipeline: Pipeline, stage_name: str) -> str | None:
    """Return the stage ID matching stage_name in pipeline, or None."""
    for s in pipeline.stages:
        if s.name == stage_name:
            return s.id
    return None


def _ensure_app_group(
    release: Release,
    application: ApplicationArtifact,
    execution_mode: str,
    pipeline_ids: list[str],
    order: int,
) -> None:
    existing = ReleaseApplicationGroup.query.filter_by(
        release_id=release.id, application_id=application.id
    ).first()
    if not existing:
        db.session.add(
            ReleaseApplicationGroup(
                id=resource_id("rag"),
                release_id=release.id,
                application_id=application.id,
                execution_mode=execution_mode,
                pipeline_ids=json.dumps(pipeline_ids),
                order=order,
            )
        )
        print(f"    Added app group: {application.name} -> {release.name} ({execution_mode})")


def _ensure_binding(
    user: User | None,
    group: Group | None,
    role: Role,
    scope: str,
) -> None:
    uid = user.id if user else None
    gid = group.id if group else None
    if not RoleBinding.query.filter_by(
        user_id=uid, group_id=gid, role_id=role.id, scope=scope
    ).first():
        db.session.add(
            RoleBinding(
                id=resource_id("rb"),
                role_id=role.id,
                user_id=uid,
                group_id=gid,
                scope=scope,
            )
        )
        who = f"user:{user.username}" if user else f"group:{group.name}"
        print(f"  Created binding: {who} -> {role.name} @ {scope}")


def _seed_pipeline_runs(pipeline: Pipeline) -> None:
    """Create 6 historical pipeline runs with varied statuses and realistic logs."""
    runs_count = PipelineRun.query.filter_by(pipeline_id=pipeline.id).count()
    if runs_count >= 6:
        print(f"  Pipeline runs already exist for: {pipeline.name}")
        return

    TASK_LOGS = {
        "Succeeded": (
            "==> Starting task\n"
            "  Pulling dependencies...\n"
            "  Running checks...\n"
            "  All checks passed ✓\n"
            "==> Task completed successfully\n"
        ),
        "Failed": (
            "==> Starting task\n"
            "  Pulling dependencies...\n"
            "  Running checks...\n"
            "  ERROR: Assertion failed at line 42\n"
            "  FAIL: 3 tests failed, 17 passed\n"
            "==> Task failed with exit code 1\n"
        ),
        "Warning": (
            "==> Starting task\n"
            "  Running analysis...\n"
            "  WARNING: 2 medium-severity findings\n"
            "  Continuing (on_error=warn)\n"
            "==> Task completed with warnings\n"
        ),
        "Cancelled": "==> Task cancelled (upstream failure)\n",
    }

    run_specs = [
        ("a1b2c3d", "Succeeded", "alice",  _ago(days=7),          timedelta(minutes=47), None),
        ("d4e5f6a", "Failed",    "alice",  _ago(days=5),          timedelta(minutes=12), 2),
        ("b7c8d9e", "Succeeded", "carol",  _ago(days=4),          timedelta(minutes=52), None),
        ("c3d4e5f", "Warning",   "bob",    _ago(days=2),          timedelta(minutes=44), None),
        ("e5f6a7b", "Failed",    "carol",  _ago(days=1),          timedelta(minutes=18), 3),
        ("f6a7b8c", "Succeeded", "alice",  _ago(hours=3),         timedelta(minutes=51), None),
    ]

    stages = sorted(pipeline.stages, key=lambda s: s.order)
    for commit, run_status, triggered_by, started, duration, fail_at_stage in run_specs:
        if PipelineRun.query.filter_by(pipeline_id=pipeline.id, commit_sha=commit).first():
            continue
        run = PipelineRun(
            id=pipeline_run_id(),
            pipeline_id=pipeline.id,
            commit_sha=commit,
            status=run_status,
            triggered_by=triggered_by,
            started_at=started,
            finished_at=started + duration,
            compliance_rating=pipeline.compliance_rating,
            compliance_score=pipeline.compliance_score,
            runtime_properties="{}",
        )
        db.session.add(run)
        db.session.flush()

        for i, stage in enumerate(stages):
            if fail_at_stage is not None and i > fail_at_stage:
                sr_status = "Cancelled"
            elif fail_at_stage is not None and i == fail_at_stage:
                sr_status = "Failed"
            elif run_status == "Warning" and i == len(stages) - 1:
                sr_status = "Warning"
            else:
                sr_status = "Succeeded"

            sr = StageRun(
                id=resource_id("srun"),
                pipeline_run_id=run.id,
                stage_id=stage.id,
                status=sr_status,
                started_at=started + timedelta(minutes=i * 8),
                finished_at=started + timedelta(minutes=i * 8 + 7),
                runtime_properties="{}",
            )
            db.session.add(sr)
            db.session.flush()

            tasks = sorted(stage.tasks, key=lambda t: t.order)
            for j, task in enumerate(tasks):
                if sr_status == "Cancelled":
                    tr_status = "Cancelled"
                elif sr_status == "Failed":
                    tr_status = "Failed" if j == 0 else "Cancelled"
                elif sr_status == "Warning" and j == len(tasks) - 1:
                    tr_status = "Warning"
                else:
                    tr_status = "Succeeded"

                db.session.add(TaskRun(
                    id=resource_id("trun"),
                    task_id=task.id,
                    stage_run_id=sr.id,
                    status=tr_status,
                    return_code=0 if tr_status in ("Succeeded", "Warning") else (1 if tr_status == "Failed" else None),
                    logs=TASK_LOGS.get(tr_status, ""),
                    started_at=sr.started_at + timedelta(seconds=j * 90),
                    finished_at=sr.started_at + timedelta(seconds=j * 90 + 85),
                ))
    db.session.flush()
    print(f"  Created pipeline runs for: {pipeline.name}")


def _seed_release_run(release: Release) -> None:
    runs_count = ReleaseRun.query.filter_by(release_id=release.id).count()
    if runs_count >= 1:
        print(f"  Release run already exists for: {release.name}")
        return
    rrun = ReleaseRun(
        id=release_run_id(),
        release_id=release.id,
        status="Succeeded",
        triggered_by="alice",
        compliance_rating=ComplianceRating.GOLD,
        compliance_score=85.0,
        started_at=_ago(days=1),
        finished_at=_ago(days=1) + timedelta(hours=2),
    )
    db.session.add(rrun)
    db.session.flush()
    print(f"  Created release run for: {release.name}")


def _print_summary(product_id: str) -> None:
    from app.models.auth import User as _User

    pipelines = Pipeline.query.filter_by(product_id=product_id).all()
    releases = Release.query.filter_by(product_id=product_id).all()
    total_stages = sum(Stage.query.filter_by(pipeline_id=p.id).count() for p in pipelines)
    total_tasks = sum(
        Task.query.filter_by(stage_id=s.id).count()
        for p in pipelines
        for s in Stage.query.filter_by(pipeline_id=p.id).all()
    )
    print("\nSummary:")
    print(f"  Users          : {_User.query.count()}")
    print(f"  Groups         : {Group.query.count()}")
    print(f"  Roles          : {Role.query.count()}")
    print(f"  Environments   : {Environment.query.count()}")
    print(
        f"  Applications   : {ApplicationArtifact.query.filter_by(product_id=product_id).count()}"
    )
    print(f"  Releases       : {len(releases)}")
    print(f"  Pipelines      : {len(pipelines)}")
    print(f"  Stages         : {total_stages}")
    print(f"  Tasks          : {total_tasks}")
    print(f"  Pipeline Runs  : {PipelineRun.query.count()}")
    print(f"  Compliance Rules: {ComplianceRule.query.count()}")
    print(f"  Vault Secrets  : {VaultSecret.query.count()}")
    print(f"  Webhooks       : {Webhook.query.count()}")
    print(f"  Agent Pools    : {AgentPool.query.count()}")
    print(f"  Plugins        : {Plugin.query.count()}")


if __name__ == "__main__":
    seed()
