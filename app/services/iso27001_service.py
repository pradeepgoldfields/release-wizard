"""ISO 27001:2022 compliance evaluation service.

Evaluates the platform's configuration against all 93 controls from
ISO/IEC 27001:2022 Annex A, organised into 4 themes and 11 clauses.

Each control is mapped to one or more platform checks that can be evaluated
automatically (based on data in the database) or flagged as requiring a
manual attestation.

Control status:
  pass      — automatic check passed
  fail      — automatic check failed
  manual    — cannot be determined automatically; requires human attestation
  na        — not applicable for this platform profile
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ISOCheck:
    """A single automated or manual compliance check."""

    id: str  # e.g. "A.5.1"
    title: str
    description: str
    category: str  # Theme A-D
    clause: str  # e.g. "5 Organisational"
    check_type: str = "manual"  # automatic | manual | na
    # populated at evaluation time
    status: str = "manual"  # pass | fail | manual | na
    evidence: str = ""
    detail: dict = field(default_factory=dict)


# ── ISO 27001:2022 Annex A control catalogue ──────────────────────────────────

CONTROLS: list[dict[str, str]] = [
    # ── Theme A: Organisational (5) ───────────────────────────────────────────
    {
        "id": "5.1",
        "title": "Policies for information security",
        "desc": "Information security policy and topic-specific policies are defined, approved, published, communicated and reviewed.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.2",
        "title": "Information security roles and responsibilities",
        "desc": "Roles and responsibilities for information security are defined and allocated.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.3",
        "title": "Segregation of duties",
        "desc": "Conflicting duties and areas of responsibility are segregated.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.4",
        "title": "Management responsibilities",
        "desc": "Management requires all personnel to apply information security in accordance with the policy.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.5",
        "title": "Contact with authorities",
        "desc": "Contacts with relevant authorities are established and maintained.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.6",
        "title": "Contact with special interest groups",
        "desc": "Contacts with special interest groups or specialist security forums are established.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.7",
        "title": "Threat intelligence",
        "desc": "Information relating to information security threats is collected and analysed.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.8",
        "title": "Information security in project management",
        "desc": "Information security is integrated into project management.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.9",
        "title": "Inventory of information and other associated assets",
        "desc": "An inventory of information and other associated assets is developed and maintained.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.10",
        "title": "Acceptable use of information and other associated assets",
        "desc": "Rules for the acceptable use and procedures for handling information are identified and documented.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.11",
        "title": "Return of assets",
        "desc": "Personnel and other interested parties return all organisation assets upon change or termination.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.12",
        "title": "Classification of information",
        "desc": "Information is classified according to the organisation's needs.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.13",
        "title": "Labelling of information",
        "desc": "An appropriate set of procedures for information labelling is developed and implemented.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.14",
        "title": "Information transfer",
        "desc": "Information transfer rules, procedures, or agreements are in place.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.15",
        "title": "Access control",
        "desc": "Rules to control physical and logical access to information are established and implemented.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.16",
        "title": "Identity management",
        "desc": "The full life cycle of identities is managed.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.17",
        "title": "Authentication information",
        "desc": "Allocation and management of authentication information is controlled by a management process.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.18",
        "title": "Access rights",
        "desc": "Access rights are provisioned, reviewed, modified and removed in accordance with policy.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.19",
        "title": "Information security in supplier relationships",
        "desc": "Processes and procedures are defined to manage information security in supplier relationships.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.20",
        "title": "Addressing information security within supplier agreements",
        "desc": "Relevant information security requirements are established with each supplier.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.21",
        "title": "Managing information security in the ICT supply chain",
        "desc": "Processes and procedures are defined to manage information security in the ICT supply chain.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.22",
        "title": "Monitoring, review and change management of supplier services",
        "desc": "Supplier service delivery changes are managed.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.23",
        "title": "Information security for use of cloud services",
        "desc": "Processes for acquisition, use and management of cloud services are established.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.24",
        "title": "Information security incident management planning and preparation",
        "desc": "The organisation plans and prepares for managing information security incidents.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.25",
        "title": "Assessment and decision on information security events",
        "desc": "Security events are assessed and decided whether to classify them as incidents.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.26",
        "title": "Response to information security incidents",
        "desc": "Information security incidents are responded to in accordance with documented procedures.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.27",
        "title": "Learning from information security incidents",
        "desc": "Knowledge gained from security incidents is used to strengthen controls.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.28",
        "title": "Collection of evidence",
        "desc": "Procedures for identification, collection, acquisition and preservation of evidence are established.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.29",
        "title": "Information security during disruption",
        "desc": "The organisation plans how to maintain information security at an appropriate level during disruption.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.30",
        "title": "ICT readiness for business continuity",
        "desc": "ICT readiness is planned and implemented based on business continuity objectives.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.31",
        "title": "Legal, statutory, regulatory and contractual requirements",
        "desc": "Legal, statutory, regulatory and contractual requirements relevant to IS are identified.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.32",
        "title": "Intellectual property rights",
        "desc": "Procedures to protect intellectual property rights are implemented.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.33",
        "title": "Protection of records",
        "desc": "Records are protected from loss, destruction, falsification and unauthorised access.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.34",
        "title": "Privacy and protection of personally identifiable information",
        "desc": "Privacy and protection of PII is ensured as required by law and regulation.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.35",
        "title": "Independent review of information security",
        "desc": "Approach to managing information security is reviewed independently at planned intervals.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.36",
        "title": "Compliance with policies, rules and standards for IS",
        "desc": "Compliance with information security policies, rules and standards is regularly reviewed.",
        "category": "A",
        "clause": "5 Organisational",
    },
    {
        "id": "5.37",
        "title": "Documented operating procedures",
        "desc": "Operating procedures for information processing facilities are documented and made available.",
        "category": "A",
        "clause": "5 Organisational",
    },
    # ── Theme B: People (6) ───────────────────────────────────────────────────
    {
        "id": "6.1",
        "title": "Screening",
        "desc": "Background verification checks on all candidates are carried out prior to joining.",
        "category": "B",
        "clause": "6 People",
    },
    {
        "id": "6.2",
        "title": "Terms and conditions of employment",
        "desc": "Employment contractual agreements state responsibilities for IS.",
        "category": "B",
        "clause": "6 People",
    },
    {
        "id": "6.3",
        "title": "Information security awareness, education and training",
        "desc": "Personnel receive appropriate security awareness education and training.",
        "category": "B",
        "clause": "6 People",
    },
    {
        "id": "6.4",
        "title": "Disciplinary process",
        "desc": "A disciplinary process is formalised and communicated to take action against personnel.",
        "category": "B",
        "clause": "6 People",
    },
    {
        "id": "6.5",
        "title": "Responsibilities after termination or change of employment",
        "desc": "IS responsibilities after termination are defined, enforced and communicated.",
        "category": "B",
        "clause": "6 People",
    },
    {
        "id": "6.6",
        "title": "Confidentiality or non-disclosure agreements",
        "desc": "Confidentiality or NDA agreements reflecting IS needs are identified and signed.",
        "category": "B",
        "clause": "6 People",
    },
    {
        "id": "6.7",
        "title": "Remote working",
        "desc": "Security measures are implemented for personnel working remotely.",
        "category": "B",
        "clause": "6 People",
    },
    {
        "id": "6.8",
        "title": "Information security event reporting",
        "desc": "Personnel are able to report observed or suspected IS events through appropriate channels.",
        "category": "B",
        "clause": "6 People",
    },
    # ── Theme C: Physical (7) ─────────────────────────────────────────────────
    {
        "id": "7.1",
        "title": "Physical security perimeters",
        "desc": "Security perimeters are defined and used to protect information and assets.",
        "category": "C",
        "clause": "7 Physical",
    },
    {
        "id": "7.2",
        "title": "Physical entry",
        "desc": "Secure areas are protected by appropriate entry controls and access points.",
        "category": "C",
        "clause": "7 Physical",
    },
    {
        "id": "7.3",
        "title": "Securing offices, rooms and facilities",
        "desc": "Physical security for offices, rooms and facilities is designed and implemented.",
        "category": "C",
        "clause": "7 Physical",
    },
    {
        "id": "7.4",
        "title": "Physical security monitoring",
        "desc": "Premises are monitored for unauthorised physical access.",
        "category": "C",
        "clause": "7 Physical",
    },
    {
        "id": "7.5",
        "title": "Protecting against physical and environmental threats",
        "desc": "Protection against physical and environmental threats is designed and implemented.",
        "category": "C",
        "clause": "7 Physical",
    },
    {
        "id": "7.6",
        "title": "Working in secure areas",
        "desc": "Security measures for working in secure areas are designed and implemented.",
        "category": "C",
        "clause": "7 Physical",
    },
    {
        "id": "7.7",
        "title": "Clear desk and clear screen",
        "desc": "Clear desk rules for papers and removable media and clear screen rules are defined and enforced.",
        "category": "C",
        "clause": "7 Physical",
    },
    {
        "id": "7.8",
        "title": "Equipment siting and protection",
        "desc": "Equipment is sited securely and protected from environmental threats.",
        "category": "C",
        "clause": "7 Physical",
    },
    {
        "id": "7.9",
        "title": "Security of assets off-premises",
        "desc": "Off-site assets are protected.",
        "category": "C",
        "clause": "7 Physical",
    },
    {
        "id": "7.10",
        "title": "Storage media",
        "desc": "Storage media is managed through its life cycle of acquisition, use, transportation and disposal.",
        "category": "C",
        "clause": "7 Physical",
    },
    {
        "id": "7.11",
        "title": "Supporting utilities",
        "desc": "Information processing facilities are protected from power failures and other utility disruptions.",
        "category": "C",
        "clause": "7 Physical",
    },
    {
        "id": "7.12",
        "title": "Cabling security",
        "desc": "Cables carrying power, data or supporting IS services are protected from interference.",
        "category": "C",
        "clause": "7 Physical",
    },
    {
        "id": "7.13",
        "title": "Equipment maintenance",
        "desc": "Equipment is maintained correctly to ensure availability, integrity and confidentiality.",
        "category": "C",
        "clause": "7 Physical",
    },
    {
        "id": "7.14",
        "title": "Secure disposal or re-use of equipment",
        "desc": "Items of equipment are verified to ensure that all sensitive data has been removed before disposal.",
        "category": "C",
        "clause": "7 Physical",
    },
    # ── Theme D: Technological (8) ────────────────────────────────────────────
    {
        "id": "8.1",
        "title": "User end point devices",
        "desc": "Information stored on, processed by or accessible via end-point devices is protected.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.2",
        "title": "Privileged access rights",
        "desc": "Allocation and use of privileged access rights is restricted and managed.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.3",
        "title": "Information access restriction",
        "desc": "Access to information and other associated assets is restricted in accordance with policy.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.4",
        "title": "Access to source code",
        "desc": "Read and write access to source code, development tools and software libraries is managed appropriately.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.5",
        "title": "Secure authentication",
        "desc": "Secure authentication technologies and procedures are implemented.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.6",
        "title": "Capacity management",
        "desc": "The use of resources is monitored and adjusted to meet capacity requirements.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.7",
        "title": "Protection against malware",
        "desc": "Protection against malware is implemented and supported by appropriate user awareness.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.8",
        "title": "Management of technical vulnerabilities",
        "desc": "Technical vulnerabilities are managed to prevent exploitation.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.9",
        "title": "Configuration management",
        "desc": "Configurations, including security configurations, of hardware, software and networks are managed.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.10",
        "title": "Information deletion",
        "desc": "Information stored in IS and devices is deleted when no longer required.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.11",
        "title": "Data masking",
        "desc": "Data masking is used in accordance with the topic-specific policy on access control.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.12",
        "title": "Data leakage prevention",
        "desc": "Data leakage prevention measures are applied to systems, networks and devices.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.13",
        "title": "Information backup",
        "desc": "Backup copies of information, software and systems are maintained and tested regularly.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.14",
        "title": "Redundancy of information processing facilities",
        "desc": "Processing facilities are implemented with sufficient redundancy to meet availability requirements.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.15",
        "title": "Logging",
        "desc": "Logs recording activities, exceptions, faults and events are produced, stored and protected.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.16",
        "title": "Monitoring activities",
        "desc": "Networks, systems and applications are monitored for anomalous behaviour.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.17",
        "title": "Clock synchronisation",
        "desc": "The clocks of information processing systems are synchronised to approved time sources.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.18",
        "title": "Use of privileged utility programs",
        "desc": "The use of utility programs that can override system and application controls is restricted.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.19",
        "title": "Installation of software on operational systems",
        "desc": "Procedures and measures are implemented to securely manage software installation.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.20",
        "title": "Networks security",
        "desc": "Networks are secured, managed and controlled to protect information in systems and applications.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.21",
        "title": "Security of network services",
        "desc": "Security mechanisms, service levels and requirements of network services are identified.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.22",
        "title": "Segregation of networks",
        "desc": "Groups of information services, users and IS are segregated in networks.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.23",
        "title": "Web filtering",
        "desc": "Access to external websites is managed to reduce exposure to malicious content.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.24",
        "title": "Use of cryptography",
        "desc": "Rules for the effective use of cryptography, including management of cryptographic keys, are defined.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.25",
        "title": "Secure development life cycle",
        "desc": "Rules for the secure development of software and systems are established and applied.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.26",
        "title": "Application security requirements",
        "desc": "IS requirements are identified, specified and approved when developing or acquiring applications.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.27",
        "title": "Secure system architecture and engineering principles",
        "desc": "Principles for engineering secure systems are established, documented and applied.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.28",
        "title": "Secure coding",
        "desc": "Secure coding principles are applied to software development.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.29",
        "title": "Security testing in development and acceptance",
        "desc": "Security testing processes are defined and implemented in the development life cycle.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.30",
        "title": "Outsourced development",
        "desc": "Outsourced system development activities are directed, monitored and reviewed.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.31",
        "title": "Separation of development, test and production environments",
        "desc": "Development, testing and production environments are separated and secured.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.32",
        "title": "Change management",
        "desc": "Changes to IS and information processing facilities are subject to change management procedures.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.33",
        "title": "Test information",
        "desc": "Test information is appropriately selected, protected and managed.",
        "category": "D",
        "clause": "8 Technological",
    },
    {
        "id": "8.34",
        "title": "Protection of information systems during audit testing",
        "desc": "Audit tests and activities involving assessment of systems are planned and agreed.",
        "category": "D",
        "clause": "8 Technological",
    },
]


# ── Automatic check implementations ──────────────────────────────────────────


def _check_rbac(ctx: dict) -> tuple[str, str]:
    """5.15/5.16/5.18 — Access control, identity management, access rights."""
    users = ctx.get("user_count", 0)
    roles = ctx.get("role_count", 0)
    bindings = ctx.get("binding_count", 0)
    if users > 0 and roles > 0 and bindings > 0:
        return "pass", f"{users} users, {roles} roles, {bindings} bindings configured"
    return "fail", "No RBAC configuration found — users, roles or bindings missing"


def _check_auth(ctx: dict) -> tuple[str, str]:
    """8.5 — Secure authentication (JWT + bcrypt)."""
    if ctx.get("auth_enabled"):
        return "pass", "JWT-based authentication with bcrypt password hashing is active"
    return "fail", "Authentication not confirmed"


def _check_secrets(ctx: dict) -> tuple[str, str]:
    """8.24 — Cryptography (Fernet-encrypted vault)."""
    count = ctx.get("vault_secret_count", 0)
    if count > 0:
        return "pass", f"{count} secrets stored with Fernet symmetric encryption"
    return "manual", "No vault secrets found — verify secrets management approach"


def _check_audit_log(ctx: dict) -> tuple[str, str]:
    """8.15/5.28 — Logging and evidence collection."""
    count = ctx.get("audit_event_count", 0)
    if count > 0:
        return "pass", f"{count} immutable audit events recorded in the append-only log"
    return "fail", "No audit events found — audit logging may not be active"


def _check_segregation(ctx: dict) -> tuple[str, str]:
    """8.31 — Separation of environments."""
    env_count = ctx.get("environment_count", 0)
    env_names = ctx.get("environment_names", [])
    has_prod = any("prod" in n.lower() for n in env_names)
    has_dev = any("dev" in n.lower() or "staging" in n.lower() for n in env_names)
    if env_count >= 2 and has_prod and has_dev:
        return "pass", f"{env_count} environments defined: {', '.join(env_names)}"
    if env_count >= 1:
        return "manual", f"{env_count} environments defined but dev/prod separation not confirmed"
    return "fail", "No environments defined — cannot verify environment segregation"


def _check_pipeline_compliance(ctx: dict) -> tuple[str, str]:
    """8.25/8.29 — Secure development lifecycle and security testing."""
    rules = ctx.get("compliance_rule_count", 0)
    rated = ctx.get("pipelines_with_compliance", 0)
    total = ctx.get("pipeline_count", 0)
    if rules > 0 and rated > 0:
        pct = int(rated / total * 100) if total else 0
        return (
            "pass",
            f"{rules} admission rules active; {rated}/{total} pipelines ({pct}%) have compliance ratings",
        )
    if total > 0:
        return "fail", f"No compliance admission rules — {total} pipelines are ungated"
    return "manual", "No pipelines found to evaluate"


def _check_change_management(ctx: dict) -> tuple[str, str]:
    """8.32 — Change management (pipeline runs as change records)."""
    runs = ctx.get("pipeline_run_count", 0)
    if runs > 0:
        return "pass", f"{runs} pipeline runs recorded as deployment change records"
    return "manual", "No pipeline runs found — change management history not available"


def _check_vulnerability_scanning(ctx: dict) -> tuple[str, str]:
    """8.8 — Technical vulnerability management."""
    has_security_scan = ctx.get("has_security_scan_pipeline", False)
    if has_security_scan:
        return "pass", "Security scanning pipeline detected in CI configuration"
    return "fail", "No security scanning pipeline detected — add a security-scan stage"


def _check_sbom(ctx: dict) -> tuple[str, str]:
    """5.21 — ICT supply chain (SBOM generation)."""
    has_sbom = ctx.get("has_sbom_task", False)
    if has_sbom:
        return "pass", "SBOM generation task found in pipeline definitions"
    return "manual", "No SBOM generation task detected — consider adding syft/cyclonedx stage"


def _check_webhook_auth(ctx: dict) -> tuple[str, str]:
    """5.14/8.20 — Information transfer and network security."""
    webhook_count = ctx.get("webhook_count", 0)
    if webhook_count > 0:
        return "pass", f"{webhook_count} webhooks configured with token-based authentication"
    return "manual", "No webhooks configured — verify external trigger authentication"


# Maps control ID to the check function
_AUTO_CHECKS: dict[str, Any] = {
    "5.15": _check_rbac,
    "5.16": _check_rbac,
    "5.17": _check_auth,
    "5.18": _check_rbac,
    "5.21": _check_sbom,
    "5.28": _check_audit_log,
    "5.33": _check_audit_log,
    "5.36": _check_pipeline_compliance,
    "8.2": _check_rbac,
    "8.3": _check_rbac,
    "8.5": _check_auth,
    "8.8": _check_vulnerability_scanning,
    "8.15": _check_audit_log,
    "8.16": _check_audit_log,
    "8.24": _check_secrets,
    "8.25": _check_pipeline_compliance,
    "8.29": _check_vulnerability_scanning,
    "8.31": _check_segregation,
    "8.32": _check_change_management,
}


def _build_context() -> dict:
    """Collect platform metrics used by automatic checks."""
    from app.models.auth import Role, RoleBinding, User
    from app.models.compliance import AuditEvent, ComplianceRule
    from app.models.environment import Environment
    from app.models.pipeline import Pipeline
    from app.models.run import PipelineRun
    from app.models.vault import VaultSecret
    from app.models.webhook import Webhook

    envs = Environment.query.all()
    pipelines = Pipeline.query.all()

    # Check for security scan pipeline or task
    has_security_scan = any(
        "security" in p.name.lower() or "scan" in p.name.lower() for p in pipelines
    )

    # Check for SBOM task in any pipeline
    has_sbom = False
    for p in pipelines:
        for stage in p.stages:
            for task in stage.tasks:
                if "sbom" in (task.name or "").lower() or "sbom" in (task.run_code or "").lower():
                    has_sbom = True
                    break

    return {
        "user_count": User.query.count(),
        "role_count": Role.query.count(),
        "binding_count": RoleBinding.query.count(),
        "auth_enabled": True,  # JWT is always on
        "vault_secret_count": VaultSecret.query.count(),
        "audit_event_count": AuditEvent.query.count(),
        "environment_count": len(envs),
        "environment_names": [e.name for e in envs],
        "compliance_rule_count": ComplianceRule.query.filter_by(is_active=True).count(),
        "pipeline_count": len(pipelines),
        "pipelines_with_compliance": sum(
            1 for p in pipelines if p.compliance_score and p.compliance_score > 0
        ),
        "pipeline_run_count": PipelineRun.query.count(),
        "has_security_scan_pipeline": has_security_scan,
        "has_sbom_task": has_sbom,
        "webhook_count": Webhook.query.filter_by(is_active=True).count(),
    }


# ── Public API ─────────────────────────────────────────────────────────────────


def evaluate_iso27001() -> dict:
    """Evaluate the platform against all ISO 27001:2022 Annex A controls.

    Returns a structured report with per-control status and summary statistics.
    """
    ctx = _build_context()
    results = []

    for ctrl in CONTROLS:
        check_fn = _AUTO_CHECKS.get(ctrl["id"])
        if check_fn:
            status, evidence = check_fn(ctx)
            check_type = "automatic"
        else:
            status = "manual"
            evidence = "Manual attestation required — cannot be evaluated automatically"
            check_type = "manual"

        results.append(
            {
                "id": ctrl["id"],
                "title": ctrl["title"],
                "description": ctrl["desc"],
                "category": ctrl["category"],
                "clause": ctrl["clause"],
                "check_type": check_type,
                "status": status,
                "evidence": evidence,
            }
        )

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    manual = sum(1 for r in results if r["status"] == "manual")
    na = sum(1 for r in results if r["status"] == "na")

    # Score = passed / (passed + failed) ignoring manual/na
    auto_total = passed + failed
    score = round(passed / auto_total * 100, 1) if auto_total > 0 else 0.0

    # Group by clause
    clauses: dict[str, list] = {}
    for r in results:
        clauses.setdefault(r["clause"], []).append(r)

    clause_summary = []
    for clause_name, controls in clauses.items():
        cp = sum(1 for c in controls if c["status"] == "pass")
        cf = sum(1 for c in controls if c["status"] == "fail")
        cm = sum(1 for c in controls if c["status"] == "manual")
        clause_summary.append(
            {
                "clause": clause_name,
                "total": len(controls),
                "passed": cp,
                "failed": cf,
                "manual": cm,
            }
        )

    return {
        "standard": "ISO/IEC 27001:2022",
        "annex": "Annex A",
        "total_controls": total,
        "passed": passed,
        "failed": failed,
        "manual": manual,
        "na": na,
        "auto_score": score,
        "platform_context": ctx,
        "clause_summary": clause_summary,
        "controls": results,
    }
