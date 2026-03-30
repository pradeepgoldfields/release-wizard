"""Sandbox script execution service.

Runs user-supplied bash or python scripts in an isolated subprocess,
or as a Kubernetes Job when running inside a cluster.

Execution strategy (chosen automatically at runtime):
  - K8s cluster detected  → ``_run_script_k8s()``  (kubernetes Job)
  - Local / CI            → ``_run_script_subprocess()``

The contract:
  - Exit code 0  → Succeeded
  - Exit code 1  → Warning  (honoured only when task.on_error == "warn")
  - Exit code 2+ → Failed
  - Last stdout line that is valid JSON is captured as output_json.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.extensions import db
from app.models.task import TaskRun
from app.services.id_service import resource_id

log = logging.getLogger(__name__)

# K8s service-account token path (present inside every Pod)
_K8S_SA_TOKEN = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
_K8S_NAMESPACE_FILE = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")


def _in_kubernetes() -> bool:
    """Return True when the process is running inside a Kubernetes Pod."""
    return _K8S_SA_TOKEN.exists()


def _k8s_namespace() -> str:
    try:
        return _K8S_NAMESPACE_FILE.read_text().strip()
    except OSError:
        return os.getenv("POD_NAMESPACE", "release-wizard")


def _run_script_k8s(language: str, code: str, timeout: int, task_run_id: str) -> tuple[int, str]:
    """Execute a script as a Kubernetes Job and stream its logs back.

    Creates a Job named ``rw-task-<task_run_id>``, waits for completion
    (up to *timeout* seconds), collects logs, then deletes the Job.

    Returns ``(return_code, logs)``.
    """
    try:
        from kubernetes import client  # noqa: PLC0415
        from kubernetes import config as k8s_config

        k8s_config.load_incluster_config()
    except ImportError:
        return 1, "[error] kubernetes package not installed — run: pip install kubernetes\n"
    except Exception as exc:
        return 1, f"[error] Failed to load K8s config: {exc}\n"

    namespace = _k8s_namespace()
    job_name = f"rw-task-{task_run_id.lower().replace('_', '-')}"
    image = os.getenv("TASK_RUNNER_IMAGE", "registry.access.redhat.com/ubi9/python-312:latest")

    if language == "bash":
        cmd = ["bash", "-c", code]
    else:
        cmd = ["python3", "-c", code]

    batch_v1 = client.BatchV1Api()
    core_v1 = client.CoreV1Api()

    job_body = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(
            name=job_name,
            namespace=namespace,
            labels={"app": "release-wizard", "task-run-id": task_run_id},
        ),
        spec=client.V1JobSpec(
            ttl_seconds_after_finished=300,
            backoff_limit=0,
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"job-name": job_name}),
                spec=client.V1PodSpec(
                    restart_policy="Never",
                    containers=[
                        client.V1Container(
                            name="task",
                            image=image,
                            command=cmd,
                            resources=client.V1ResourceRequirements(
                                limits={"cpu": "500m", "memory": "256Mi"},
                                requests={"cpu": "100m", "memory": "64Mi"},
                            ),
                        )
                    ],
                ),
            ),
        ),
    )

    logs = ""
    return_code = 1
    try:
        batch_v1.create_namespaced_job(namespace=namespace, body=job_body)
        log.info("K8s Job created: %s/%s", namespace, job_name)

        # Poll for completion
        deadline = time.monotonic() + timeout
        pod_name = None
        while time.monotonic() < deadline:
            job = batch_v1.read_namespaced_job(name=job_name, namespace=namespace)
            status = job.status
            if status.succeeded or status.failed:
                return_code = 0 if status.succeeded else 2
                break
            # Find pod name for log streaming
            if not pod_name:
                pods = core_v1.list_namespaced_pod(
                    namespace=namespace, label_selector=f"job-name={job_name}"
                )
                if pods.items:
                    pod_name = pods.items[0].metadata.name
            time.sleep(3)
        else:
            return_code = 124
            logs = f"[error] K8s Job timed out after {timeout}s\n"

        # Collect logs
        if pod_name:
            try:
                logs = core_v1.read_namespaced_pod_log(name=pod_name, namespace=namespace)
            except Exception as exc:
                logs += f"\n[warn] Could not retrieve pod logs: {exc}\n"

    except Exception as exc:
        logs = f"[error] K8s Job execution failed: {exc}\n"
        return_code = 1
    finally:
        try:
            batch_v1.delete_namespaced_job(
                name=job_name,
                namespace=namespace,
                body=client.V1DeleteOptions(propagation_policy="Foreground"),
            )
        except Exception:
            pass

    return return_code, logs


def _parse_output_json(stdout: str) -> str | None:
    """Extract JSON from the last non-empty line of stdout, if valid."""
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    for line in reversed(lines):
        try:
            json.loads(line)
            return line
        except ValueError:
            pass
    return None


def _status_from_code(return_code: int, on_error: str) -> str:
    if return_code == 0:
        return "Succeeded"
    if return_code == 1 and on_error == "warn":
        return "Warning"
    return "Failed"


def _run_script_subprocess(
    language: str,
    code: str,
    timeout: int,
    context_env: dict | None = None,
) -> tuple[int, str]:
    """Write code to a temp file and execute it.  Returns (return_code, logs)."""
    suffix = ".sh" if language == "bash" else ".py"
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8") as f:
        if language == "bash" and not code.startswith("#!"):
            f.write("#!/bin/bash\nset -euo pipefail\n")
        f.write(code)
        script_path = Path(f.name)

    try:
        if language == "bash":
            cmd = ["bash", str(script_path)]
        else:
            cmd = [sys.executable, str(script_path)]

        base_env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": "/tmp",
            "TERM": "xterm",
        }
        if context_env:
            base_env.update(context_env)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=base_env,
        )
        logs = result.stdout
        if result.stderr:
            logs += "\n[stderr]\n" + result.stderr
        return result.returncode, logs
    except subprocess.TimeoutExpired:
        return 124, f"[error] Script timed out after {timeout}s\n"
    except FileNotFoundError:
        return 127, f"[error] Interpreter not found for language: {language}\n"
    except Exception as exc:
        return 1, f"[error] Execution failed: {exc}\n"
    finally:
        script_path.unlink(missing_ok=True)


def run_task_async(  # noqa: PLR0913
    app: Any, task_run_id: str, language: str, code: str, timeout: int, on_error: str
) -> None:
    """Kick off script execution in a background thread and update the TaskRun."""

    def _worker() -> None:
        with app.app_context():
            task_run = db.session.get(TaskRun, task_run_id)
            if not task_run:
                return

            task_run.status = "Running"
            db.session.commit()

            if _in_kubernetes():
                log.info("Executing task %s via K8s Job", task_run_id)
                return_code, logs = _run_script_k8s(language, code, timeout, task_run_id)
            else:
                return_code, logs = _run_script_subprocess(language, code, timeout)
            output_json = _parse_output_json(logs)
            status = _status_from_code(return_code, on_error)

            task_run.return_code = return_code
            task_run.logs = logs
            task_run.output_json = output_json
            task_run.status = status
            task_run.finished_at = datetime.now(UTC)
            db.session.commit()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def create_and_run_task(
    task_id: str,
    language: str,
    code: str,
    timeout: int,
    on_error: str,
    agent_pool_id: str | None,
    stage_run_id: str | None,
    app: Any,
) -> TaskRun:
    """Create a TaskRun record and kick off async execution."""
    task_run = TaskRun(
        id=resource_id("trun"),
        task_id=task_id,
        stage_run_id=stage_run_id,
        agent_pool_id=agent_pool_id,
        status="Pending",
        logs="",
    )
    db.session.add(task_run)
    db.session.commit()

    run_task_async(app, task_run.id, language, code, timeout, on_error)
    return task_run
