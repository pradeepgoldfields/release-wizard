# Conduit — System Administrator Guide

**Audience:** System Administrators with the `system-administrator` role
**Version:** 1.0
**Last updated:** 2026-04-01

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [First Login & Initial Setup](#2-first-login--initial-setup)
3. [User Management](#3-user-management)
4. [Roles & Permissions](#4-roles--permissions)
5. [Role Bindings (RBAC)](#5-role-bindings-rbac)
6. [Key Management](#6-key-management)
7. [Global Variables](#7-global-variables)
8. [System Settings](#8-system-settings)
9. [Framework Controls](#9-framework-controls)
10. [Monitoring](#10-monitoring)
11. [Vault (Secrets Management)](#11-vault-secrets-management)
12. [Plugins & Integrations](#12-plugins--integrations)
13. [Webhooks](#13-webhooks)
14. [Compliance Administration](#14-compliance-administration)
15. [Backup & Recovery](#15-backup--recovery)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. Introduction

Conduit is a self-hosted CI/CD orchestration and compliance platform. As a **System Administrator** you have full access to every resource and feature on the platform. This guide walks through day-to-day administration tasks: onboarding users, managing access, configuring integrations, and keeping the platform healthy.

> **Security note:** The built-in `admin` account and the `system-administrator` role cannot be deleted. Protect these credentials and rotate the JWT secret key periodically.

---

## 2. First Login & Initial Setup

### Default credentials

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `admin` |
| URL | `http://<host>:8080` |

> **Change the default password immediately** after first login via **Administration → User Management → admin → Change Password**.

### Post-install checklist

1. **Change admin password** — Administration → User Management → select `admin` → Change Password
2. **Set JWT secret key** — Administration → System → set `JWT_SECRET_KEY` to a strong random value (min 32 chars)
3. **Configure AI assistant** — Administration → Key Management → add `GROQ_API_KEY`
4. **Create environments** — Environments → New Environment (e.g. `dev`, `staging`, `production`)
5. **Seed roles** — Administration → Permissions → verify `system-administrator` and `product-admin` built-in roles exist
6. **Create your first product** — Products → New Product
7. **Invite users** — Administration → User Management → New User (or bulk import)

---

## 3. User Management

Navigate to **Administration → User Management**.

### Creating a user

1. Click **New User**
2. Fill in **Username** (required), **Email**, **Display Name**
3. Set a temporary **Password** — the user should change it on first login
4. Click **Save**
5. Assign role bindings immediately (see §5)

### Bulk import

Click **Bulk Import** to create multiple users at once from JSON or CSV.

**JSON format:**
```json
[
  {"username": "alice", "email": "alice@example.com", "display_name": "Alice Smith", "password": "temp123"},
  {"username": "bob",   "email": "bob@example.com",   "display_name": "Bob Jones",   "password": "temp123"}
]
```

**CSV format:**
```
username,email,display_name,password
alice,alice@example.com,Alice Smith,temp123
bob,bob@example.com,Bob Jones,temp123
```

> Existing usernames are silently skipped. The import summary shows how many were created vs skipped.

### Deactivating a user

Open the user → click **Edit** → toggle **Active** to off → Save. Deactivated users cannot log in but their data and bindings are preserved.

### Changing a password

Open the user → **Change Password** → enter and confirm new password. Passwords must be at least 8 characters.

### Deleting a user

Click **Delete** on the user row. Built-in users (e.g. `admin`) cannot be deleted — the button is disabled.

### LDAP users

LDAP-synced users have an **LDAP DN** field populated. Their passwords are not stored in Conduit — authentication is delegated to the directory. You can still assign role bindings to LDAP users.

---

## 4. Roles & Permissions

Navigate to **Administration → Permissions → Roles tab**.

### Built-in roles

| Role | Description |
|------|-------------|
| `system-administrator` | Full access to all resources and features |
| `product-admin` | Full control over all product resources and member access |

Built-in roles cannot be deleted (the Delete button is disabled). Their permission sets are refreshed on every platform startup.

### Creating a custom role

1. Click **New Role**
2. Enter a **Name** and optional **Description**
3. Select permissions from the grouped checkbox picker — permissions are grouped by resource (Products, Pipelines, Releases, Environments, etc.)
4. Click **Save**

### Editing a role

Open the role → adjust checkboxes → **Save**. Changes take effect on the user's next request (no logout required).

### Permission reference

| Resource | Permissions |
|----------|-------------|
| Products | `view` · `create` · `edit` · `delete` |
| Applications | `view` · `create` · `edit` · `delete` |
| Pipelines | `view` · `create` · `edit` · `delete` · `execute` · `run` |
| Releases | `view` · `create` · `edit` · `delete` · `execute` · `approve` |
| Stages | `view` · `create` · `edit` · `delete` · `execute` |
| Tasks | `view` · `create` · `edit` · `delete` · `execute` |
| Environments | `view` · `create` · `edit` · `delete` |
| Templates | `view` · `create` · `edit` · `delete` |
| Vault | `view` · `create` · `reveal` · `delete` |
| Compliance | `view` · `edit` · `approve` |
| Users | `view` · `create` · `edit` · `delete` |
| Roles | `view` · `create` · `edit` · `delete` |
| Permissions | `view` · `grant` · `revoke` · `change` |
| Global Variables | `view` · `edit` |
| Monitoring | `view` · `configure` |

---

## 5. Role Bindings (RBAC)

Navigate to **Administration → Permissions → Bindings tab**, or open a specific user and manage their bindings directly.

### Scopes

| Scope | Meaning |
|-------|---------|
| `organization` | Platform-wide — applies across all products |
| `product:<id>` | Scoped to a single product and all its children |
| `environment:<id>` | Scoped to a single environment |

### Granting access

1. Open **Administration → User Management** → select a user
2. Click **+ Add Role Binding**
3. Choose **Role**, **Scope** (organization / product / environment), and the specific resource if scoped
4. Click **Save**

### Revoking access

On the user detail page, find the binding in the Role Bindings table → click **Revoke**.

### Viewing effective permissions

On the user detail page, the **Effective Permissions** section shows the merged set of all permissions the user holds across all their bindings.

> **Tip:** A user can have multiple bindings at different scopes. A product-scoped `product-admin` binding combined with an org-scoped `read-only` binding gives full product access plus read-everywhere.

---

## 6. Key Management

Navigate to **Administration → Key Management**.

Platform API keys are stored encrypted in the database. They are used by services like the AI chat assistant.

### Adding a key

1. Click **Add Key**
2. Select the **Key Type** (e.g. `GROQ_API_KEY`)
3. Paste the key value
4. Click **Save** — the value is encrypted at rest immediately

### Rotating a key

Click the **Edit** icon on the key row → enter the new value → Save. The old value is overwritten.

### Required keys

| Key | Purpose |
|-----|---------|
| `GROQ_API_KEY` | Powers the AI chat assistant (Groq / Llama 3.3 70B) |

---

## 7. Global Variables

Navigate to **Administration → Global Variables**.

Global variables are key-value pairs available to all pipeline tasks as environment variables at runtime.

### Adding a variable

1. Click **New Variable**
2. Enter **Name** (e.g. `REGISTRY_URL`) and **Value**
3. Mark as **Secret** if the value should be masked in logs
4. Click **Save**

### Using in pipelines

Reference global variables in task definitions using `${VARIABLE_NAME}`. They are injected alongside pipeline-specific parameter values at execution time.

> Variables marked as Secret are never returned in plaintext via the API — they appear as `***` in the UI.

---

## 8. System Settings

Navigate to **Administration → System**.

These settings control platform-wide behaviour and override environment variables at runtime.

### Key settings

| Setting | Description | Default |
|---------|-------------|---------|
| `JWT_SECRET_KEY` | Signing key for JWT tokens | Random on first boot |
| `JWT_EXPIRY_HOURS` | Token lifetime in hours | `8` |
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `MAX_CONCURRENT_RUNS` | Maximum parallel pipeline runs | `10` |
| `AUDIT_RETENTION_DAYS` | Days to retain audit events | `90` |

> Changes to `JWT_SECRET_KEY` invalidate all active sessions immediately. All users will need to log in again.

---

## 9. Framework Controls

Navigate to **Administration → Framework Controls**.

Framework Controls define the compliance frameworks your organisation has adopted (e.g. ISO 27001, SOC 2, NIST CSF) and map platform controls to framework requirements.

### Adding a framework

1. Click **New Framework**
2. Enter the framework **Name**, **Version**, and **Description**
3. Click **Save**

### Mapping controls

1. Open a framework → click **Add Control**
2. Enter the **Control ID** (e.g. `A.8.1`), **Title**, and **Description**
3. Link to one or more **Compliance Rules** that satisfy the control
4. Click **Save**

### Compliance scoring

Control coverage is reflected in the **Governance → Maturity** dashboard. A control is considered satisfied when all linked compliance rules pass for the current release.

---

## 10. Monitoring

Navigate to **Administration → Monitoring**.

The Monitoring page surfaces platform health and operational metrics.

### What's shown

| Panel | Description |
|-------|-------------|
| Pipeline Run Rate | Runs per hour over the last 24 hours |
| Success / Failure Ratio | Pass rate across all products |
| Active Runs | Currently executing pipeline runs |
| Agent Pool Utilisation | Active vs idle agents per pool |
| Recent Audit Events | Last 50 platform-level events |
| Webhook Delivery Health | Success rate for outbound webhook calls |

### External metrics

Conduit exposes a Prometheus-compatible metrics endpoint at `GET /metrics`. Scrape this endpoint from your observability stack (Prometheus, Grafana, Datadog, etc.).

```
http://<host>:8080/metrics
```

The endpoint is unauthenticated and should be protected at the network/ingress level in production.

---

## 11. Vault (Secrets Management)

Navigate to any product → **Vault**, or platform-wide via the Vault API.

The built-in vault stores secrets encrypted with Fernet symmetric encryption. Secrets are scoped per product and can be referenced in pipeline task definitions.

### Creating a secret

1. Open a product → Vault tab → **New Secret**
2. Enter **Name** and **Value**
3. Optionally set an **Expiry** date
4. Click **Save** — the value is encrypted immediately

### Revealing a secret

Click the **Reveal** button on a secret row. This action requires the `vault:reveal` permission and is recorded in the audit log.

### Using secrets in pipelines

Reference vault secrets in task configurations using `${SECRET:secret-name}`. The runtime substitutes the plaintext value at execution time and never logs it.

### Secret rotation

1. Click **Edit** on the secret
2. Enter the new value
3. Save — the old ciphertext is overwritten

---

## 12. Plugins & Integrations

Navigate to **Administration → System** or via the API at `/api/v1/plugins`.

Plugins extend Conduit with integrations to external CI/CD tools.

### Built-in plugins

| Plugin | Type | Description |
|--------|------|-------------|
| `gitlab-ci` | CI | Trigger and monitor GitLab CI pipelines |
| `bitbucket-pipelines` | CI | Trigger Bitbucket Pipelines |
| `cloudbees-ci` | CI | CloudBees CI integration |

### Configuring a plugin

1. Open a plugin → **New Configuration**
2. Enter a **Config Name** (e.g. `prod-gitlab`)
3. Set the **Tool URL** (e.g. `https://gitlab.example.com`)
4. Add credentials (API token, username, etc.)
5. Click **Test** to validate connectivity
6. Click **Save**

Each plugin can have multiple named configurations — one per environment or target instance.

---

## 13. Webhooks

Navigate to a product → **Webhooks**, or globally via `/api/v1/webhooks`.

Webhooks allow Conduit to notify external systems when events occur (pipeline run completed, release deployed, compliance check failed, etc.).

### Creating a webhook

1. Click **New Webhook**
2. Enter the **Target URL**
3. Select **Events** to subscribe to
4. Optionally set a **Secret** for HMAC signature verification
5. Click **Save**

### Inbound webhooks (triggers)

Each webhook has a unique trigger URL:
```
POST /api/v1/webhooks/<webhook-id>/trigger
```

Calling this URL starts the associated pipeline run. No authentication is required on the trigger endpoint — protect it with the webhook secret.

### Delivery history

Open a webhook → **Deliveries tab** to see a log of all outbound calls, HTTP status codes, and response bodies. Failed deliveries can be retried manually.

---

## 14. Compliance Administration

Navigate to **Governance → Compliance**.

### Compliance rules

Compliance rules define admission criteria that must pass before a release can proceed. Rules are evaluated automatically on every release run.

#### Rule types

| Type | Description |
|------|-------------|
| `required_approval` | Release must have at least N approvals |
| `all_stages_passed` | All pipeline stages must have succeeded |
| `no_critical_failures` | No task marked as critical may have failed |
| `compliance_score` | Minimum compliance score threshold |
| `environment_gate` | Deployment target must be an approved environment |

#### Creating a rule

1. Governance → Compliance → **New Rule**
2. Select **Rule Type**, enter **Name** and parameters
3. Set **Severity** (`critical`, `high`, `medium`, `low`)
4. Click **Save**

### ISO 27001 compliance

Conduit includes a built-in ISO/IEC 27001:2022 Annex A control evaluator. Navigate to **Governance → Compliance → ISO 27001** to see a live status for all 93 controls.

Controls are evaluated automatically. The overall compliance score is shown on the Maturity dashboard.

### Approving exceptions

For compliance checks that cannot be remediated immediately:

1. Open the failing control
2. Click **Approve Exception**
3. Enter a **Justification** and **Expiry date**
4. Click **Save** — the control is marked as excepted until expiry

All exceptions are recorded in the audit log.

---

## 15. Backup & Recovery

### Database backup

**SQLite (default):**
```bash
# Copy the database file while the app is running
cp instance/conduit.db instance/conduit.db.bak-$(date +%Y%m%d)
```

For a consistent backup while the app is live:
```bash
sqlite3 instance/conduit.db ".backup 'instance/conduit-backup.db'"
```

**PostgreSQL:**
```bash
pg_dump $DATABASE_URL > conduit-$(date +%Y%m%d).sql
```

### What to back up

| Item | Location |
|------|----------|
| Database | `instance/conduit.db` (SQLite) or via `pg_dump` |
| Environment variables | `.env` file or K8s Secret |
| JWT secret key | `JWT_SECRET_KEY` env var |
| Vault encryption key | `VAULT_KEY` env var |

> **Critical:** If you lose `VAULT_KEY`, all vault secrets are unrecoverable. Back it up separately from the database.

### Restore procedure

1. Stop the application
2. Restore the database file / PostgreSQL dump
3. Ensure the same `VAULT_KEY` and `JWT_SECRET_KEY` are set in the environment
4. Start the application — schema migrations run automatically on boot

---

## 16. Troubleshooting

### User cannot log in

| Symptom | Check |
|---------|-------|
| "Invalid credentials" | Verify username/password; check if user is **Active** |
| LDAP user rejected | Verify `LDAP_URL` and `LDAP_BIND_DN` in System Settings |
| Token expired immediately | Check `JWT_EXPIRY_HOURS` setting |

### Pipeline run stuck in "running"

1. Check **Administration → Monitoring → Active Runs**
2. If a run has been running for longer than expected, open it and click **Cancel**
3. Check agent pool health — an unavailable agent pool causes runs to hang

### API returns 401 Unauthorized

- Token may have expired — log out and log in again
- If all users are affected, `JWT_SECRET_KEY` may have been rotated — all sessions need to re-authenticate

### API returns 403 Forbidden

- The user lacks the required permission for that action
- Check their role bindings in **Administration → User Management**
- Ensure the role has the correct permissions in **Administration → Permissions**

### Compliance score is 0%

- Ensure at least one **Compliance Rule** is configured and active
- Check that pipeline runs have completed (rules are evaluated post-run)
- Verify the product has at least one release with a completed run

### AI chat not responding

- Verify `GROQ_API_KEY` is set in **Administration → Key Management**
- Check the key is valid — test it with a direct API call to Groq
- Check `LOG_LEVEL=DEBUG` and look for `chat_service` errors in the logs

### Viewing logs

```bash
# Direct run
python wsgi.py

# Docker
docker logs <container-id> --tail 200 -f

# Kubernetes
kubectl logs -n conduit -l app=conduit --tail=200 -f
```

Log output is structured JSON. Filter by field:
```bash
kubectl logs -n conduit -l app=conduit | grep '"status": 5'
```

---

*For API documentation see **Documentation → API Reference**. For architecture and data model details see **Documentation → Technical Docs**.*
