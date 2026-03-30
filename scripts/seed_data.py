"""Seed script — creates realistic test data in the running app's database.

Run from the repo root (with venv activated):
    python scripts/seed_data.py

Creates:
  - 1 Product ("Acme Platform")
  - 2 Releases  (v1.0.0, v2.0.0-beta)
  - 10 Pipelines (ci-build, lint-check, unit-test, integration-test,
                  security-scan, build-image, deploy-dev, deploy-staging,
                  smoke-test, deploy-prod)
  - 5 Stages per pipeline  (each with 2-3 Tasks containing real bash/python scripts)

The script is idempotent — re-running will skip objects that already exist.
"""

from __future__ import annotations

import os
import sys

# Make sure the repo root is on the path when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.pipeline import Pipeline, Stage  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.release import Release  # noqa: E402
from app.models.task import Task  # noqa: E402
from app.services.id_service import resource_id  # noqa: E402

# ── Script templates ──────────────────────────────────────────────────────────

BASH_SCRIPTS = {
    "checkout": """\
#!/usr/bin/env bash
set -euo pipefail
echo "==> Checking out source"
git clone --depth 1 "$GIT_REPO" /workspace/src || true
cd /workspace/src
echo "HEAD: $(git rev-parse --short HEAD 2>/dev/null || echo 'n/a')"
echo "Branch: $(git branch --show-current 2>/dev/null || echo 'detached')"
echo "==> Checkout complete"
""",
    "lint": """\
#!/usr/bin/env bash
set -euo pipefail
echo "==> Running linter"
cd /workspace/src
ruff check . --output-format=github
echo "==> Lint passed"
""",
    "unit_test": """\
#!/usr/bin/env bash
set -euo pipefail
echo "==> Running unit tests"
cd /workspace/src
pytest tests/unit -v --tb=short 2>&1
echo "==> Unit tests passed"
""",
    "build_image": """\
#!/usr/bin/env bash
set -euo pipefail
echo "==> Building container image"
IMAGE_TAG="${IMAGE_REPO}:${BUILD_NUMBER:-latest}"
podman build -t "$IMAGE_TAG" .
echo "Built: $IMAGE_TAG"
podman push "$IMAGE_TAG"
echo "==> Image pushed"
""",
    "deploy": """\
#!/usr/bin/env bash
set -euo pipefail
NAMESPACE="${NAMESPACE:-release-wizard-dev}"
echo "==> Deploying to namespace: $NAMESPACE"
kubectl set image deployment/app app="${IMAGE_REPO}:${IMAGE_TAG}" -n "$NAMESPACE"
kubectl rollout status deployment/app -n "$NAMESPACE" --timeout=120s
echo "==> Deploy complete"
""",
    "smoke_test": """\
#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${APP_URL:-http://app.release-wizard-dev.svc}"
echo "==> Smoke tests against $BASE_URL"
curl -sf "$BASE_URL/healthz" | grep -q '"status":"ok"'
echo "  /healthz OK"
curl -sf "$BASE_URL/readyz"  | grep -q '"status":"ok"'
echo "  /readyz  OK"
echo "==> Smoke tests passed"
""",
    "cleanup": """\
#!/usr/bin/env bash
set -euo pipefail
echo "==> Cleaning workspace"
rm -rf /workspace/src /workspace/artifacts
echo "Disk after cleanup: $(df -h /workspace | tail -1)"
echo "==> Done"
""",
    "tag_release": """\
#!/usr/bin/env bash
set -euo pipefail
TAG="${RELEASE_VERSION:-$(date +%Y%m%d%H%M%S)}"
echo "==> Tagging release $TAG"
git tag -a "v$TAG" -m "Release $TAG [skip ci]"
git push origin "v$TAG"
echo "==> Tag pushed"
""",
    "notify": """\
#!/usr/bin/env bash
set -euo pipefail
echo "==> Sending Slack notification"
STATUS="${PIPELINE_STATUS:-success}"
curl -sf -X POST "$SLACK_WEBHOOK" \
  -H 'Content-Type: application/json' \
  -d "{\"text\":\"Pipeline *${PIPELINE_NAME}* finished with status *${STATUS}*\"}"
echo "==> Notification sent"
""",
}

PYTHON_SCRIPTS = {
    "collect_metrics": """\
#!/usr/bin/env python3
\"\"\"Collect test coverage metrics and write a summary JSON.\"\"\"
import json, pathlib, subprocess, sys

result = subprocess.run(
    ["pytest", "tests/unit", "--cov=app", "--cov-report=json", "-q"],
    capture_output=True, text=True,
)
print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)

cov_file = pathlib.Path("coverage.json")
if cov_file.exists():
    data = json.loads(cov_file.read_text())
    pct = data.get("totals", {}).get("percent_covered", 0)
    print(f"Coverage: {pct:.1f}%")
    if pct < 60:
        print("ERROR: coverage below 60%", file=sys.stderr)
        sys.exit(1)
else:
    print("No coverage report generated")
""",
    "security_scan": """\
#!/usr/bin/env python3
\"\"\"Run bandit security scan and fail on HIGH severity findings.\"\"\"
import subprocess, sys, json

result = subprocess.run(
    ["bandit", "-r", "app/", "-f", "json", "-ll"],
    capture_output=True, text=True,
)
try:
    report = json.loads(result.stdout)
    metrics = report.get("metrics", {}).get("_totals", {})
    highs = metrics.get("SEVERITY.HIGH", 0)
    print(f"Bandit: HIGH={highs}, MEDIUM={metrics.get('SEVERITY.MEDIUM',0)}")
    if highs > 0:
        print("FAIL: high-severity issues found", file=sys.stderr)
        sys.exit(1)
    print("Security scan passed")
except json.JSONDecodeError:
    print(result.stdout)
    print("Scan complete (no JSON output)")
""",
    "integration_test": """\
#!/usr/bin/env python3
\"\"\"Run integration test suite against a live environment.\"\"\"
import subprocess, sys, os

env_url = os.getenv("APP_URL", "http://localhost:8080")
print(f"Running integration tests against {env_url}")

result = subprocess.run(
    ["pytest", "tests/integration", "-v", "--tb=short",
     f"--base-url={env_url}"],
    capture_output=False,
)
sys.exit(result.returncode)
""",
    "validate_manifest": """\
#!/usr/bin/env python3
\"\"\"Validate Kubernetes manifests with kubeval/kubeconform.\"\"\"
import subprocess, sys, pathlib

manifests = list(pathlib.Path("k8s").glob("*.yaml"))
print(f"Validating {len(manifests)} manifests")
for m in manifests:
    r = subprocess.run(
        ["kubeconform", "-strict", str(m)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"FAIL: {m.name}", file=sys.stderr)
        print(r.stderr, file=sys.stderr)
        sys.exit(1)
    print(f"  OK: {m.name}")
print("All manifests valid")
""",
    "generate_sbom": """\
#!/usr/bin/env python3
\"\"\"Generate Software Bill of Materials using syft.\"\"\"
import subprocess, sys, json, pathlib

result = subprocess.run(
    ["syft", ".", "-o", "spdx-json"],
    capture_output=True, text=True,
)
if result.returncode != 0:
    print(result.stderr, file=sys.stderr)
    sys.exit(result.returncode)

out = pathlib.Path("sbom.spdx.json")
out.write_text(result.stdout)
try:
    sbom = json.loads(result.stdout)
    pkg_count = len(sbom.get("packages", []))
    print(f"SBOM generated: {pkg_count} packages → {out}")
except Exception:
    print(f"SBOM written to {out}")
""",
}


# ── Seed helpers ──────────────────────────────────────────────────────────────

PIPELINE_DEFS = [
    {"name": "ci-build", "kind": "ci"},
    {"name": "lint-check", "kind": "ci"},
    {"name": "unit-test", "kind": "ci"},
    {"name": "integration-test", "kind": "ci"},
    {"name": "security-scan", "kind": "ci"},
    {"name": "build-image", "kind": "ci"},
    {"name": "deploy-dev", "kind": "cd"},
    {"name": "deploy-staging", "kind": "cd"},
    {"name": "smoke-test", "kind": "cd"},
    {"name": "deploy-prod", "kind": "cd"},
]

# Each pipeline gets 5 stages; tasks are (name, language, script_key, on_error)
STAGE_DEFS = [
    {
        "name": "checkout",
        "order": 1,
        "tasks": [
            ("clone-repo", "bash", "checkout", "fail"),
        ],
    },
    {
        "name": "validate",
        "order": 2,
        "tasks": [
            ("lint", "bash", "lint", "fail"),
            ("validate-k8s", "python", "validate_manifest", "warn"),
        ],
    },
    {
        "name": "test",
        "order": 3,
        "tasks": [
            ("unit-tests", "bash", "unit_test", "fail"),
            ("collect-metrics", "python", "collect_metrics", "warn"),
            ("integration-tests", "python", "integration_test", "fail"),
        ],
    },
    {
        "name": "security",
        "order": 4,
        "tasks": [
            ("security-scan", "python", "security_scan", "warn"),
            ("generate-sbom", "python", "generate_sbom", "warn"),
        ],
    },
    {
        "name": "publish",
        "order": 5,
        "tasks": [
            ("build-image", "bash", "build_image", "fail"),
            ("tag-release", "bash", "tag_release", "warn"),
            ("notify", "bash", "notify", "warn"),
        ],
    },
]


def _get_script(language: str, key: str) -> str:
    if language == "python":
        return PYTHON_SCRIPTS.get(key, f'print("Running {key}")\n')
    return BASH_SCRIPTS.get(key, f'echo "Running {key}"\n')


def seed() -> None:
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

        # ── Releases ─────────────────────────────────────────────────────────
        for rel_spec in [
            {"name": "Release 1.0.0", "version": "1.0.0", "description": "Initial GA release"},
            {
                "name": "Release 2.0.0-beta",
                "version": "2.0.0-beta",
                "description": "Beta release — new RBAC engine",
            },
        ]:
            if not Release.query.filter_by(
                product_id=product.id, version=rel_spec["version"]
            ).first():
                rel = Release(
                    id=resource_id("rel"),
                    product_id=product.id,
                    **rel_spec,
                )
                db.session.add(rel)
                print(f"  Created release: {rel_spec['version']}")
            else:
                print(f"  Release already exists: {rel_spec['version']}")
        db.session.commit()

        # ── Pipelines + Stages + Tasks ────────────────────────────────────────
        for p_spec in PIPELINE_DEFS:
            pipeline = Pipeline.query.filter_by(product_id=product.id, name=p_spec["name"]).first()
            if not pipeline:
                pipeline = Pipeline(
                    id=resource_id("pipe"),
                    product_id=product.id,
                    name=p_spec["name"],
                    kind=p_spec["kind"],
                    git_repo="https://github.com/acme/platform.git",
                    git_branch="main",
                )
                db.session.add(pipeline)
                db.session.flush()
                print(f"  Created pipeline: {pipeline.name}")
            else:
                print(f"  Pipeline already exists: {pipeline.name}")

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

                for t_order, (t_name, t_lang, t_key, t_on_err) in enumerate(
                    s_spec["tasks"], start=1
                ):
                    if not Task.query.filter_by(stage_id=stage.id, name=t_name).first():
                        task = Task(
                            id=resource_id("task"),
                            stage_id=stage.id,
                            name=t_name,
                            order=t_order,
                            run_language=t_lang,
                            run_code=_get_script(t_lang, t_key),
                            on_error=t_on_err,
                            timeout=300,
                            is_required=(t_on_err == "fail"),
                        )
                        db.session.add(task)

        db.session.commit()
        print("\nSeed complete.")
        _print_summary(product.id)


def _print_summary(product_id: str) -> None:
    pipelines = Pipeline.query.filter_by(product_id=product_id).all()
    releases = Release.query.filter_by(product_id=product_id).all()
    total_stages = sum(Stage.query.filter_by(pipeline_id=p.id).count() for p in pipelines)
    total_tasks = sum(
        Task.query.filter_by(stage_id=s.id).count()
        for p in pipelines
        for s in Stage.query.filter_by(pipeline_id=p.id).all()
    )
    print("\nSummary:")
    print(f"  Releases  : {len(releases)}")
    print(f"  Pipelines : {len(pipelines)}")
    print(f"  Stages    : {total_stages}")
    print(f"  Tasks     : {total_tasks}")


if __name__ == "__main__":
    seed()
