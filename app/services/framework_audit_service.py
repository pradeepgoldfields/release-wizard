"""ACF and ISAE 3000 / SOC 2 framework audit report generator for pipeline runs.

Maps industry-standard assurance control frameworks to evidence automatically
extracted from a PipelineRun's task logs, task types, compliance scores,
audit events, and run metadata.

Frameworks supported
--------------------
ISAE 3000 / SOC 2 Type II
    Maps the 5 AICPA Trust Service Criteria (TSC) to CI/CD pipeline controls.
    Each TSC maps to one or more pipeline dimensions whose presence constitutes
    evidence that the control is operating effectively.

ACF (Australian Assurance and Compliance Framework / APRA CPS 234 / ASD ISM)
    Maps the 8 ACF control domains (People, Processes, Technology, Information,
    Physical, Governance, Incident, Supply Chain) to pipeline task evidence.

Evidence confidence levels
--------------------------
  confirmed  — pipeline metadata or task output definitively satisfies the control
  partial    — some but not all indicators are present
  manual     — cannot be determined automatically from pipeline data
  not_met    — control is clearly absent or failed
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# ── ISAE 3000 / SOC 2 Trust Service Criteria ─────────────────────────────────
# Reference: AICPA TSC 2017 (updated 2022)
# For CI/CD pipelines these map directly to DevSecOps practices.

SOC2_CRITERIA: list[dict] = [
    # ── CC1: Control Environment ──────────────────────────────────────────────
    {
        "id": "CC1.1",
        "category": "CC1",
        "category_label": "Control Environment",
        "title": "Commitment to integrity and ethical values",
        "description": "The entity demonstrates a commitment to integrity and ethical values. "
        "In CI/CD: pipelines enforce policy gates, require approval for production deploys, "
        "and maintain an immutable audit trail.",
        "task_types": ["security-gate"],
        "dimension_keys": ["security_gates", "compliance_as_code"],
        "evidence_keywords": ["approve", "gate", "policy", "compliance", "required"],
        "weight": 3,
    },
    {
        "id": "CC1.2",
        "category": "CC1",
        "category_label": "Control Environment",
        "title": "Board oversight of internal controls",
        "description": "The board of directors demonstrates independence from management and exercises "
        "oversight of internal control. In CI/CD: release approvals, separation of trigger "
        "from deployment, role-based pipeline access.",
        "task_types": ["security-gate", "compliance-check"],
        "dimension_keys": ["security_gates"],
        "evidence_keywords": ["approval", "authorize", "sign-off", "rbac"],
        "weight": 2,
    },
    {
        "id": "CC1.3",
        "category": "CC1",
        "category_label": "Control Environment",
        "title": "Organizational structure and authority",
        "description": "Reporting lines, authority and responsibilities are defined. "
        "In CI/CD: pipeline ownership via product/team assignment, RBAC role bindings, "
        "audit log of who triggered each run.",
        "task_types": [],
        "dimension_keys": [],
        "evidence_keywords": ["rbac", "role", "owner", "triggered_by"],
        "weight": 2,
    },
    # ── CC2: Communication and Information ────────────────────────────────────
    {
        "id": "CC2.1",
        "category": "CC2",
        "category_label": "Communication & Information",
        "title": "Information to support internal control objectives",
        "description": "The entity obtains or generates relevant, quality information to support "
        "the functioning of internal controls. In CI/CD: structured task output JSON, "
        "SBOM generation, artifact metadata.",
        "task_types": ["supply-chain"],
        "dimension_keys": ["supply_chain", "artifact_management"],
        "evidence_keywords": ["sbom", "output_json", "artifact", "report"],
        "weight": 2,
    },
    {
        "id": "CC2.2",
        "category": "CC2",
        "category_label": "Communication & Information",
        "title": "Internal communication of control information",
        "description": "The entity internally communicates information necessary to support the "
        "functioning of internal controls. In CI/CD: notifications, structured run logs, "
        "Prometheus alerting, audit trail.",
        "task_types": ["notify", "observability"],
        "dimension_keys": ["observability"],
        "evidence_keywords": ["notify", "alert", "slack", "pagerduty", "webhook", "log"],
        "weight": 2,
    },
    # ── CC3: Risk Assessment ──────────────────────────────────────────────────
    {
        "id": "CC3.2",
        "category": "CC3",
        "category_label": "Risk Assessment",
        "title": "Identification and analysis of risk",
        "description": "The entity identifies and analyzes risk to achieve its objectives. "
        "In CI/CD: SAST, SCA, DAST, secret scanning provide automated risk identification.",
        "task_types": ["sast", "sca", "dast", "secret-scan"],
        "dimension_keys": ["sast", "sca", "dast", "secret_scanning"],
        "evidence_keywords": ["sast", "sca", "dast", "sonar", "snyk", "trivy", "gitleaks"],
        "weight": 4,
    },
    {
        "id": "CC3.3",
        "category": "CC3",
        "category_label": "Risk Assessment",
        "title": "Consideration of fraud in risk assessment",
        "description": "The entity considers the potential for fraud in assessing risks. "
        "In CI/CD: secret scanning, dependency confusion prevention, supply chain security.",
        "task_types": ["secret-scan", "supply-chain"],
        "dimension_keys": ["secret_scanning", "supply_chain"],
        "evidence_keywords": ["secret", "gitleaks", "trufflehog", "cosign", "supply-chain"],
        "weight": 3,
    },
    # ── CC4: Monitoring ────────────────────────────────────────────────────────
    {
        "id": "CC4.1",
        "category": "CC4",
        "category_label": "Monitoring Activities",
        "title": "Ongoing and separate evaluations",
        "description": "The entity selects, develops, and performs ongoing and/or separate evaluations "
        "to ascertain whether components of internal control are present and functioning. "
        "In CI/CD: automated test suites, code coverage, compliance scoring.",
        "task_types": ["unit-test", "integration-test", "code-coverage"],
        "dimension_keys": ["unit_testing", "integration_testing", "code_coverage"],
        "evidence_keywords": ["test", "coverage", "pytest", "jest", "integration"],
        "weight": 4,
    },
    {
        "id": "CC4.2",
        "category": "CC4",
        "category_label": "Monitoring Activities",
        "title": "Evaluation and communication of deficiencies",
        "description": "The entity evaluates and communicates internal control deficiencies in a timely "
        "manner to those responsible for corrective action. In CI/CD: failed pipeline "
        "notifications, alert rules firing, DevSecOps maturity gap reporting.",
        "task_types": ["notify"],
        "dimension_keys": ["observability"],
        "evidence_keywords": ["notify", "failure", "alert", "deficiency"],
        "weight": 3,
    },
    # ── CC5: Control Activities ────────────────────────────────────────────────
    {
        "id": "CC5.1",
        "category": "CC5",
        "category_label": "Control Activities",
        "title": "Selection and development of control activities",
        "description": "The entity selects and develops control activities that contribute to the "
        "mitigation of risks. In CI/CD: required tasks (is_required=true), "
        "on_error=fail gates, compliance rules.",
        "task_types": ["security-gate", "compliance-check"],
        "dimension_keys": ["security_gates", "compliance_as_code"],
        "evidence_keywords": ["required", "gate", "policy", "fail", "compliance"],
        "weight": 4,
    },
    {
        "id": "CC5.2",
        "category": "CC5",
        "category_label": "Control Activities",
        "title": "Selection of technology control activities",
        "description": "The entity selects and develops general control activities over technology. "
        "In CI/CD: IaC scanning, container scanning, image signing.",
        "task_types": ["iac-scan", "container-scan", "supply-chain"],
        "dimension_keys": ["iac_security", "container_security", "supply_chain"],
        "evidence_keywords": ["terraform", "checkov", "trivy", "cosign", "iac"],
        "weight": 3,
    },
    {
        "id": "CC5.3",
        "category": "CC5",
        "category_label": "Control Activities",
        "title": "Deployment of policies and procedures",
        "description": "The entity deploys control activities through policies that establish what "
        "is expected. In CI/CD: pipeline-as-code enforces repeatable, auditable processes; "
        "version-controlled pipeline definitions.",
        "task_types": ["build", "release"],
        "dimension_keys": ["release_practices", "artifact_management"],
        "evidence_keywords": ["version", "tag", "changelog", "semver", "artifact"],
        "weight": 3,
    },
    # ── CC6: Logical and Physical Access ──────────────────────────────────────
    {
        "id": "CC6.1",
        "category": "CC6",
        "category_label": "Logical & Physical Access",
        "title": "Access controls to meet objectives",
        "description": "The entity implements logical access security controls over protected information "
        "assets to prevent security threats. In CI/CD: secret management, vault integration, "
        "no hardcoded credentials in pipeline scripts.",
        "task_types": ["secret-scan"],
        "dimension_keys": ["secret_scanning"],
        "evidence_keywords": ["vault", "secret", "credential", "no hardcoded", "gitleaks"],
        "weight": 4,
    },
    {
        "id": "CC6.3",
        "category": "CC6",
        "category_label": "Logical & Physical Access",
        "title": "Access control over third-party access",
        "description": "The entity authorizes, modifies, or removes access to data. In CI/CD: "
        "webhook tokens, RBAC role bindings, API key management.",
        "task_types": [],
        "dimension_keys": ["security_gates"],
        "evidence_keywords": ["rbac", "token", "api-key", "role", "permission"],
        "weight": 3,
    },
    # ── CC7: System Operations ─────────────────────────────────────────────────
    {
        "id": "CC7.1",
        "category": "CC7",
        "category_label": "System Operations",
        "title": "Detect and monitor for vulnerabilities",
        "description": "The entity uses detection and monitoring procedures to identify changes to "
        "configurations and vulnerabilities. In CI/CD: DAST, SCA, vulnerability management.",
        "task_types": ["dast", "sca", "vuln-management"],
        "dimension_keys": ["dast", "sca", "vulnerability_management"],
        "evidence_keywords": ["dast", "vulnerability", "cve", "trivy", "grype", "scan"],
        "weight": 4,
    },
    {
        "id": "CC7.2",
        "category": "CC7",
        "category_label": "System Operations",
        "title": "Monitor system components for anomalous behaviour",
        "description": "The entity monitors system components and the operation of those components "
        "for anomalies. In CI/CD: observability stack, Prometheus alerting, structured logging.",
        "task_types": ["observability"],
        "dimension_keys": ["observability"],
        "evidence_keywords": ["prometheus", "grafana", "alert", "monitoring", "log", "trace"],
        "weight": 3,
    },
    {
        "id": "CC7.4",
        "category": "CC7",
        "category_label": "System Operations",
        "title": "Respond to identified security incidents",
        "description": "The entity responds to identified security incidents by executing a defined incident "
        "response program. In CI/CD: pipeline failure notifications, alert routing.",
        "task_types": ["notify"],
        "dimension_keys": ["observability"],
        "evidence_keywords": ["incident", "pagerduty", "notify", "alert", "remediate"],
        "weight": 3,
    },
    # ── CC8: Change Management ─────────────────────────────────────────────────
    {
        "id": "CC8.1",
        "category": "CC8",
        "category_label": "Change Management",
        "title": "Authorise, design and implement changes",
        "description": "The entity authorises, designs, develops or acquires, configures, documents, "
        "tests, approves and implements changes. In CI/CD: the pipeline itself IS the "
        "change management process — every deploy is tested, gated and logged.",
        "task_types": ["unit-test", "integration-test", "security-gate", "deploy"],
        "dimension_keys": [
            "unit_testing",
            "integration_testing",
            "security_gates",
            "environment_promotion",
        ],
        "evidence_keywords": ["test", "gate", "approve", "deploy", "smoke"],
        "weight": 4,
    },
    # ── CC9: Risk Mitigation ───────────────────────────────────────────────────
    {
        "id": "CC9.1",
        "category": "CC9",
        "category_label": "Risk Mitigation",
        "title": "Risk mitigation activities",
        "description": "The entity identifies, selects and develops risk mitigation activities for risks "
        "arising from potential business disruptions. In CI/CD: canary deployments, "
        "smoke tests, rollback capability.",
        "task_types": ["smoke-test", "deploy"],
        "dimension_keys": ["smoke_testing", "environment_promotion"],
        "evidence_keywords": ["smoke", "canary", "rollback", "blue-green", "healthcheck"],
        "weight": 3,
    },
    {
        "id": "CC9.2",
        "category": "CC9",
        "category_label": "Risk Mitigation",
        "title": "Vendor and business partner risk assessment",
        "description": "The entity assesses and manages risks associated with vendors and business partners. "
        "In CI/CD: SCA, SBOM, supply chain security, dependency pinning.",
        "task_types": ["sca", "supply-chain"],
        "dimension_keys": ["sca", "supply_chain"],
        "evidence_keywords": ["sbom", "dependency", "supply-chain", "sca", "audit"],
        "weight": 3,
    },
]

# ── ACF Control Domains ────────────────────────────────────────────────────────
# Based on the Australian Government ICT Security Policy Framework and
# APRA CPS 234 Information Security, mapped to CI/CD pipeline controls.

ACF_DOMAINS: list[dict] = [
    {
        "id": "ACF-GOV-1",
        "domain": "Governance",
        "title": "Security governance and accountability",
        "description": "Security governance structures are in place with clear accountability. "
        "Pipeline evidence: RBAC role bindings, audit trail, approval gates, "
        "release sign-off process.",
        "task_types": ["security-gate", "compliance-check"],
        "dimension_keys": ["security_gates", "compliance_as_code"],
        "evidence_keywords": ["approval", "governance", "sign-off", "rbac", "policy"],
        "weight": 4,
    },
    {
        "id": "ACF-GOV-2",
        "domain": "Governance",
        "title": "Risk management",
        "description": "Risks are identified, assessed and treated. Pipeline evidence: SAST, SCA, "
        "DAST, vulnerability management tasks in pipeline.",
        "task_types": ["sast", "sca", "dast", "vuln-management"],
        "dimension_keys": ["sast", "sca", "dast", "vulnerability_management"],
        "evidence_keywords": ["risk", "vulnerability", "scan", "assess"],
        "weight": 4,
    },
    {
        "id": "ACF-PROC-1",
        "domain": "Processes",
        "title": "Change and release management",
        "description": "Changes are controlled, tested and approved before deployment. "
        "Pipeline evidence: the pipeline itself — every run creates an immutable, "
        "tested, gated change record.",
        "task_types": ["unit-test", "integration-test", "deploy"],
        "dimension_keys": ["unit_testing", "integration_testing", "environment_promotion"],
        "evidence_keywords": ["test", "deploy", "gate", "promote", "release"],
        "weight": 4,
    },
    {
        "id": "ACF-PROC-2",
        "domain": "Processes",
        "title": "Vulnerability and patch management",
        "description": "Vulnerabilities are identified, prioritised and remediated within SLA. "
        "Pipeline evidence: SCA dependency scanning, container scanning, CVE checking.",
        "task_types": ["sca", "container-scan", "vuln-management"],
        "dimension_keys": ["sca", "container_security", "vulnerability_management"],
        "evidence_keywords": ["patch", "cve", "vulnerability", "dependency", "trivy"],
        "weight": 4,
    },
    {
        "id": "ACF-PROC-3",
        "domain": "Processes",
        "title": "Incident detection and response",
        "description": "Security incidents are detected and responded to in a timely manner. "
        "Pipeline evidence: observability tasks, alerting, failure notifications.",
        "task_types": ["notify", "observability"],
        "dimension_keys": ["observability"],
        "evidence_keywords": ["incident", "alert", "notify", "pagerduty", "monitor"],
        "weight": 3,
    },
    {
        "id": "ACF-TECH-1",
        "domain": "Technology",
        "title": "Secure development lifecycle",
        "description": "Software is developed securely using consistent, tested processes. "
        "Pipeline evidence: SAST, code coverage, unit tests, linting, peer review gates.",
        "task_types": ["sast", "unit-test", "code-coverage", "lint"],
        "dimension_keys": ["sast", "unit_testing", "code_coverage"],
        "evidence_keywords": ["sast", "lint", "test", "coverage", "secure-dev"],
        "weight": 4,
    },
    {
        "id": "ACF-TECH-2",
        "domain": "Technology",
        "title": "Hardened infrastructure and container security",
        "description": "Infrastructure is configured to a hardened baseline. Pipeline evidence: "
        "IaC scanning, container image scanning, CIS benchmark checks.",
        "task_types": ["iac-scan", "container-scan", "compliance-check"],
        "dimension_keys": ["iac_security", "container_security", "compliance_as_code"],
        "evidence_keywords": ["terraform", "checkov", "trivy", "container", "iac", "cis"],
        "weight": 3,
    },
    {
        "id": "ACF-INFO-1",
        "domain": "Information",
        "title": "Data classification and protection",
        "description": "Sensitive information is identified, classified and protected. "
        "Pipeline evidence: secret scanning, vault integration, masked secrets in logs.",
        "task_types": ["secret-scan"],
        "dimension_keys": ["secret_scanning"],
        "evidence_keywords": ["secret", "vault", "credential", "classify", "mask"],
        "weight": 4,
    },
    {
        "id": "ACF-INFO-2",
        "domain": "Information",
        "title": "Audit logging and log integrity",
        "description": "Audit logs are generated, protected and retained. Pipeline evidence: "
        "immutable run audit trail, structured task logs, output JSON capture.",
        "task_types": ["observability"],
        "dimension_keys": ["observability"],
        "evidence_keywords": ["audit", "log", "trail", "immutable", "retention"],
        "weight": 4,
    },
    {
        "id": "ACF-SUPPLY-1",
        "domain": "Supply Chain",
        "title": "Software supply chain security",
        "description": "Third-party components are vetted, inventoried and monitored for vulnerabilities. "
        "Pipeline evidence: SBOM generation, artifact signing, SCA scanning, Dependency-Track.",
        "task_types": ["sca", "supply-chain"],
        "dimension_keys": ["sca", "supply_chain"],
        "evidence_keywords": ["sbom", "cosign", "supply-chain", "sca", "dependency", "provenance"],
        "weight": 4,
    },
    {
        "id": "ACF-SUPPLY-2",
        "domain": "Supply Chain",
        "title": "Artifact integrity and provenance",
        "description": "Artifacts are signed and their provenance can be verified. "
        "Pipeline evidence: cosign signing, Sigstore, SLSA provenance attestation.",
        "task_types": ["supply-chain", "artifact"],
        "dimension_keys": ["supply_chain", "artifact_management"],
        "evidence_keywords": ["cosign", "sigstore", "slsa", "provenance", "attestation", "sign"],
        "weight": 3,
    },
    {
        "id": "ACF-PERF-1",
        "domain": "Performance & Reliability",
        "title": "Performance and capacity testing",
        "description": "Systems are tested for performance and capacity before deployment. "
        "Pipeline evidence: load test, stress test, benchmark tasks in pipeline.",
        "task_types": ["perf-test"],
        "dimension_keys": ["performance_testing"],
        "evidence_keywords": ["load", "performance", "k6", "jmeter", "gatling", "benchmark"],
        "weight": 2,
    },
    {
        "id": "ACF-PERF-2",
        "domain": "Performance & Reliability",
        "title": "Smoke and health checks post-deployment",
        "description": "Systems are verified as healthy after deployment. Pipeline evidence: "
        "smoke test, health check, readyz endpoint verification.",
        "task_types": ["smoke-test"],
        "dimension_keys": ["smoke_testing"],
        "evidence_keywords": ["smoke", "health", "healthcheck", "readyz", "curl"],
        "weight": 3,
    },
    {
        "id": "ACF-API-1",
        "domain": "Technology",
        "title": "API security and contract testing",
        "description": "APIs are tested for security vulnerabilities and conformance to specification. "
        "Pipeline evidence: OpenAPI validation, OWASP API security checks, contract tests.",
        "task_types": ["api-security"],
        "dimension_keys": ["api_security"],
        "evidence_keywords": ["openapi", "spectral", "api-security", "contract", "owasp-api"],
        "weight": 3,
    },
]


# ── Evidence extraction ────────────────────────────────────────────────────────

import json as _json  # noqa: E402


def _extract_task_type_set(run: Any) -> set[str]:
    """Extract all task_type tags seen across all task runs in a pipeline run."""
    tags: set[str] = set()
    for sr in run.stage_runs or []:
        for tr in sr.task_runs or []:
            raw = getattr(tr, "task_type", "") or ""
            for t in raw.split(","):
                t = t.strip().lower()
                if t:
                    tags.add(t)
    return tags


def _extract_all_text(run: Any) -> str:
    """Concatenate all task names, logs, and output_json for keyword matching."""
    parts = []
    for sr in run.stage_runs or []:
        for tr in sr.task_runs or []:
            parts.append(getattr(tr, "task_name", "") or "")
            parts.append(getattr(tr, "logs", "") or "")
            parts.append(getattr(tr, "output_json", "") or "")
    return " ".join(parts).lower()


def _build_artifact_evidences(
    run: Any, keywords: list[str], required_types: set[str]
) -> list[dict]:
    """Extract structured evidence artifacts from task runs.

    Each artifact has:
      - type: "task_run" | "log_snippet" | "output_json"
      - task_name, stage_name, status, started_at, finished_at
      - For log_snippet: the matching lines (up to 5) around each keyword hit
      - For output_json: the parsed JSON output of the task
    """
    artifacts: list[dict] = []
    kw_lower = [k.lower() for k in keywords]
    type_lower = {t.lower() for t in required_types}

    for sr in run.stage_runs or []:
        stage_name = getattr(sr, "stage_name", "") or sr.stage_id
        for tr in sr.task_runs or []:
            task_name = getattr(tr, "task_name", "") or tr.task_id
            task_type_raw = (getattr(tr, "task_type", "") or "").lower()
            task_types = {t.strip() for t in task_type_raw.split(",") if t.strip()}
            logs = getattr(tr, "logs", "") or ""
            output_json_raw = getattr(tr, "output_json", "") or ""
            status = getattr(tr, "status", "Unknown")
            started_at = getattr(tr, "started_at", None)
            finished_at = getattr(tr, "finished_at", None)
            exit_code = getattr(tr, "return_code", None)

            task_text = f"{task_name} {logs} {output_json_raw}".lower()
            type_match = bool(task_types & type_lower) if type_lower else False
            kw_match = any(kw in task_text for kw in kw_lower)

            if not (type_match or kw_match):
                continue

            # Base task run artifact
            artifact: dict[str, Any] = {
                "type": "task_run",
                "task_id": getattr(tr, "task_id", ""),
                "task_run_id": getattr(tr, "id", ""),
                "task_name": task_name,
                "stage_name": stage_name,
                "task_type": task_type_raw or "—",
                "status": status,
                "exit_code": exit_code,
                "started_at": started_at.isoformat() if started_at else None,
                "finished_at": finished_at.isoformat() if finished_at else None,
                "matched_types": sorted(task_types & type_lower) if type_lower else [],
                "matched_keywords": [kw for kw in kw_lower if kw in task_text][:5],
                "log_snippets": [],
                "output_json": None,
            }

            # Extract log snippets — lines containing matching keywords (up to 5 lines each kw, max 10 total)
            if logs and kw_match:
                log_lines = logs.splitlines()
                seen_lines: set[int] = set()
                snippets: list[str] = []
                for kw in kw_lower:
                    if kw not in logs.lower():
                        continue
                    for i, line in enumerate(log_lines):
                        if kw in line.lower() and i not in seen_lines:
                            # Include ±1 context line
                            start = max(0, i - 1)
                            end = min(len(log_lines), i + 2)
                            for j in range(start, end):
                                if j not in seen_lines:
                                    seen_lines.add(j)
                                    cleaned = log_lines[j].strip()
                                    if cleaned:
                                        snippets.append(cleaned[:200])
                            if len(snippets) >= 10:
                                break
                    if len(snippets) >= 10:
                        break
                artifact["log_snippets"] = snippets[:10]

            # Extract output JSON
            if output_json_raw:
                try:
                    parsed = _json.loads(output_json_raw)
                    # Only include if it has meaningful keys (not just empty)
                    if isinstance(parsed, dict) and parsed:
                        # Limit to first 10 keys for readability
                        limited = {k: v for i, (k, v) in enumerate(parsed.items()) if i < 10}
                        artifact["output_json"] = limited
                    elif isinstance(parsed, list) and parsed:
                        artifact["output_json"] = parsed[:5]
                except Exception:
                    if output_json_raw.strip():
                        artifact["output_json"] = {"raw": output_json_raw[:300]}

            artifacts.append(artifact)

    return artifacts


def _score_control(
    control: dict,
    task_types_present: set[str],
    full_text: str,
    pipeline_dimensions: dict[str, int] | None,
    run_status: str,
    run: Any = None,
) -> dict:
    """Evaluate a single control against pipeline run evidence."""
    required_types = set(control.get("task_types", []))
    dim_keys = control.get("dimension_keys", [])
    keywords = control.get("evidence_keywords", [])

    # Evidence signals
    type_hit = bool(required_types & task_types_present) if required_types else False
    keyword_hit = any(kw in full_text for kw in keywords) if keywords else False
    dim_score = 0
    if pipeline_dimensions:
        for dk in dim_keys:
            dim_score = max(dim_score, pipeline_dimensions.get(dk, 0))

    # Structured evidence artifacts from actual task runs
    artifacts: list[dict] = []
    if run is not None and (type_hit or keyword_hit):
        try:
            artifacts = _build_artifact_evidences(run, keywords, required_types)
        except Exception:
            pass

    # Human-readable evidence lines
    evidences: list[str] = []
    if type_hit:
        matched = sorted(required_types & task_types_present)
        evidences.append(f"Task type tag(s) found in pipeline: {', '.join(matched)}")
    if artifacts:
        for a in artifacts[:3]:
            status_icon = "✅" if a["status"] in ("Succeeded", "Warning") else "❌"
            evidences.append(
                f"{status_icon} Task '{a['task_name']}' (stage: {a['stage_name']}, "
                f"type: {a['task_type']}, status: {a['status']})"
            )
    elif keyword_hit:
        matched_kws = [kw for kw in keywords if kw in full_text][:3]
        evidences.append(f"Keyword match in run logs/output: {', '.join(matched_kws)}")
    if dim_score >= 3:
        evidences.append(f"DevSecOps dimension enforced (maturity score {dim_score}/3)")
    elif dim_score == 2:
        evidences.append(f"DevSecOps dimension configured (maturity score {dim_score}/3)")
    elif dim_score == 1:
        evidences.append(f"DevSecOps dimension partially met (maturity score {dim_score}/3)")

    if run_status in ("Failed", "Cancelled"):
        evidences.append(f"Note: pipeline run ended with status={run_status}")

    # Confidence
    if type_hit and dim_score >= 2:
        confidence = "confirmed"
    elif type_hit or (keyword_hit and dim_score >= 1):
        confidence = "partial"
    elif keyword_hit:
        confidence = "partial"
    elif not required_types and not keywords:
        confidence = "manual"
    else:
        confidence = "not_met"

    # If pipeline itself failed, max out at partial for anything that matched
    if run_status in ("Failed",) and confidence == "confirmed":
        confidence = "partial"
        evidences.append("Pipeline run did not complete successfully — evidence is indicative only")

    return {
        **{k: v for k, v in control.items() if k not in ("evidence_keywords",)},
        "confidence": confidence,
        "evidences": evidences,
        "artifacts": artifacts,
        "dim_score": dim_score,
    }


def _confidence_label(c: str) -> str:
    return {
        "confirmed": "Confirmed",
        "partial": "Partial",
        "manual": "Manual review",
        "not_met": "Not met",
    }.get(c, c)


def _overall_rating(controls: list[dict]) -> str:
    counts = {"confirmed": 0, "partial": 0, "manual": 0, "not_met": 0}
    for c in controls:
        counts[c["confidence"]] = counts.get(c["confidence"], 0) + 1
    total = len(controls)
    if total == 0:
        return "No Controls"
    confirmed_pct = counts["confirmed"] / total
    not_met_pct = counts["not_met"] / total
    if not_met_pct > 0.3:
        return "Significant Gaps"
    if confirmed_pct >= 0.7:
        return "Largely Effective"
    if confirmed_pct >= 0.4:
        return "Partially Effective"
    return "Needs Improvement"


# ── Active controls loader ─────────────────────────────────────────────────────


def _get_active_controls(framework: str, builtin_list: list[dict]) -> list[dict]:
    """Return the merged + filtered list of controls for a framework.

    Applies DB overrides (enabled flag, field overrides, custom controls).
    Falls back to the built-in list if the DB is unavailable.
    """
    import json as _j

    try:
        from app.models.framework_control import FrameworkControl

        overrides = {r.id: r for r in FrameworkControl.query.filter_by(framework=framework).all()}
    except Exception:
        return builtin_list  # DB not available — use defaults

    result: list[dict] = []
    builtin_ids: set[str] = set()

    for b in builtin_list:
        ctrl_id = b["id"]
        builtin_ids.add(ctrl_id)
        row = overrides.get(ctrl_id)
        if row and not row.enabled:
            continue  # disabled — skip
        if row:
            merged = dict(b)
            if row.title is not None:
                merged["title"] = row.title
            if row.description is not None:
                merged["description"] = row.description
            if row.category is not None:
                merged["category"] = row.category
            if row.category_label is not None:
                merged["category_label"] = row.category_label
            if row.task_types_json is not None:
                merged["task_types"] = _j.loads(row.task_types_json)
            if row.dimension_keys_json is not None:
                merged["dimension_keys"] = _j.loads(row.dimension_keys_json)
            if row.evidence_keywords_json is not None:
                merged["evidence_keywords"] = _j.loads(row.evidence_keywords_json)
            if row.weight is not None:
                merged["weight"] = row.weight
            result.append(merged)
        else:
            result.append(b)

    # Custom (non-builtin) controls added by users
    for row in overrides.values():
        if row.id not in builtin_ids and row.enabled:
            result.append(
                {
                    "id": row.id,
                    "category": row.category or row.id,
                    "category_label": row.category_label or row.category or row.id,
                    "title": row.title or row.id,
                    "description": row.description or "",
                    "task_types": _j.loads(row.task_types_json) if row.task_types_json else [],
                    "dimension_keys": _j.loads(row.dimension_keys_json)
                    if row.dimension_keys_json
                    else [],
                    "evidence_keywords": _j.loads(row.evidence_keywords_json)
                    if row.evidence_keywords_json
                    else [],
                    "weight": row.weight or 2,
                }
            )

    return result


# ── Public API ────────────────────────────────────────────────────────────────


def build_isae_report(run_id: str) -> dict:
    """Generate an ISAE 3000 / SOC 2 TSC report for a PipelineRun."""
    from sqlalchemy.orm import joinedload

    from app.models.pipeline import Pipeline, Stage
    from app.models.run import PipelineRun

    run = (
        PipelineRun.query.options(
            joinedload(PipelineRun.stage_runs),
        )
        .filter_by(id=run_id)
        .first_or_404()
    )

    # Load pipeline with its stages and tasks to get task_type info
    pipeline = (
        Pipeline.query.options(joinedload(Pipeline.stages).joinedload(Stage.tasks))
        .filter_by(id=run.pipeline_id)
        .first()
    )

    # Load maturity dimension scores
    pipeline_dimensions: dict[str, int] = {}
    if pipeline:
        try:
            from app.services.maturity_service import (
                DIMENSIONS,
                _applicable_dimensions,
                _score_pipeline_dimension,
            )

            applicable = {k for k, _ in _applicable_dimensions(pipeline.kind or "ci")}
            for key, cfg in DIMENSIONS.items():
                d = _score_pipeline_dimension(pipeline, key, cfg, applicable=(key in applicable))
                pipeline_dimensions[key] = d["score"]
        except Exception:
            pass

    # Enrich stage_runs with task_type from the pipeline definition
    task_type_map: dict[str, str] = {}
    if pipeline:
        for stage in pipeline.stages or []:
            for task in stage.tasks or []:
                task_type_map[task.id] = task.task_type or ""

    for sr in run.stage_runs or []:
        for tr in sr.task_runs or []:
            if not getattr(tr, "task_type", None):
                tr.task_type = task_type_map.get(tr.task_id, "")

    task_types = _extract_task_type_set(run)
    full_text = _extract_all_text(run)

    active_criteria = _get_active_controls("isae", SOC2_CRITERIA)
    controls = [
        _score_control(c, task_types, full_text, pipeline_dimensions, run.status, run=run)
        for c in active_criteria
    ]

    # Group by category
    categories: dict[str, list] = {}
    for ctrl in controls:
        cat = ctrl["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(ctrl)

    overall = _overall_rating(controls)
    confirmed = sum(1 for c in controls if c["confidence"] == "confirmed")
    partial = sum(1 for c in controls if c["confidence"] == "partial")
    not_met = sum(1 for c in controls if c["confidence"] == "not_met")
    manual = sum(1 for c in controls if c["confidence"] == "manual")

    return {
        "framework": "ISAE 3000 / SOC 2 Type II (Trust Service Criteria)",
        "run_id": run.id,
        "pipeline_id": run.pipeline_id,
        "pipeline_name": getattr(pipeline, "name", run.pipeline_id)
        if pipeline
        else run.pipeline_id,
        "run_status": run.status,
        "run_started_at": run.started_at.isoformat() if run.started_at else None,
        "generated_at": datetime.now(UTC).isoformat(),
        "overall_rating": overall,
        "summary": {
            "total": len(controls),
            "confirmed": confirmed,
            "partial": partial,
            "not_met": not_met,
            "manual": manual,
        },
        "categories": {
            k: {
                "label": v[0]["category_label"] if v else k,
                "controls": v,
            }
            for k, v in sorted(categories.items())
        },
        "controls": controls,
    }


def build_acf_report(run_id: str) -> dict:
    """Generate an ACF (Australian Assurance/Compliance Framework) report for a PipelineRun."""
    from sqlalchemy.orm import joinedload

    from app.models.pipeline import Pipeline, Stage
    from app.models.run import PipelineRun

    run = (
        PipelineRun.query.options(joinedload(PipelineRun.stage_runs))
        .filter_by(id=run_id)
        .first_or_404()
    )

    pipeline = (
        Pipeline.query.options(joinedload(Pipeline.stages).joinedload(Stage.tasks))
        .filter_by(id=run.pipeline_id)
        .first()
    )

    pipeline_dimensions: dict[str, int] = {}
    if pipeline:
        try:
            from app.services.maturity_service import (
                DIMENSIONS,
                _applicable_dimensions,
                _score_pipeline_dimension,
            )

            applicable = {k for k, _ in _applicable_dimensions(pipeline.kind or "ci")}
            for key, cfg in DIMENSIONS.items():
                d = _score_pipeline_dimension(pipeline, key, cfg, applicable=(key in applicable))
                pipeline_dimensions[key] = d["score"]
        except Exception:
            pass

    task_type_map: dict[str, str] = {}
    if pipeline:
        for stage in pipeline.stages or []:
            for task in stage.tasks or []:
                task_type_map[task.id] = task.task_type or ""

    for sr in run.stage_runs or []:
        for tr in sr.task_runs or []:
            if not getattr(tr, "task_type", None):
                tr.task_type = task_type_map.get(tr.task_id, "")

    task_types = _extract_task_type_set(run)
    full_text = _extract_all_text(run)

    active_domains = _get_active_controls("acf", ACF_DOMAINS)
    controls = [
        _score_control(c, task_types, full_text, pipeline_dimensions, run.status, run=run)
        for c in active_domains
    ]

    domains: dict[str, list] = {}
    for ctrl in controls:
        d = ctrl["domain"]
        if d not in domains:
            domains[d] = []
        domains[d].append(ctrl)

    overall = _overall_rating(controls)
    confirmed = sum(1 for c in controls if c["confidence"] == "confirmed")
    partial = sum(1 for c in controls if c["confidence"] == "partial")
    not_met = sum(1 for c in controls if c["confidence"] == "not_met")
    manual = sum(1 for c in controls if c["confidence"] == "manual")

    return {
        "framework": "ACF — Australian Assurance & Compliance Framework (APRA CPS 234 / ASD ISM)",
        "run_id": run.id,
        "pipeline_id": run.pipeline_id,
        "pipeline_name": getattr(pipeline, "name", run.pipeline_id)
        if pipeline
        else run.pipeline_id,
        "run_status": run.status,
        "run_started_at": run.started_at.isoformat() if run.started_at else None,
        "generated_at": datetime.now(UTC).isoformat(),
        "overall_rating": overall,
        "summary": {
            "total": len(controls),
            "confirmed": confirmed,
            "partial": partial,
            "not_met": not_met,
            "manual": manual,
        },
        "domains": {k: {"controls": v} for k, v in sorted(domains.items())},
        "controls": controls,
    }
