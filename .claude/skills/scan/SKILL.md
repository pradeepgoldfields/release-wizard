---
name: scan
description: Run security scans on the Conduit codebase — SAST, SCA, or both. Reports findings grouped by severity.
argument-hint: "[sast|sca|all]"
---

# Security Scan — Conduit

Scan type: **$ARGUMENTS** (defaults to `all` if empty)

## SAST — Static Application Security Testing

Delegates to the `sast-scanner` agent. That agent:
1. Scans `app/` Python source for injection, XSS, insecure deserialization, hardcoded secrets
2. Scans `app/static/js/` for `innerHTML` XSS, `eval()`, exposed tokens
3. Scans `Dockerfile`, `Jenkinsfile`, Helm values for secrets in IaC

```bash
source venv/Scripts/activate

# Bandit — Python SAST
pip install bandit -q
bandit -r app/ -ll -f txt 2>&1

# Gitleaks — secret scanning
gitleaks detect --source . --no-git 2>&1 || true
```

## SCA — Software Composition Analysis

Delegates to the `sca-scanner` agent. That agent:
1. Checks all packages in `requirements.txt` and `requirements-dev.txt` for CVEs
2. Reports licence issues
3. Lists packages more than 2 major versions behind

```bash
source venv/Scripts/activate

pip install safety pip-audit pip-licenses -q

# CVE check
safety check -r requirements.txt 2>&1

# Licence audit
pip-licenses --format=table --order=license 2>&1
```

## Report format

```
## Security Scan — <date>

### SAST Findings
<findings from sast-scanner agent>

### SCA Findings
<findings from sca-scanner agent>

### Overall Status
🔴 Critical issues found — must fix before merge
🟡 High/medium issues — review before merge
🟢 Clean — no significant findings
```
