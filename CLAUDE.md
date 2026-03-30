# CLAUDE.md — release-wizard

## Project Overview

A Python web application (Flask + Gunicorn) developed on Windows and deployed as a UBI (Universal Base Image) container on Kubernetes.

## Project Structure

```
release-wizard/
├── app/
│   ├── __init__.py          # Flask app factory (create_app)
│   ├── config.py            # Config class — reads env vars
│   ├── routes/
│   │   ├── health.py        # GET /healthz, GET /readyz
│   │   └── main.py          # Application routes
│   ├── models/              # SQLAlchemy models (add as needed)
│   ├── services/            # Business logic layer
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS / JS assets
│       ├── css/
│       └── js/
├── tests/
│   ├── unit/                # Fast, no I/O tests
│   └── integration/         # Tests that hit real services
├── k8s/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── ingress.yaml
├── Dockerfile               # Multi-stage UBI build
├── .dockerignore
├── Jenkinsfile              # CI/CD pipeline (K8s agent)
├── wsgi.py                  # Gunicorn entrypoint
├── requirements.txt         # Runtime deps (pinned)
├── requirements-dev.txt     # Dev/test deps
├── pyproject.toml           # ruff + pytest config
├── .gitattributes           # Enforce LF line endings
└── venv/                    # Local venv (never committed)
```

## Libraries Usage
Use necessary python libraries where ever necessary.
Make sure to user latest and stable versions of the libraries

## Environment Setup

### Local Development (Windows)

- **Python**: 3.14 via `venv/` (do not modify `venv/` directly)
- **Activate venv**: `source venv/Scripts/activate` (Git Bash) or `venv\Scripts\activate.bat` (cmd)
- **Install deps**: `pip install -r requirements.txt`

### Target Runtime Environment

- **Base image**: Red Hat UBI (e.g., `registry.access.redhat.com/ubi9/python-312` or similar)
- **Orchestration**: Kubernetes
- **OS inside container**: RHEL-compatible Linux (not Windows)

## Critical: Windows vs Container Path Differences

Never hardcode Windows-style paths (`C:\`, backslashes). All paths in application code must use forward slashes or `pathlib.Path` so they work inside the UBI container.

```python
# Bad
open("C:\\Users\\prade\\data\\file.txt")

# Good
from pathlib import Path
open(Path("data") / "file.txt")
```

## Running the App Locally

```bash
source venv/Scripts/activate        # Windows Git Bash
pip install -r requirements-dev.txt
python wsgi.py                      # dev server (Flask built-in)
# or with auto-reload:
flask --app wsgi:app run --port 8080 --debug
```

## Dev Change Workflow (Required After Every Code Change)

After **every** code change you must: free the port, restart the server, and verify it is up.
Run these steps in order — do not skip any.

### Step 1 — Free port 8080

```bash
# Git Bash / PowerShell
powershell -Command "
  Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id \$_.OwningProcess -Force -ErrorAction SilentlyContinue }
"
```

### Step 2 — Build (lint + test)

```bash
source venv/Scripts/activate
ruff check . && ruff format --check .
pytest
```

### Step 3 — Start the server

```bash
python wsgi.py &          # background, or open a second terminal
```

### Step 4 — Verify the server is up

```bash
curl -s http://localhost:8080/healthz   # expect {"status":"ok"}
```

### One-liner (copy-paste)

```bash
powershell -Command "Get-NetTCPConnection -LocalPort 8080 -EA SilentlyContinue | %{ Stop-Process -Id \$_.OwningProcess -Force -EA SilentlyContinue }" ; source venv/Scripts/activate && ruff check . && pytest && python wsgi.py
```

> **Rule**: CI (Jenkinsfile) follows the same order — lint → test → build image → deploy → health-check.
> Never skip the port-free step; stale processes cause silent failures.

## Building and Running the Container

```bash
# Build
docker build -t release-wizard:local .

# Run locally (mirrors K8s environment)
docker run --rm -p 8080:8080 release-wizard:local

# Exec into container for debugging
docker exec -it <container-id> /bin/bash
```

## Dockerfile Guidelines

- Multi-stage build: `builder` installs deps, final image copies only what is needed
- Base image: `registry.access.redhat.com/ubi9/python-312`
- Do not use `apt-get` — UBI uses `microdnf` or `dnf`
- Run as UID 1001 (non-root, required for OpenShift/K8s security contexts)
- `readOnlyRootFilesystem: true` is set in the deployment — do not write to the filesystem at runtime

## Jenkins Pipeline (Jenkinsfile)

Stages in order:

| Stage | Description |
|-------|-------------|
| Install Dependencies | `pip install -r requirements-dev.txt` inside UBI Python pod |
| Lint | `ruff check` + `ruff format --check` |
| Unit Tests | `pytest tests/unit` with coverage report |
| Integration Tests | `pytest tests/integration` |
| Build Image | `podman build` inside privileged Podman pod |
| Push Image | Pushes to registry on `main` / `release/*` branches only |
| Deploy to Dev | `kubectl apply -f k8s/` → `release-wizard-dev` namespace (auto, on `main`) |
| Deploy to Prod | Manual approval gate → `release-wizard-prod` namespace (on `release/*`) |

**Before first use**, update in `Jenkinsfile`:
- `IMAGE_REPO` — your container registry URL
- `REGISTRY_CREDENTIALS` — Jenkins credentials ID for the registry

## Kubernetes Considerations

- The app must respect `PORT` and `HOST` environment variables (K8s injects config via env vars and ConfigMaps)
- Health check endpoints are expected:
  - `GET /healthz` — liveness probe
  - `GET /readyz` — readiness probe
- Do not write to the local filesystem at runtime unless a PersistentVolumeClaim is mounted; containers are ephemeral
- Secrets are injected as env vars or mounted files — never hardcode credentials

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Port the app listens on | `8080` |
| `HOST` | Bind address | `0.0.0.0` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

## Testing

```bash
# Unit tests
pytest

# With coverage
pytest --cov=. --cov-report=term-missing
```

Tests must pass in both the local Windows venv and inside the UBI container. Avoid tests that rely on Windows-specific behavior.

## Linting / Formatting

```bash
ruff check .
ruff format .
```

## File Encoding

Always use UTF-8. Explicitly specify encoding when opening files:

```python
open("file.txt", encoding="utf-8")
```

Windows may default to cp1252; the container will expect UTF-8.

## Line Endings

Configure Git to avoid CRLF issues:

```
# .gitattributes
* text=auto eol=lf
```

Shell scripts and Dockerfiles must use LF line endings or they will fail inside the container.

## Dependencies

- Add all runtime dependencies to `requirements.txt`
- Add dev-only tools (pytest, ruff, etc.) to `requirements-dev.txt`
- Pin versions for reproducible container builds

## Helm Chart (Kubernetes Deployment)

The primary deployment method is the Helm chart at [helm/release-wizard/](helm/release-wizard/).

### Chart structure

| File | Purpose |
|------|---------|
| `Chart.yaml` | Chart metadata and version |
| `values.yaml` | Default values — the single source of truth for all configuration |
| `values-dev.yaml` | Dev environment overrides (1 replica, DEBUG log, HPA off) |
| `values-prod.yaml` | Prod environment overrides (3+ replicas, HPA on, existingSecret) |
| `templates/_helpers.tpl` | Named templates: labels, fullname, secretName, namespace |
| `templates/configmap.yaml` | Non-sensitive env vars |
| `templates/secret.yaml` | Sensitive env vars (skipped when `existingSecret` is set) |
| `templates/deployment.yaml` | Pod spec with probes, security context, volume mounts |
| `templates/service.yaml` | ClusterIP Service |
| `templates/ingress.yaml` | Ingress (toggled by `ingress.enabled`) |
| `templates/hpa.yaml` | HorizontalPodAutoscaler (toggled by `hpa.enabled`) |
| `templates/serviceaccount.yaml` | ServiceAccount (toggled by `serviceAccount.create`) |

### Install / upgrade

```bash
# Dev
helm upgrade --install release-wizard ./helm/release-wizard \
  -f helm/release-wizard/values-dev.yaml \
  --set image.tag=latest \
  --set secrets.databaseUrl="sqlite:///instance/release_wizard.db"

# Prod (uses pre-created Secret — never pass secrets on CLI in production)
helm upgrade --install release-wizard ./helm/release-wizard \
  -f helm/release-wizard/values-prod.yaml \
  --set image.tag=1.2.3 \
  -n release-wizard --create-namespace
```

### Secrets strategy

| Approach | When to use |
|----------|-------------|
| `secrets.*` values block | Local dev, CI smoke tests |
| `existingSecret: <name>` | Production — supply Secret via Vault, Sealed Secrets, or External Secrets Operator |

### Lint and dry-run

```bash
helm lint ./helm/release-wizard
helm template release-wizard ./helm/release-wizard -f helm/release-wizard/values-dev.yaml | less
helm upgrade --install release-wizard ./helm/release-wizard --dry-run --debug
```

## Terraform (Kubernetes Deployment)

Terraform code lives in [terraform/](terraform/). It uses the `hashicorp/kubernetes` provider to deploy all K8s resources.

### Files

| File | Purpose |
|------|---------|
| `main.tf` | Provider config, Namespace resource |
| `variables.tf` | All input variables with defaults |
| `config.tf` | ConfigMap (env config) + Secret (sensitive values) |
| `app.tf` | Deployment, Service, HorizontalPodAutoscaler |
| `ingress.tf` | Ingress with optional TLS |
| `outputs.tf` | Useful output values |
| `terraform.tfvars.example` | Template — copy to `terraform.tfvars` and fill in |

### Usage

```bash
cd terraform

# First time
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set image_repo, database_url, secret_key, etc.

terraform init
terraform plan
terraform apply
```

### Updating the image after a new build

```bash
terraform apply -var="image_tag=1.2.3"
```

### Secrets

Supply `database_url`, `secret_key`, `jwt_secret_key` via `terraform.tfvars` (never commit this file) or environment variables:

```bash
export TF_VAR_database_url="postgresql+psycopg2://user:pass@host/db"
export TF_VAR_secret_key="$(openssl rand -hex 32)"
export TF_VAR_jwt_secret_key="$(openssl rand -hex 32)"
```

`terraform.tfvars` is already listed in `.gitignore`.

## What to Avoid

- Windows-only libraries or paths
- Writing to `/tmp` without accounting for container ephemeral storage
- Running as root in the container
- Using `localhost` — use `0.0.0.0` as bind address so the app is reachable inside K8s pods
- Storing state in memory between requests (pods can be restarted or scaled)
