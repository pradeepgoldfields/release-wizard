"""DevSecOps Maturity Model — pipeline/application/product scoring engine.

Algorithm
---------
Each pipeline is assessed across 12 security/quality dimensions.
For each dimension, every task in the pipeline is inspected (task_type tags,
name, description, run_code) for matches.  The best score across all matching
tasks is taken per dimension (presence of even one well-configured task earns
the credit).

Explicit task_type tags take precedence over keyword matching and always grant
at least score=1.  Custom tags (any non-standard value) are also matched if they
appear in the dimension's tag_aliases list.

Task score per dimension (0–3):
  0  Absent     — no tag or keyword match found in the pipeline
  1  Basic      — task found (via tag or keyword); not hardened
  2  Configured — found AND (non-default timeout OR specific name OR explicit tag)
  3  Enforced   — score ≥ 2 AND is_required=True AND on_error="fail"

Pipeline-kind awareness:
  Dimensions are tagged with applicable_kinds. A dimension whose kind does not
  include the pipeline's kind is skipped (treated as N/A — not counted against
  the score). This ensures CI pipelines are not penalised for missing
  deployment dimensions and CD pipelines are not penalised for missing build
  dimensions that live upstream.

Weighted sum across applicable dimensions, normalised to 0–100.

Grades:
  0–19   Initiation
  20–39  Developing
  40–59  Defined
  60–79  Managed
  80–100 Optimizing
"""

from __future__ import annotations

from typing import Any

# ── Task type tag registry ─────────────────────────────────────────────────────
# Canonical task_type values shown in the UI picker.
TASK_TYPE_OPTIONS: list[dict[str, str]] = [
    {"value": "sast", "label": "SAST — Static Analysis"},
    {"value": "sca", "label": "SCA — Dependency Scan"},
    {"value": "dast", "label": "DAST — Dynamic Analysis"},
    {"value": "secret-scan", "label": "Secret Scanning"},
    {"value": "container-scan", "label": "Container / Image Scan"},
    {"value": "unit-test", "label": "Unit Testing"},
    {"value": "integration-test", "label": "Integration Testing"},
    {"value": "code-coverage", "label": "Code Coverage"},
    {"value": "smoke-test", "label": "Smoke / Health Check"},
    {"value": "build", "label": "Build / Compile"},
    {"value": "release", "label": "Release / Versioning"},
    {"value": "deploy", "label": "Deploy / Env Promotion"},
    {"value": "security-gate", "label": "Security Gate / Approval"},
    {"value": "lint", "label": "Lint / Format"},
    {"value": "notify", "label": "Notification"},
    {"value": "iac-scan", "label": "IaC Security Scan"},
    {"value": "api-security", "label": "API Security / Contract Test"},
    {"value": "supply-chain", "label": "Supply Chain / SBOM"},
    {"value": "observability", "label": "Observability Check"},
    {"value": "perf-test", "label": "Performance / Load Test"},
    {"value": "artifact", "label": "Artifact Publish"},
    {"value": "compliance-check", "label": "Compliance as Code"},
    {"value": "vuln-management", "label": "Vulnerability Management"},
    {"value": "custom", "label": "Custom (specify below)"},
]

# Pipeline kinds that exist in the system
_CI_KINDS = {"ci", "CI"}
_CD_KINDS = {"cd", "CD"}
_ALL_KINDS = {"ci", "cd", "CI", "CD", "release", "build"}

# ── Dimension registry ────────────────────────────────────────────────────────
# 20 dimensions across DSOMM / OWASP SAMM / NIST SSDF / OpenSSF Scorecard.
# Weights reflect industry importance; score is normalised to 0–100 per pipeline
# using only applicable dimensions (kind-aware) so no pipeline is penalised for
# dimensions outside its scope.
# applicable_kinds: set of pipeline.kind values where this dimension counts.
#   None or empty set = applies to ALL kinds.
DIMENSIONS: dict[str, dict[str, Any]] = {
    "sast": {
        "label": "SAST",
        "description": "Static Application Security Testing",
        "icon": "🔍",
        "tag_aliases": ["sast"],
        "keywords": [
            "sast",
            "sonarqube",
            "sonar",
            "semgrep",
            "bandit",
            "checkmarx",
            "veracode",
            "snyk",
            "eslint-security",
            "pylint-security",
            "flake8-security",
            "codeql",
            "spotbugs",
        ],
        "applicable_kinds": None,  # all pipelines
        "weight": 4,
        "action_hint": "Add a SonarQube/Semgrep/Bandit task — set is_required=True and on_error=fail",
    },
    "sca": {
        "label": "SCA",
        "description": "Software Composition Analysis",
        "icon": "📦",
        "tag_aliases": ["sca"],
        "keywords": [
            "sca",
            "dependency-check",
            "owasp-dependency",
            "snyk",
            "trivy",
            "grype",
            "cyclonedx",
            "sbom",
            "audit",
            "pip-audit",
            "npm-audit",
            "bundler-audit",
        ],
        "applicable_kinds": None,
        "weight": 4,
        "action_hint": "Add a dependency scan task (Trivy/Grype/pip-audit) — enforce it to block on vulnerable deps",
    },
    "dast": {
        "label": "DAST",
        "description": "Dynamic Application Security Testing",
        "icon": "🌐",
        "tag_aliases": ["dast"],
        "keywords": [
            "dast",
            "zap",
            "owasp-zap",
            "burp",
            "arachni",
            "nikto",
            "nuclei",
            "w3af",
            "dynamic-scan",
        ],
        "applicable_kinds": {"cd", "CD", "release"},  # runs against deployed app
        "weight": 3,
        "action_hint": "Add an OWASP ZAP or Nuclei task against a running instance of the app",
    },
    "unit_testing": {
        "label": "Unit Testing",
        "description": "Automated unit test suite",
        "icon": "🧪",
        "tag_aliases": ["unit-test"],
        "keywords": [
            "unit",
            "pytest",
            "jest",
            "mocha",
            "junit",
            "unittest",
            "rspec",
            "nunit",
            "xunit",
            "test",
            "spec",
        ],
        "applicable_kinds": {"ci", "CI", "build", "release"},  # not required in CD
        "weight": 3,
        "action_hint": "Add a pytest/jest task to run your unit test suite",
    },
    "integration_testing": {
        "label": "Integration Testing",
        "description": "API and service integration tests",
        "icon": "🔗",
        "tag_aliases": ["integration-test"],
        "keywords": [
            "integration",
            "e2e",
            "end-to-end",
            "api-test",
            "postman",
            "newman",
            "karate",
            "cypress",
            "playwright",
            "selenium",
            "contract-test",
            "pact",
        ],
        "applicable_kinds": {"ci", "CI", "cd", "CD", "release"},
        "weight": 3,
        "action_hint": "Add Newman/Playwright/Cypress integration tests that hit real endpoints",
    },
    "code_coverage": {
        "label": "Code Coverage",
        "description": "Test coverage measurement and enforcement",
        "icon": "📊",
        "tag_aliases": ["code-coverage"],
        "keywords": [
            "coverage",
            "codecov",
            "coveralls",
            "istanbul",
            "jacoco",
            "cover",
            "lcov",
            "--cov",
        ],
        "applicable_kinds": {"ci", "CI", "build", "release"},
        "weight": 2,
        "action_hint": "Add a coverage report task and enforce a minimum threshold (e.g. 80%)",
    },
    "smoke_testing": {
        "label": "Smoke Testing",
        "description": "Post-deploy health and sanity checks",
        "icon": "💨",
        "tag_aliases": ["smoke-test"],
        "keywords": [
            "smoke",
            "sanity",
            "health-check",
            "healthcheck",
            "curl-test",
            "readyz",
            "healthz",
            "ping-test",
        ],
        "applicable_kinds": {"cd", "CD", "release"},
        "weight": 2,
        "action_hint": "Add a curl/healthcheck smoke test after deployment to verify the app is responsive",
    },
    "release_practices": {
        "label": "Release Practices",
        "description": "Versioning, changelogs, and release tagging",
        "icon": "🏷️",
        "tag_aliases": ["release"],
        "keywords": [
            "release",
            "version",
            "tag",
            "changelog",
            "semantic-version",
            "semver",
            "gitflow",
            "conventional-commit",
            "release-notes",
        ],
        "applicable_kinds": None,
        "weight": 3,
        "action_hint": "Add a semantic versioning/changelog task to automate release notes",
    },
    "environment_promotion": {
        "label": "Env Promotion",
        "description": "Gate-based promotion between environments",
        "icon": "🚀",
        "tag_aliases": ["deploy"],
        "keywords": [
            "promote",
            "deploy",
            "kubectl",
            "helm",
            "environment",
            "staging",
            "production",
            "rollout",
            "canary",
            "blue-green",
        ],
        "applicable_kinds": {"cd", "CD", "release"},
        "weight": 3,
        "action_hint": "Add a kubectl/helm deploy task with environment gate approvals",
    },
    "security_gates": {
        "label": "Security Gates",
        "description": "Policy enforcement and manual approvals",
        "icon": "🔐",
        "tag_aliases": ["security-gate"],
        "keywords": [
            "gate",
            "approval",
            "sign-off",
            "policy",
            "opa",
            "conftest",
            "security-gate",
            "compliance-check",
            "admission",
        ],
        "applicable_kinds": None,
        "weight": 4,
        "action_hint": "Add a policy/OPA task or approval gate before production deployments",
    },
    "container_security": {
        "label": "Container Security",
        "description": "Image scanning and signing",
        "icon": "🐳",
        "tag_aliases": ["container-scan"],
        "keywords": [
            "trivy",
            "docker-scan",
            "snyk-container",
            "anchore",
            "clair",
            "cosign",
            "crane",
            "image-scan",
            "container-scan",
        ],
        "applicable_kinds": {"ci", "CI", "cd", "CD", "build", "release"},
        "weight": 3,
        "action_hint": "Add Trivy/Anchore container image scanning before push to registry",
    },
    "secret_scanning": {
        "label": "Secret Scanning",
        "description": "Detection of leaked credentials in code",
        "icon": "🕵️",
        "tag_aliases": ["secret-scan"],
        "keywords": [
            "secret-scan",
            "trufflehog",
            "gitleaks",
            "detect-secrets",
            "git-secrets",
            "secret",
            "credential-scan",
        ],
        "applicable_kinds": None,
        "weight": 2,
        "action_hint": "Add Gitleaks/TruffleHog to scan commits for accidentally committed secrets",
    },
    # ── Additional dimensions aligned with DSOMM / OWASP SAMM / NIST SSDF ──────
    "iac_security": {
        "label": "IaC Security",
        "description": "Infrastructure-as-Code scanning and drift detection",
        "icon": "🏗️",
        "tag_aliases": ["iac-scan", "iac-security"],
        "keywords": [
            "terraform",
            "checkov",
            "tfsec",
            "terrascan",
            "kics",
            "ansible-lint",
            "cfn-nag",
            "pulumi",
            "helm-lint",
            "iac",
            "infra-scan",
            "drift",
            "driftctl",
        ],
        "applicable_kinds": {"cd", "CD", "release"},
        "weight": 3,
        "action_hint": "Add Checkov/tfsec to scan Terraform/Helm/CloudFormation manifests before deployment",
    },
    "api_security": {
        "label": "API Security",
        "description": "API contract validation and security testing",
        "icon": "🔌",
        "tag_aliases": ["api-security", "api-test"],
        "keywords": [
            "swagger",
            "openapi",
            "spectral",
            "owasp-api",
            "42crunch",
            "api-security",
            "api-scan",
            "apisec",
            "rest-assured",
            "schemathesis",
            "dredd",
            "graphql-security",
        ],
        "applicable_kinds": None,
        "weight": 3,
        "action_hint": "Add Spectral or OWASP API Security checks to validate your API definitions",
    },
    "supply_chain": {
        "label": "Supply Chain",
        "description": "SBOM generation, artifact signing and provenance",
        "icon": "🔗",
        "tag_aliases": ["supply-chain", "sbom", "provenance"],
        "keywords": [
            "sbom",
            "cyclonedx",
            "spdx",
            "cosign",
            "sigstore",
            "in-toto",
            "slsa",
            "syft",
            "rekor",
            "provenance",
            "attestation",
            "supply-chain",
            "software-bill",
        ],
        "applicable_kinds": {"ci", "CI", "cd", "CD", "build", "release"},
        "weight": 3,
        "action_hint": "Generate an SBOM with Syft/CycloneDX and sign artifacts with Cosign (Sigstore) for SLSA compliance",
    },
    "observability": {
        "label": "Observability",
        "description": "Structured logging, metrics, and distributed tracing",
        "icon": "📡",
        "tag_aliases": ["observability", "monitoring"],
        "keywords": [
            "prometheus",
            "grafana",
            "opentelemetry",
            "otel",
            "jaeger",
            "zipkin",
            "datadog",
            "newrelic",
            "elastic-apm",
            "logging",
            "structured-log",
            "log-validation",
            "metrics-check",
            "alertmanager",
            "pagerduty",
        ],
        "applicable_kinds": {"cd", "CD", "release"},
        "weight": 2,
        "action_hint": "Add a post-deploy step that validates metrics/logs are flowing (e.g. query Prometheus for the new service)",
    },
    "performance_testing": {
        "label": "Performance Testing",
        "description": "Load, stress, and benchmark testing",
        "icon": "⚡",
        "tag_aliases": ["perf-test", "load-test", "performance-test"],
        "keywords": [
            "k6",
            "jmeter",
            "gatling",
            "locust",
            "artillery",
            "ab ",
            "wrk",
            "vegeta",
            "load-test",
            "stress-test",
            "benchmark",
            "performance",
            "latency",
            "throughput",
        ],
        "applicable_kinds": {"ci", "CI", "cd", "CD", "release"},
        "weight": 2,
        "action_hint": "Add a k6/Gatling load test to catch regressions before production — gate on p99 latency",
    },
    "artifact_management": {
        "label": "Artifact Management",
        "description": "Versioned artifact promotion and retention policies",
        "icon": "📁",
        "tag_aliases": ["artifact", "publish", "artifact-management"],
        "keywords": [
            "nexus",
            "artifactory",
            "jfrog",
            "harbor",
            "quay",
            "docker-push",
            "publish",
            "upload-artifact",
            "release-artifact",
            "oci-push",
            "npm-publish",
            "pypi-publish",
            "maven-deploy",
            "retention",
        ],
        "applicable_kinds": {"ci", "CI", "cd", "CD", "build", "release"},
        "weight": 2,
        "action_hint": "Add an artifact publish step to Nexus/Artifactory/Harbor and enforce image retention policies",
    },
    "compliance_as_code": {
        "label": "Compliance as Code",
        "description": "Automated policy enforcement (OPA, Kyverno, CIS benchmarks)",
        "icon": "📋",
        "tag_aliases": ["compliance-check", "policy-as-code"],
        "keywords": [
            "opa",
            "conftest",
            "kyverno",
            "cis-benchmark",
            "inspec",
            "chef-inspec",
            "compliance",
            "policy",
            "cis",
            "pci-dss",
            "soc2",
            "fedramp",
            "nist",
            "iso27001",
        ],
        "applicable_kinds": None,
        "weight": 3,
        "action_hint": "Add Conftest/OPA policies to enforce CIS or internal compliance rules automatically in pipeline",
    },
    "vulnerability_management": {
        "label": "Vulnerability Mgmt",
        "description": "CVE triage, SLA tracking and patch verification",
        "icon": "🩹",
        "tag_aliases": ["vuln-management", "cve-check"],
        "keywords": [
            "cve",
            "nvd",
            "vulndb",
            "patch",
            "remediation",
            "vex",
            "epss",
            "cvss",
            "osv",
            "grype",
            "dependency-track",
            "defect-dojo",
            "vuln-check",
            "security-advisory",
        ],
        "applicable_kinds": None,
        "weight": 3,
        "action_hint": "Integrate Dependency-Track or DefectDojo to track CVEs over time and enforce SLA-based blocking",
    },
}

# Maximum possible raw XP across all dimensions (used as fallback when all dims apply)
_MAX_RAW_XP: int = sum(d["weight"] * 3 for d in DIMENSIONS.values())


def _applicable_dimensions(pipeline_kind: str) -> list[tuple[str, dict]]:
    """Return (key, cfg) pairs for dimensions that apply to this pipeline kind."""
    kind = (pipeline_kind or "ci").lower()
    result = []
    for key, cfg in DIMENSIONS.items():
        kinds = cfg.get("applicable_kinds")
        if kinds is None or kind in {k.lower() for k in kinds}:
            result.append((key, cfg))
    return result


_GRADE_BANDS = [
    (80, "Optimizing", "rocket"),
    (60, "Managed", "trophy"),
    (40, "Defined", "gear"),
    (20, "Developing", "seedling"),
    (0, "Initiation", "egg"),
]


# ── Core scoring primitives ────────────────────────────────────────────────────


def _score_task_for_dimension(task: Any, keywords: list[str], tag_aliases: list[str]) -> int:
    """Return 0-3 score for one task against one dimension's keyword list and tag aliases.

    Explicit task_type tags are checked first and always elevate the match to
    at least score=2 (configured), since the user has intentionally labelled the task.
    """
    # ── Explicit tag match (highest confidence) ───────────────────────────────
    task_tags = {
        t.strip().lower() for t in (getattr(task, "task_type", "") or "").split(",") if t.strip()
    }
    tag_match = bool(task_tags & {a.lower() for a in tag_aliases})

    # ── Keyword match (fallback) ───────────────────────────────────────────────
    search = " ".join(
        [
            (task.name or ""),
            (task.description or ""),
            (task.run_code or ""),
        ]
    ).lower()
    keyword_match = any(kw in search for kw in keywords)

    if not tag_match and not keyword_match:
        return 0  # absent

    # Start at 2 for explicit tag, 1 for keyword-only
    score = 2 if tag_match else 1

    # Level 2 via keyword: specific name or non-default timeout
    if not tag_match:
        task_name_lower = (task.name or "").lower()
        specific_name = len(task_name_lower) > 5 and any(kw in task_name_lower for kw in keywords)
        non_default_timeout = getattr(task, "timeout", 300) != 300
        if specific_name or non_default_timeout:
            score = 2

    # Level 3: enforced — required + fail-fast
    if (
        score >= 2
        and getattr(task, "is_required", False)
        and getattr(task, "on_error", "") == "fail"
    ):
        score = 3

    return score


def _score_pipeline_dimension(
    pipeline: Any, dim_key: str, dim_cfg: dict, applicable: bool = True
) -> dict:
    """Score a single dimension across all tasks in a pipeline."""
    keywords = dim_cfg["keywords"]
    tag_aliases = dim_cfg.get("tag_aliases", [])
    best_score = 0
    matched_tasks: list[str] = []

    if applicable:
        for stage in pipeline.stages or []:
            for task in stage.tasks or []:
                ts = _score_task_for_dimension(task, keywords, tag_aliases)
                if ts > 0:
                    matched_tasks.append(task.name)
                if ts > best_score:
                    best_score = ts

    return {
        "key": dim_key,
        "label": dim_cfg["label"],
        "description": dim_cfg["description"],
        "icon": dim_cfg["icon"],
        "score": best_score,
        "weight": dim_cfg["weight"],
        "earned_xp": best_score * dim_cfg["weight"],
        "max_xp": dim_cfg["weight"] * 3,
        "matched_tasks": list(dict.fromkeys(matched_tasks)),  # deduplicate
        "action_hint": dim_cfg["action_hint"],
        "applicable": applicable,
    }


def _score_to_grade(score: float) -> tuple[str, str]:
    for threshold, grade, icon in _GRADE_BANDS:
        if score >= threshold:
            return grade, icon
    return "Initiation", "egg"


def _compute_badges(dimension_results: list[dict]) -> list[dict]:
    """Award a badge for each dimension scoring ≥ 2."""
    return [
        {
            "key": d["key"],
            "label": d["label"],
            "icon": d["icon"],
            "level": d["score"],
            "level_label": ["Absent", "Basic", "Configured", "Enforced"][d["score"]],
        }
        for d in dimension_results
        if d["score"] >= 2
    ]


def _next_milestone(score: float, dimension_results: list[dict]) -> dict:
    """Find the most impactful next improvement step."""
    grade, _ = _score_to_grade(score)
    next_grade = None
    points_needed = 0.0
    for threshold, gname, _ in reversed(_GRADE_BANDS):
        if score < threshold:
            next_grade = gname
            points_needed = round(threshold - score, 1)
            break

    # Only consider applicable dimensions for improvement suggestions
    applicable = [d for d in dimension_results if d.get("applicable", True)]
    improvable = [d for d in applicable if 0 < d["score"] < 3]
    if not improvable:
        improvable = [d for d in applicable if d["score"] == 0]

    best_dim = max(improvable, key=lambda d: d["weight"]) if improvable else None

    return {
        "current_grade": grade,
        "next_grade": next_grade or grade,
        "points_needed": points_needed,
        "suggested_dimension": best_dim["key"] if best_dim else None,
        "suggested_label": best_dim["label"] if best_dim else None,
        "suggested_icon": best_dim["icon"] if best_dim else None,
        "current_dim_score": best_dim["score"] if best_dim else 0,
        "action_hint": best_dim["action_hint"]
        if best_dim
        else "All dimensions are fully enforced!",
    }


# ── Public API ────────────────────────────────────────────────────────────────


def score_pipeline(pipeline_id: str) -> dict:
    """Return full maturity assessment for a single pipeline."""
    from sqlalchemy.orm import joinedload

    from app.models.pipeline import Pipeline, Stage  # noqa: F401

    pipeline = (
        Pipeline.query.options(joinedload(Pipeline.stages).joinedload(Stage.tasks))
        .filter_by(id=pipeline_id)
        .first_or_404()
    )

    applicable_dims = {key for key, _ in _applicable_dimensions(pipeline.kind or "ci")}
    dimension_results = [
        _score_pipeline_dimension(pipeline, key, cfg, applicable=(key in applicable_dims))
        for key, cfg in DIMENSIONS.items()
    ]

    # Only include applicable dimensions in score normalisation
    applicable_results = [d for d in dimension_results if d["applicable"]]
    total_earned = sum(d["earned_xp"] for d in applicable_results)
    max_applicable_xp = sum(d["max_xp"] for d in applicable_results)
    raw_score = (total_earned / max_applicable_xp * 100) if max_applicable_xp else 0.0
    score = round(raw_score, 1)

    grade, grade_icon = _score_to_grade(score)
    badges = _compute_badges(dimension_results)
    milestone = _next_milestone(score, dimension_results)

    return {
        "pipeline_id": pipeline.id,
        "pipeline_name": pipeline.name,
        "pipeline_kind": pipeline.kind,
        "product_id": pipeline.product_id,
        "application_id": pipeline.application_id,
        "score": score,
        "xp": total_earned,
        "max_xp": max_applicable_xp,
        "grade": grade,
        "grade_icon": grade_icon,
        "stage_count": len(pipeline.stages or []),
        "task_count": sum(len(s.tasks or []) for s in (pipeline.stages or [])),
        "applicable_dimension_count": len(applicable_results),
        "dimensions": dimension_results,
        "badges": badges,
        "badge_count": len(badges),
        "next_milestone": milestone,
    }


def score_application(application_id: str) -> dict:
    """Return maturity assessment for an application artifact and all its pipelines."""
    from app.models.application import ApplicationArtifact
    from app.models.pipeline import Pipeline  # noqa: F401

    app_artifact = db_get_or_404(ApplicationArtifact, application_id)
    pipelines = Pipeline.query.filter_by(application_id=application_id).all()

    pipeline_scores = [score_pipeline(p.id) for p in pipelines]

    avg_score = (
        round(sum(p["score"] for p in pipeline_scores) / len(pipeline_scores), 1)
        if pipeline_scores
        else 0.0
    )
    grade, grade_icon = _score_to_grade(avg_score)

    # Aggregate dimension gaps across all pipelines in this application
    gap_dims: dict[str, list[int]] = {k: [] for k in DIMENSIONS}
    for ps in pipeline_scores:
        for d in ps["dimensions"]:
            gap_dims[d["key"]].append(d["score"])
    top_gaps = sorted(
        [
            {
                "key": k,
                "label": DIMENSIONS[k]["label"],
                "icon": DIMENSIONS[k]["icon"],
                "avg_score": round(sum(v) / len(v), 2) if v else 0,
            }
            for k, v in gap_dims.items()
        ],
        key=lambda x: x["avg_score"],
    )[:5]

    return {
        "application_id": app_artifact.id,
        "application_name": app_artifact.name,
        "build_version": app_artifact.build_version,
        "compliance_rating": app_artifact.compliance_rating or "Non-Compliant",
        "product_id": app_artifact.product_id,
        "score": avg_score,
        "grade": grade,
        "grade_icon": grade_icon,
        "pipeline_count": len(pipeline_scores),
        "pipelines": pipeline_scores,
        "top_gaps": top_gaps,
    }


def score_product(product_id: str) -> dict:
    """Return maturity assessment for a product aggregated through its applications."""
    from app.models.application import ApplicationArtifact
    from app.models.product import Product

    product = db_get_or_404(Product, product_id)
    applications = ApplicationArtifact.query.filter_by(product_id=product_id).all()

    application_scores = [score_application(a.id) for a in applications]

    avg_score = (
        round(sum(a["score"] for a in application_scores) / len(application_scores), 1)
        if application_scores
        else 0.0
    )
    grade, grade_icon = _score_to_grade(avg_score)

    # Aggregate dimension gaps across all applications
    gap_dims: dict[str, list[int]] = {k: [] for k in DIMENSIONS}
    for app_score in application_scores:
        for ps in app_score["pipelines"]:
            for d in ps["dimensions"]:
                gap_dims[d["key"]].append(d["score"])
    top_gaps = sorted(
        [
            {
                "key": k,
                "label": DIMENSIONS[k]["label"],
                "icon": DIMENSIONS[k]["icon"],
                "avg_score": round(sum(v) / len(v), 2) if v else 0,
            }
            for k, v in gap_dims.items()
        ],
        key=lambda x: x["avg_score"],
    )[:5]

    total_pipelines = sum(a["pipeline_count"] for a in application_scores)

    return {
        "product_id": product.id,
        "product_name": product.name,
        "score": avg_score,
        "grade": grade,
        "grade_icon": grade_icon,
        "application_count": len(application_scores),
        "pipeline_count": total_pipelines,
        "applications": application_scores,
        "top_gaps": top_gaps,
    }


def get_overview() -> dict:
    """Return maturity summary for all products."""
    from app.models.product import Product

    products = Product.query.order_by(Product.name).all()
    summaries = []
    for product in products:
        ps = score_product(product.id)
        summaries.append(
            {
                "product_id": ps["product_id"],
                "product_name": ps["product_name"],
                "score": ps["score"],
                "grade": ps["grade"],
                "grade_icon": ps["grade_icon"],
                "application_count": ps["application_count"],
                "pipeline_count": ps["pipeline_count"],
                "top_gaps": ps["top_gaps"],
            }
        )

    summaries.sort(key=lambda x: x["score"], reverse=True)
    platform_avg = (
        round(sum(s["score"] for s in summaries) / len(summaries), 1) if summaries else 0.0
    )

    return {
        "products": summaries,
        "total_products": len(products),
        "platform_avg_score": platform_avg,
    }


# ── Thin DB helper (avoids importing db at module level) ──────────────────────


def db_get_or_404(model: Any, pk: str) -> Any:
    from app.extensions import db

    return db.get_or_404(model, pk)
