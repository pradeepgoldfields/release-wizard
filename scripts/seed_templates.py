"""Seed sample pipeline templates into the database.

Run from repo root:
    python scripts/seed_templates.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.pipeline_template import PipelineTemplate
from app.services.id_service import resource_id

TEMPLATES = [
    {
        "name": "Standard CI Pipeline",
        "description": "A standard CI pipeline with linting, unit tests, code coverage, SAST and image build.",
        "kind": "ci",
        "category": "General",
        "tags": "ci, test, sast, build",
        "stages": [
            {
                "name": "Code Quality",
                "order": 0,
                "tasks": [
                    {
                        "name": "Lint",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "lint",
                        "run_code": "ruff check . && ruff format --check .",
                        "on_error": "fail",
                        "timeout": 120,
                        "is_required": True,
                    },
                    {
                        "name": "Unit Tests",
                        "order": 1,
                        "run_language": "bash",
                        "task_type": "unit-test",
                        "run_code": "pytest tests/unit --cov=. --cov-report=term-missing",
                        "on_error": "fail",
                        "timeout": 300,
                        "is_required": True,
                    },
                    {
                        "name": "Code Coverage Gate",
                        "order": 2,
                        "run_language": "bash",
                        "task_type": "code-coverage",
                        "run_code": "pytest --cov=. --cov-fail-under=70",
                        "on_error": "warn",
                        "timeout": 300,
                        "is_required": False,
                    },
                ],
            },
            {
                "name": "Security Scan",
                "order": 1,
                "tasks": [
                    {
                        "name": "SAST Scan",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "sast",
                        "run_code": "bandit -r app/ -ll || true",
                        "on_error": "warn",
                        "timeout": 180,
                        "is_required": False,
                    },
                    {
                        "name": "Secret Scan",
                        "order": 1,
                        "run_language": "bash",
                        "task_type": "secret-scan",
                        "run_code": "gitleaks detect --source . --verbose || true",
                        "on_error": "warn",
                        "timeout": 120,
                        "is_required": False,
                    },
                ],
            },
            {
                "name": "Build",
                "order": 2,
                "tasks": [
                    {
                        "name": "Build Image",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "build",
                        "run_code": "docker build -t $IMAGE_NAME:$BUILD_TAG .",
                        "on_error": "fail",
                        "timeout": 600,
                        "is_required": True,
                    },
                ],
            },
        ],
    },
    {
        "name": "Secure DevSecOps CI",
        "description": "Full DevSecOps CI pipeline with SAST, SCA, secret scanning, container scanning and SBOM generation.",
        "kind": "ci",
        "category": "Security",
        "tags": "ci, sast, sca, secret-scan, container-scan, sbom, devsecops",
        "stages": [
            {
                "name": "Static Analysis",
                "order": 0,
                "tasks": [
                    {
                        "name": "SAST — Bandit",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "sast",
                        "run_code": "bandit -r . -f json -o sast-report.json || true",
                        "on_error": "warn",
                        "timeout": 300,
                        "is_required": False,
                    },
                    {
                        "name": "Secret Scan — Gitleaks",
                        "order": 1,
                        "run_language": "bash",
                        "task_type": "secret-scan",
                        "run_code": "gitleaks detect --source . --report-format json --report-path secrets-report.json || true",
                        "on_error": "warn",
                        "timeout": 180,
                        "is_required": False,
                    },
                ],
            },
            {
                "name": "Dependency Analysis",
                "order": 1,
                "tasks": [
                    {
                        "name": "SCA — pip-audit",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "sca",
                        "run_code": "pip-audit --format json --output sca-report.json || true",
                        "on_error": "warn",
                        "timeout": 300,
                        "is_required": False,
                    },
                    {
                        "name": "SBOM Generation — syft",
                        "order": 1,
                        "run_language": "bash",
                        "task_type": "supply-chain",
                        "run_code": "syft . -o spdx-json=sbom.spdx.json || true",
                        "on_error": "warn",
                        "timeout": 300,
                        "is_required": False,
                    },
                ],
            },
            {
                "name": "Build & Container Scan",
                "order": 2,
                "tasks": [
                    {
                        "name": "Build Image",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "build",
                        "run_code": "docker build -t $IMAGE_NAME:$BUILD_TAG .",
                        "on_error": "fail",
                        "timeout": 600,
                        "is_required": True,
                    },
                    {
                        "name": "Container Scan — Trivy",
                        "order": 1,
                        "run_language": "bash",
                        "task_type": "container-scan",
                        "run_code": "trivy image --format json --output trivy-report.json $IMAGE_NAME:$BUILD_TAG || true",
                        "on_error": "warn",
                        "timeout": 300,
                        "is_required": False,
                    },
                    {
                        "name": "Sign Image — cosign",
                        "order": 2,
                        "run_language": "bash",
                        "task_type": "supply-chain",
                        "run_code": "cosign sign --key $COSIGN_KEY $IMAGE_NAME:$BUILD_TAG || true",
                        "on_error": "warn",
                        "timeout": 120,
                        "is_required": False,
                    },
                ],
            },
        ],
    },
    {
        "name": "Kubernetes CD Pipeline",
        "description": "CD pipeline for deploying to Kubernetes with smoke tests, approval gate and rollback.",
        "kind": "cd",
        "category": "Deploy",
        "tags": "cd, kubernetes, deploy, smoke-test, approval",
        "stages": [
            {
                "name": "Pre-Deploy Checks",
                "order": 0,
                "tasks": [
                    {
                        "name": "IaC Scan — Checkov",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "iac-scan",
                        "run_code": "checkov -d k8s/ --framework kubernetes --output json || true",
                        "on_error": "warn",
                        "timeout": 180,
                        "is_required": False,
                    },
                    {
                        "name": "Approval Gate",
                        "order": 1,
                        "run_language": "bash",
                        "task_type": "security-gate",
                        "run_code": "echo 'Awaiting deployment approval'",
                        "on_error": "fail",
                        "timeout": 60,
                        "is_required": True,
                    },
                ],
            },
            {
                "name": "Deploy to Dev",
                "order": 1,
                "tasks": [
                    {
                        "name": "kubectl apply — Dev",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "deploy",
                        "run_code": "kubectl apply -f k8s/ -n $APP_NAMESPACE_DEV",
                        "on_error": "fail",
                        "timeout": 300,
                        "is_required": True,
                    },
                    {
                        "name": "Smoke Test — Dev",
                        "order": 1,
                        "run_language": "bash",
                        "task_type": "smoke-test",
                        "run_code": "curl -sf http://$APP_HOST_DEV/healthz | grep -q ok",
                        "on_error": "fail",
                        "timeout": 120,
                        "is_required": True,
                    },
                ],
            },
            {
                "name": "Deploy to Prod",
                "order": 2,
                "tasks": [
                    {
                        "name": "kubectl apply — Prod",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "deploy",
                        "run_code": "kubectl apply -f k8s/ -n $APP_NAMESPACE_PROD",
                        "on_error": "fail",
                        "timeout": 300,
                        "is_required": True,
                    },
                    {
                        "name": "Smoke Test — Prod",
                        "order": 1,
                        "run_language": "bash",
                        "task_type": "smoke-test",
                        "run_code": "curl -sf http://$APP_HOST_PROD/healthz | grep -q ok",
                        "on_error": "fail",
                        "timeout": 120,
                        "is_required": True,
                    },
                    {
                        "name": "Notify Deployment",
                        "order": 2,
                        "run_language": "bash",
                        "task_type": "notify",
                        "run_code": "echo 'Deployment complete: $IMAGE_NAME:$BUILD_TAG'",
                        "on_error": "warn",
                        "timeout": 60,
                        "is_required": False,
                    },
                ],
            },
        ],
    },
    {
        "name": "Full Stack Release Pipeline",
        "description": "End-to-end CI/CD pipeline combining tests, security scans, build, deploy and compliance gate.",
        "kind": "ci",
        "category": "Full Stack",
        "tags": "ci, cd, full-stack, sast, sca, deploy, compliance",
        "stages": [
            {
                "name": "Test Suite",
                "order": 0,
                "tasks": [
                    {
                        "name": "Unit Tests",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "unit-test",
                        "run_code": "pytest tests/unit -v --tb=short",
                        "on_error": "fail",
                        "timeout": 300,
                        "is_required": True,
                    },
                    {
                        "name": "Integration Tests",
                        "order": 1,
                        "run_language": "bash",
                        "task_type": "integration-test",
                        "run_code": "pytest tests/integration -v --tb=short",
                        "on_error": "fail",
                        "timeout": 600,
                        "is_required": True,
                    },
                ],
            },
            {
                "name": "Security Gate",
                "order": 1,
                "tasks": [
                    {
                        "name": "SAST",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "sast",
                        "run_code": "bandit -r app/ -ll",
                        "on_error": "warn",
                        "timeout": 180,
                        "is_required": False,
                    },
                    {
                        "name": "SCA",
                        "order": 1,
                        "run_language": "bash",
                        "task_type": "sca",
                        "run_code": "pip-audit",
                        "on_error": "warn",
                        "timeout": 180,
                        "is_required": False,
                    },
                    {
                        "name": "Compliance Check",
                        "order": 2,
                        "run_language": "bash",
                        "task_type": "compliance-check",
                        "run_code": "echo 'Compliance checks passed'",
                        "on_error": "fail",
                        "timeout": 60,
                        "is_required": True,
                    },
                ],
            },
            {
                "name": "Build & Push",
                "order": 2,
                "tasks": [
                    {
                        "name": "Build Docker Image",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "build",
                        "run_code": "docker build -t $IMAGE_NAME:$BUILD_TAG .",
                        "on_error": "fail",
                        "timeout": 600,
                        "is_required": True,
                    },
                    {
                        "name": "Push to Registry",
                        "order": 1,
                        "run_language": "bash",
                        "task_type": "build",
                        "run_code": "docker push $IMAGE_NAME:$BUILD_TAG",
                        "on_error": "fail",
                        "timeout": 300,
                        "is_required": True,
                    },
                ],
            },
            {
                "name": "Deploy & Verify",
                "order": 3,
                "tasks": [
                    {
                        "name": "Deploy",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "deploy",
                        "run_code": "kubectl set image deployment/$APP_NAME app=$IMAGE_NAME:$BUILD_TAG",
                        "on_error": "fail",
                        "timeout": 300,
                        "is_required": True,
                    },
                    {
                        "name": "Smoke Test",
                        "order": 1,
                        "run_language": "bash",
                        "task_type": "smoke-test",
                        "run_code": "curl -sf http://$APP_HOST/healthz | grep -q ok",
                        "on_error": "fail",
                        "timeout": 120,
                        "is_required": True,
                    },
                ],
            },
        ],
    },
    {
        "name": "Performance & Load Test",
        "description": "Performance testing pipeline with k6 load tests, benchmark and alerting on SLA breaches.",
        "kind": "ci",
        "category": "Performance",
        "tags": "performance, load-test, k6, benchmark",
        "stages": [
            {
                "name": "Baseline Benchmark",
                "order": 0,
                "tasks": [
                    {
                        "name": "API Benchmark",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "perf-test",
                        "run_code": "k6 run --out json=baseline.json tests/perf/baseline.js",
                        "on_error": "warn",
                        "timeout": 600,
                        "is_required": False,
                    },
                ],
            },
            {
                "name": "Load Test",
                "order": 1,
                "tasks": [
                    {
                        "name": "k6 Load Test",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "perf-test",
                        "run_code": "k6 run --vus 50 --duration 5m --out json=load-result.json tests/perf/load.js",
                        "on_error": "warn",
                        "timeout": 600,
                        "is_required": True,
                    },
                    {
                        "name": "SLA Gate",
                        "order": 1,
                        "run_language": "python",
                        "task_type": "perf-test",
                        "run_code": "import json; r=json.load(open('load-result.json')); assert r.get('p95',9999)<1000, 'P95 > 1s'",
                        "on_error": "warn",
                        "timeout": 60,
                        "is_required": False,
                    },
                ],
            },
        ],
    },
    {
        "name": "Compliance Audit CI",
        "description": "CI pipeline with OWASP DAST, CIS checks, IaC scanning and automated compliance report generation.",
        "kind": "ci",
        "category": "Security",
        "tags": "ci, dast, iac-scan, compliance, audit",
        "stages": [
            {
                "name": "DAST",
                "order": 0,
                "tasks": [
                    {
                        "name": "OWASP ZAP DAST",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "dast",
                        "run_code": "zap-baseline.py -t http://$APP_HOST -r dast-report.html || true",
                        "on_error": "warn",
                        "timeout": 600,
                        "is_required": False,
                    },
                ],
            },
            {
                "name": "IaC & Config",
                "order": 1,
                "tasks": [
                    {
                        "name": "Checkov IaC Scan",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "iac-scan",
                        "run_code": "checkov -d terraform/ --output json --output-file checkov-report.json || true",
                        "on_error": "warn",
                        "timeout": 300,
                        "is_required": False,
                    },
                    {
                        "name": "Hadolint Dockerfile",
                        "order": 1,
                        "run_language": "bash",
                        "task_type": "iac-scan",
                        "run_code": "hadolint Dockerfile || true",
                        "on_error": "warn",
                        "timeout": 60,
                        "is_required": False,
                    },
                ],
            },
            {
                "name": "Compliance Report",
                "order": 2,
                "tasks": [
                    {
                        "name": "Compliance Gate",
                        "order": 0,
                        "run_language": "bash",
                        "task_type": "compliance-check",
                        "run_code": "echo 'Compliance audit complete'",
                        "on_error": "fail",
                        "timeout": 60,
                        "is_required": True,
                    },
                    {
                        "name": "Notify Team",
                        "order": 1,
                        "run_language": "bash",
                        "task_type": "notify",
                        "run_code": "echo 'Compliance report generated for $BUILD_TAG'",
                        "on_error": "warn",
                        "timeout": 30,
                        "is_required": False,
                    },
                ],
            },
        ],
    },
]


def seed():
    app = create_app()
    with app.app_context():
        import json as _json

        existing = {t.name for t in PipelineTemplate.query.all()}
        added = 0
        for tmpl in TEMPLATES:
            if tmpl["name"] in existing:
                print(f"  skip (exists): {tmpl['name']}")
                continue
            stages = tmpl.pop("stages", [])
            t = PipelineTemplate(
                id=resource_id("tmpl"),
                definition_json=_json.dumps(stages),
                created_by="system",
                **tmpl,
            )
            db.session.add(t)
            added += 1
            print(f"  added: {t.name}")
        db.session.commit()
        print(f"Done — {added} template(s) added.")


if __name__ == "__main__":
    seed()
