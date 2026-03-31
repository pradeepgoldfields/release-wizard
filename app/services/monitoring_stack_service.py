"""Telemetry stack launcher — starts Prometheus, Alertmanager, and Grafana
using Docker or Podman, writes the required config files on the fly, and
provides status queries.

The monitoring directory is written to the system temp dir (or a configurable
path) so the container filesystem restriction does not apply.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any

# ── Config templates ──────────────────────────────────────────────────────────

_PROMETHEUS_YML = textwrap.dedent("""\
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - alert_rules.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  - job_name: conduit
    static_configs:
      - targets: ['{host}:8080']
    metrics_path: /metrics
""")

_ALERT_RULES_YML = textwrap.dedent("""\
groups:
  - name: conduit
    rules:
      - alert: HighFailureRate
        expr: rate(conduit_pipeline_runs_total{status="Failed"}[1h]) / rate(conduit_pipeline_runs_total[1h]) > 0.2
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High pipeline failure rate (>20%)"

      - alert: LongRunningPipeline
        expr: conduit_pipeline_run_duration_seconds > 1800
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Pipeline running for over 30 minutes"

      - alert: NoRecentRuns
        expr: increase(conduit_pipeline_runs_total[24h]) == 0
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "No pipeline runs in 24 hours"

      - alert: LowComplianceScore
        expr: conduit_compliance_score_avg < 70
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Average compliance score dropped below 70"

      - alert: ManyActiveRuns
        expr: conduit_active_pipeline_runs > 10
        for: 1m
        labels:
          severity: info
        annotations:
          summary: "More than 10 concurrent pipeline runs"

      - alert: HighHttpErrorRate
        expr: rate(conduit_http_requests_total{status=~"5.."}[5m]) / rate(conduit_http_requests_total[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "HTTP 5xx error rate exceeds 5%"
""")

_ALERTMANAGER_YML = textwrap.dedent("""\
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 1h
  receiver: default
  routes:
    - match:
        severity: critical
      receiver: critical-alerts

receivers:
  - name: default
  - name: critical-alerts

inhibit_rules:
  - source_match:
      severity: critical
    target_match:
      severity: warning
    equal: ['alertname']
""")

# Grafana datasource provisioning
_GRAFANA_DS = textwrap.dedent("""\
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
""")

# Grafana Conduit dashboard JSON (simplified 6-panel starter)
_GRAFANA_DASHBOARD = json.dumps({
    "id": None,
    "title": "Conduit CI/CD Platform",
    "tags": ["conduit"],
    "timezone": "browser",
    "schemaVersion": 38,
    "version": 1,
    "panels": [
        {
            "id": 1, "title": "Pipeline Run Rate", "type": "timeseries",
            "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
            "targets": [{"expr": 'rate(conduit_pipeline_runs_total[5m])', "legendFormat": "{{status}}"}],
        },
        {
            "id": 2, "title": "Active Pipeline Runs", "type": "stat",
            "gridPos": {"x": 12, "y": 0, "w": 6, "h": 4},
            "targets": [{"expr": "conduit_active_pipeline_runs"}],
        },
        {
            "id": 3, "title": "Compliance Score Avg", "type": "gauge",
            "gridPos": {"x": 18, "y": 0, "w": 6, "h": 4},
            "targets": [{"expr": "conduit_compliance_score_avg"}],
            "fieldConfig": {"defaults": {"min": 0, "max": 100,
                "thresholds": {"mode": "absolute", "steps": [
                    {"color": "red", "value": 0},
                    {"color": "yellow", "value": 60},
                    {"color": "green", "value": 80},
                ]}}},
        },
        {
            "id": 4, "title": "P95 Pipeline Duration (s)", "type": "timeseries",
            "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8},
            "targets": [{"expr": 'histogram_quantile(0.95, rate(conduit_pipeline_run_duration_seconds_bucket[5m]))', "legendFormat": "p95"}],
        },
        {
            "id": 5, "title": "Success Rate %", "type": "gauge",
            "gridPos": {"x": 12, "y": 4, "w": 6, "h": 4},
            "targets": [{"expr": 'rate(conduit_pipeline_runs_total{status="Succeeded"}[1h]) / rate(conduit_pipeline_runs_total[1h]) * 100'}],
            "fieldConfig": {"defaults": {"min": 0, "max": 100,
                "thresholds": {"mode": "absolute", "steps": [
                    {"color": "red", "value": 0},
                    {"color": "yellow", "value": 70},
                    {"color": "green", "value": 90},
                ]}}},
        },
        {
            "id": 6, "title": "HTTP Request Latency P99 (s)", "type": "timeseries",
            "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8},
            "targets": [{"expr": 'histogram_quantile(0.99, rate(conduit_http_request_duration_seconds_bucket[5m]))', "legendFormat": "p99 {{endpoint}}"}],
        },
    ],
}, indent=2)

_GRAFANA_DASHBOARD_PROV = textwrap.dedent("""\
apiVersion: 1
providers:
  - name: conduit
    folder: Conduit
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
""")

# ── Runtime detection ─────────────────────────────────────────────────────────


def _runtime() -> str | None:
    """Return 'docker' or 'podman' if available, else None."""
    for cmd in ("docker", "podman"):
        if shutil.which(cmd):
            return cmd
    # Windows: check common paths
    for candidate in [
        r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
        r"C:\Program Files\Podman\podman.exe",
    ]:
        if Path(candidate).exists():
            return "docker" if "docker" in candidate.lower() else "podman"
    return None


def _compose_cmd(runtime: str) -> list[str]:
    """Return compose command prefix."""
    if runtime == "docker":
        # Docker Compose v2 is a plugin; v1 is a standalone binary
        try:
            subprocess.run(["docker", "compose", "version"], capture_output=True, check=True)
            return ["docker", "compose"]
        except Exception:
            return ["docker-compose"]
    return ["podman-compose"]


# ── Stack directory ───────────────────────────────────────────────────────────

def _stack_dir() -> Path:
    """Return (and create) the directory where stack configs are written."""
    base = Path(tempfile.gettempdir()) / "conduit_monitoring"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _write_configs(stack_dir: Path) -> None:
    """Write all config files into the stack directory."""
    # Detect host address for Prometheus → Conduit scrape target
    host = "host.docker.internal" if platform.system() == "Windows" else "172.17.0.1"

    (stack_dir / "prometheus.yml").write_text(_PROMETHEUS_YML.format(host=host), encoding="utf-8")
    (stack_dir / "alert_rules.yml").write_text(_ALERT_RULES_YML, encoding="utf-8")
    (stack_dir / "alertmanager.yml").write_text(_ALERTMANAGER_YML, encoding="utf-8")

    # Grafana provisioning
    ds_dir = stack_dir / "grafana" / "provisioning" / "datasources"
    db_dir = stack_dir / "grafana" / "provisioning" / "dashboards"
    ds_dir.mkdir(parents=True, exist_ok=True)
    db_dir.mkdir(parents=True, exist_ok=True)
    (ds_dir / "conduit.yml").write_text(_GRAFANA_DS, encoding="utf-8")
    (db_dir / "conduit.yml").write_text(_GRAFANA_DASHBOARD_PROV, encoding="utf-8")
    (db_dir / "conduit_dashboard.json").write_text(_GRAFANA_DASHBOARD, encoding="utf-8")

    _write_compose(stack_dir)


def _write_compose(stack_dir: Path) -> None:
    compose = textwrap.dedent(f"""\
version: "3.9"

services:
  prometheus:
    image: prom/prometheus:v2.52.0
    container_name: conduit-prometheus
    ports:
      - "9090:9090"
    volumes:
      - {stack_dir}/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - {stack_dir}/alert_rules.yml:/etc/prometheus/alert_rules.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:v0.27.0
    container_name: conduit-alertmanager
    ports:
      - "9093:9093"
    volumes:
      - {stack_dir}/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    restart: unless-stopped

  grafana:
    image: grafana/grafana:11.0.0
    container_name: conduit-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=conduit
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_AUTH_ANONYMOUS_ENABLED=false
    volumes:
      - {stack_dir}/grafana/provisioning:/etc/grafana/provisioning:ro
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
""")
    # Use forward slashes for Docker paths even on Windows
    compose = compose.replace("\\", "/")
    (stack_dir / "docker-compose.yml").write_text(compose, encoding="utf-8")


# ── Public API ────────────────────────────────────────────────────────────────


def get_stack_status() -> dict:
    """Return status of Prometheus, Alertmanager and Grafana containers."""
    runtime = _runtime()
    if not runtime:
        return {
            "runtime": None,
            "error": "No container runtime (Docker/Podman) found on this host",
            "services": {},
        }

    services: dict[str, dict] = {}
    for name, port in [("conduit-prometheus", 9090), ("conduit-alertmanager", 9093), ("conduit-grafana", 3000)]:
        try:
            result = subprocess.run(
                [runtime, "inspect", "--format", "{{.State.Status}}", name],
                capture_output=True, text=True, timeout=5
            )
            state = result.stdout.strip() or "not found"
        except Exception:
            state = "not found"
        services[name] = {"state": state, "port": port, "url": f"http://localhost:{port}"}

    return {"runtime": runtime, "services": services, "stack_dir": str(_stack_dir())}


def start_stack() -> dict:
    """Write configs and start the monitoring stack."""
    runtime = _runtime()
    if not runtime:
        return {"ok": False, "error": "No container runtime found (install Docker or Podman)"}

    stack_dir = _stack_dir()
    _write_configs(stack_dir)
    compose = _compose_cmd(runtime)

    try:
        result = subprocess.run(
            compose + ["-f", str(stack_dir / "docker-compose.yml"), "up", "-d"],
            capture_output=True, text=True, timeout=120,
            cwd=str(stack_dir),
        )
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr or result.stdout}
        return {
            "ok": True,
            "message": "Monitoring stack started",
            "urls": {
                "prometheus": "http://localhost:9090",
                "alertmanager": "http://localhost:9093",
                "grafana": "http://localhost:3000",
            },
            "grafana_credentials": {"username": "admin", "password": "conduit"},
            "stack_dir": str(stack_dir),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Timed out starting stack (>120s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def stop_stack() -> dict:
    """Stop and remove the monitoring stack containers."""
    runtime = _runtime()
    if not runtime:
        return {"ok": False, "error": "No container runtime found"}

    stack_dir = _stack_dir()
    compose = _compose_cmd(runtime)

    try:
        result = subprocess.run(
            compose + ["-f", str(stack_dir / "docker-compose.yml"), "down"],
            capture_output=True, text=True, timeout=60,
            cwd=str(stack_dir),
        )
        return {"ok": result.returncode == 0, "output": result.stdout or result.stderr}
    except Exception as e:
        return {"ok": False, "error": str(e)}
