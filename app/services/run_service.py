"""Business logic for PipelineRun and ReleaseRun lifecycle management."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import RunStatus
from app.extensions import db
from app.models.application import ApplicationArtifact
from app.models.pipeline import Pipeline
from app.models.release import Release
from app.models.run import PipelineRun, ReleaseRun, StageRun
from app.models.task import TaskRun
from app.services.audit_service import record_event
from app.services.event_service import (
    pipeline_run_finished,
    pipeline_run_started,
    stage_run_finished,
    task_run_finished,
)
from app.services.execution_service import (
    _in_kubernetes,
    _parse_output_json,
    _run_script_k8s,
    _run_script_subprocess,
    _status_from_code,
)
from app.services.id_service import pipeline_run_id, release_run_id, resource_id

#: Statuses that mark a run as finished — triggers ``finished_at`` timestamp.
TERMINAL_STATUSES: frozenset[str] = frozenset(
    {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}
)


def start_pipeline_run(
    pipeline_id: str,
    commit_sha: str | None = None,
    artifact_id: str | None = None,
    triggered_by: str = "system",
    runtime_properties: dict | None = None,
    app: Any = None,
) -> PipelineRun:
    """Create a PipelineRun, seed StageRun/TaskRun records, kick off async execution."""
    pipeline = db.get_or_404(Pipeline, pipeline_id)

    run = PipelineRun(
        id=pipeline_run_id(),
        pipeline_id=pipeline_id,
        status=RunStatus.RUNNING if pipeline.stages else RunStatus.SUCCEEDED,
        commit_sha=commit_sha,
        artifact_id=artifact_id,
        compliance_rating=pipeline.compliance_rating,
        compliance_score=pipeline.compliance_score,
        triggered_by=triggered_by,
        runtime_properties=json.dumps(runtime_properties or {}),
        started_at=datetime.now(UTC),
    )
    db.session.add(run)

    # Seed StageRun and TaskRun records in Pending state
    for stage in sorted(pipeline.stages, key=lambda s: s.order):
        sr = StageRun(
            id=resource_id("srun"),
            pipeline_run_id=run.id,
            stage_id=stage.id,
            status=RunStatus.PENDING,
            runtime_properties="{}",
        )
        db.session.add(sr)
        db.session.flush()  # get sr.id before adding task runs

        for task in sorted(stage.tasks, key=lambda t: t.order):
            tr = TaskRun(
                id=resource_id("trun"),
                task_id=task.id,
                stage_run_id=sr.id,
                status="Pending",
                logs="",
            )
            db.session.add(tr)

    db.session.commit()

    record_event(
        "pipeline.run.started",
        triggered_by,
        "pipeline_run",
        run.id,
        "create",
        detail={"pipeline_id": pipeline_id},
    )

    pipeline_run_started(run)

    if app and pipeline.stages:
        thread = threading.Thread(
            target=_execute_pipeline_async,
            args=(app, run.id),
            daemon=True,
        )
        thread.start()

    return run


def _build_runtime_context(run: PipelineRun, stage_run=None, task_run=None, task=None) -> dict:
    """Build the full pipelineRuntime context dict for injection into task scripts.

    Includes the legacy flat runtime_properties blobs AND the new hierarchical
    resolved properties under the ``properties`` key.  The resolved dict is
    built from the full chain: task → stage → pipeline → product, with
    runtime ParameterValue overrides taking precedence.
    """
    from app.services.property_service import resolve_all

    pipeline_rt = json.loads(run.runtime_properties or "{}")
    stage_runtime: dict = {}

    for sr in run.stage_runs:
        stage_name = sr.stage.name if sr.stage else sr.stage_id
        sr_props = json.loads(sr.runtime_properties or "{}")
        task_runtime: dict = {}
        for tr in sr.task_runs:
            task_name = tr.task.name if tr.task else tr.task_id
            task_out = {}
            if tr.output_json:
                try:
                    task_out = json.loads(tr.output_json)
                except (ValueError, TypeError):
                    task_out = {}
            user_inp = {}
            if tr.user_input:
                try:
                    user_inp = json.loads(tr.user_input)
                except (ValueError, TypeError):
                    user_inp = {}
            task_runtime[task_name] = {**task_out, "input": user_inp}
        stage_runtime[stage_name] = {**sr_props, "taskRuntime": task_runtime}

    # Hierarchical resolved properties for the current execution context.
    # Secrets are masked here so they never appear in CDT_PROPS, CDT_RUNTIME,
    # or the stored context_env — tasks that need a secret must use the Vault
    # reveal endpoint instead.
    pipeline = run.pipeline
    stage = stage_run.stage if stage_run else None
    product = pipeline.product if pipeline else None
    resolved_props = resolve_all(
        pipeline_run=run,
        stage_run=stage_run,
        task_run=task_run,
        task=task,
        stage=stage,
        pipeline=pipeline,
        product=product,
        mask_secrets=True,
    )

    return {**pipeline_rt, "stageRuntime": stage_runtime, "properties": resolved_props}


def _evaluate_run_condition(condition: str | None, pipeline_status: str) -> bool:
    """Return True if the task/stage should run given the current pipeline status."""
    cond = (condition or "always").lower()
    if cond == "always":
        return True
    if cond == "on_success":
        return pipeline_status not in ("Failed", "Warning", "Cancelled")
    if cond == "on_failure":
        return pipeline_status == "Failed"
    if cond == "on_warning":
        return pipeline_status in ("Warning",)
    return True


def _run_gate_script(
    language: str,
    script: str,
    timeout: int,
    env: dict[str, str],
    label: str,
) -> tuple[bool, str]:
    """Run a gate script.  Returns (passed, logs)."""
    if not script or not script.strip():
        return True, f"[{label}] No script defined — gate passed by default."
    if _in_kubernetes():
        rc, logs = _run_script_k8s(language or "bash", script, timeout or 60, label)
    else:
        rc, logs = _run_script_subprocess(language or "bash", script, timeout or 60, env)
    passed = rc == 0
    return passed, logs


def _execute_task_run(
    app: Any,
    run_id: str,
    sr_id: str,
    tr_id: str,
    env: dict[str, str],
    pipeline_so_far_status: str = "Succeeded",
) -> tuple[str, bool]:
    """Execute a single TaskRun and persist results.  Returns (status, warned)."""

    def _now() -> datetime:
        return datetime.now(UTC)

    with app.app_context():
        run = db.session.get(PipelineRun, run_id)
        sr = db.session.get(StageRun, sr_id)
        tr = db.session.get(TaskRun, tr_id)
        if not run or not sr or not tr:
            return "Failed", False

        task = tr.task

        # ── Run condition check ───────────────────────────────────────────────
        if not _evaluate_run_condition(
            task.run_condition if task else None, pipeline_so_far_status
        ):
            tr.status = "Skipped"
            tr.logs = f"[SKIPPED] run_condition='{task.run_condition}' not met (pipeline status: {pipeline_so_far_status})"
            tr.started_at = _now()
            tr.finished_at = _now()
            db.session.commit()
            task_run_finished(tr)
            return "Skipped", False

        tr.status = "Running"
        tr.started_at = _now()
        db.session.commit()

        runtime_ctx = _build_runtime_context(run, stage_run=sr, task_run=tr, task=task)
        user_input = {}
        if tr.user_input:
            try:
                user_input = json.loads(tr.user_input)
            except (ValueError, TypeError):
                user_input = {}

        webhook_payload = runtime_ctx.get("webhook", {}).get("payload", {})
        task_env = {
            **env,
            "CDT_TASK_RUN_ID": tr.id,
            "CDT_TASK_ID": task.id,
            "CDT_TASK_NAME": task.name,
            "CDT_RUNTIME": json.dumps(runtime_ctx),
            "CDT_USER_INPUT": json.dumps(user_input),
            "CDT_WEBHOOK_PAYLOAD": json.dumps(webhook_payload),
            "CDT_PROPS": json.dumps(runtime_ctx.get("properties", {})),
        }
        tr.context_env = json.dumps(task_env)

        kind = (task.kind or "script") if task else "script"

        # ── Approval task ─────────────────────────────────────────────────────
        if kind == "approval":
            tr.status = "AwaitingApproval"
            timeout_secs = (task.approval_timeout or 0) if task else 0
            approvers_raw = (task.approval_approvers or "[]") if task else "[]"
            try:
                approvers = json.loads(approvers_raw)
            except (ValueError, TypeError):
                approvers = []
            approver_summary = (
                ", ".join(f"{s.get('type', 'user')}:{s.get('ref', '?')}" for s in approvers)
                or "anyone"
            )
            tr.logs = f"[AWAITING APPROVAL] Required approvers: {approver_summary}\n"
            if timeout_secs:
                tr.logs += f"Timeout: {timeout_secs}s\n"
            db.session.commit()
            task_run_finished(tr)

            # Poll until approved/rejected or timeout
            deadline = datetime.now(UTC).timestamp() + timeout_secs if timeout_secs else None
            import time as _time  # noqa: PLC0415

            while True:
                _time.sleep(3)
                with app.app_context():
                    tr2 = db.session.get(TaskRun, tr_id)
                    if not tr2:
                        return "Failed", False
                    if tr2.status in ("Succeeded", "Failed", "Cancelled"):
                        warned = tr2.status == "Warning"
                        return tr2.status, warned
                    if deadline and datetime.now(UTC).timestamp() > deadline:
                        tr2.status = "Failed"
                        tr2.finished_at = _now()
                        tr2.logs = (tr2.logs or "") + "\n[TIMEOUT] Approval deadline exceeded."
                        db.session.commit()
                        task_run_finished(tr2)
                        return "Failed", False

        # ── Gate task ─────────────────────────────────────────────────────────
        if kind == "gate":
            script = (task.gate_script or "") if task else ""
            language = (task.gate_language or "bash") if task else "bash"
            timeout = (task.timeout or 60) if task else 60
            passed, logs = _run_gate_script(
                language, script, timeout, task_env, f"gate:{task.name}"
            )
            tr.logs = logs
            tr.return_code = 0 if passed else 1
            tr.status = "Succeeded" if passed else "Failed"
            tr.finished_at = _now()
            db.session.commit()
            task_run_finished(tr)
            return tr.status, False

        # ── Script task (default) ─────────────────────────────────────────────
        if _in_kubernetes():
            rc, logs = _run_script_k8s(task.run_language, task.run_code, task.timeout, tr.id)
        else:
            rc, logs = _run_script_subprocess(
                task.run_language, task.run_code, task.timeout, task_env
            )

        output_json = _parse_output_json(logs)
        status = _status_from_code(rc, task.on_error)
        tr.return_code = rc
        tr.logs = logs
        tr.output_json = output_json
        tr.status = status
        tr.finished_at = _now()
        db.session.commit()
        task_run_finished(tr)

        warned = status == "Warning"
        return status, warned


def _execute_stage(
    app: Any,
    run_id: str,
    sr_id: str,
    context_env: dict[str, str],
    pipeline_so_far_status: str = "Succeeded",
) -> tuple[bool, bool]:
    """Execute a single stage's tasks, respecting per-task execution_mode.

    Runs entry gate first, then tasks, then exit gate.
    Returns (failed, warned).
    """
    import copy

    def _now() -> datetime:
        return datetime.now(UTC)

    with app.app_context():
        run = db.session.get(PipelineRun, run_id)
        sr = db.session.get(StageRun, sr_id)
        if not run or not sr:
            return True, False

        env = copy.copy(context_env)
        env["CDT_STAGE_RUN_ID"] = sr.id
        env["CDT_STAGE_ID"] = sr.stage_id
        env["CDT_STAGE_NAME"] = sr.stage.name if sr.stage else ""

        stage = sr.stage
        stage_failed = False
        stage_warning = False

        # ── Entry gate ────────────────────────────────────────────────────────
        if stage:
            entry_cfg = json.loads(stage.entry_gate or "{}")
            if entry_cfg.get("enabled"):
                passed, logs = _run_gate_script(
                    entry_cfg.get("language", "bash"),
                    entry_cfg.get("script", ""),
                    int(entry_cfg.get("timeout", 60)),
                    env,
                    f"entry-gate:{stage.name}",
                )
                sr.runtime_properties = json.dumps(
                    {
                        **json.loads(sr.runtime_properties or "{}"),
                        "entry_gate": {"passed": passed, "logs": logs},
                    }
                )
                db.session.commit()
                if not passed:
                    sr.status = RunStatus.FAILED
                    sr.finished_at = _now()
                    # Cancel all task runs
                    for tr in sr.task_runs:
                        tr.status = "Cancelled"
                        tr.finished_at = _now()
                    db.session.commit()
                    stage_run_finished(sr)
                    return True, False

        task_runs = sorted(sr.task_runs, key=lambda tr: tr.task.order)
        stage_failed = False
        stage_warning = False

        # Group task runs by execution_mode (same logic as stage grouping)
        task_groups: list[list] = []
        for tr in task_runs:
            mode = (tr.task.execution_mode or "sequential") if tr.task else "sequential"
            if mode == "parallel" and task_groups and task_groups[-1]:
                prev_mode = (
                    (task_groups[-1][-1].task.execution_mode or "sequential")
                    if task_groups[-1][-1].task
                    else "sequential"
                )
                if prev_mode == "parallel":
                    task_groups[-1].append(tr)
                    continue
            task_groups.append([tr])

        for tgroup in task_groups:
            if stage_failed:
                # Cancel everything remaining
                for tr in tgroup:
                    tr.status = "Cancelled"
                    tr.finished_at = _now()
                db.session.commit()
                continue

            if len(tgroup) == 1:
                # Sequential — run inline
                tr = tgroup[0]
                status, warned = _execute_task_run(
                    app, run_id, sr_id, tr.id, env, pipeline_so_far_status
                )
                if warned:
                    stage_warning = True
                elif status == "Failed" and (tr.task.on_error if tr.task else "fail") == "fail":
                    stage_failed = True
            else:
                # Parallel — fan out in threads, join
                results: dict[str, tuple[str, bool]] = {}

                def _run_task(tr_id: str) -> None:
                    with app.app_context():
                        _tr = db.session.get(TaskRun, tr_id)
                        on_err = _tr.task.on_error if _tr and _tr.task else "fail"
                    s, w = _execute_task_run(
                        app, run_id, sr_id, tr_id, dict(env), pipeline_so_far_status
                    )
                    results[tr_id] = (s, w, on_err)

                threads = []
                for tr in tgroup:
                    t = threading.Thread(target=_run_task, args=(tr.id,), daemon=True)
                    t.start()
                    threads.append(t)
                for t in threads:
                    t.join()

                for tr_id_key, (s, w, on_err) in results.items():
                    if w:
                        stage_warning = True
                    elif s == "Failed" and on_err == "fail":
                        stage_failed = True

        # ── Exit gate ─────────────────────────────────────────────────────────
        if stage and not stage_failed:
            exit_cfg = json.loads(stage.exit_gate or "{}")
            if exit_cfg.get("enabled"):
                exit_env = {**env, "CDT_STAGE_STATUS": "Warning" if stage_warning else "Succeeded"}
                passed, logs = _run_gate_script(
                    exit_cfg.get("language", "bash"),
                    exit_cfg.get("script", ""),
                    int(exit_cfg.get("timeout", 60)),
                    exit_env,
                    f"exit-gate:{stage.name}",
                )
                props = json.loads(sr.runtime_properties or "{}")
                props["exit_gate"] = {"passed": passed, "logs": logs}
                sr.runtime_properties = json.dumps(props)
                db.session.commit()
                if not passed:
                    stage_failed = True

        sr.status = (
            RunStatus.FAILED
            if stage_failed
            else ("Warning" if stage_warning else RunStatus.SUCCEEDED)
        )
        sr.finished_at = _now()
        db.session.commit()
        stage_run_finished(sr)
        return stage_failed, stage_warning


def _group_stage_runs(stage_runs: list) -> list[list]:
    """Group stage runs into sequential batches.

    Consecutive stages with execution_mode='parallel' are placed in the same
    batch and run concurrently; all other stages get their own single-element batch.
    """
    groups: list[list] = []
    for sr in stage_runs:
        mode = (sr.stage.execution_mode or "sequential") if sr.stage else "sequential"
        if mode == "parallel" and groups and len(groups[-1]) > 0:
            prev_mode = (
                (groups[-1][-1].stage.execution_mode or "sequential")
                if groups[-1][-1].stage
                else "sequential"
            )
            if prev_mode == "parallel":
                groups[-1].append(sr)
                continue
        groups.append([sr])
    return groups


def _execute_pipeline_async(app: Any, pipeline_run_id: str) -> None:
    """Background thread: execute all stages, respecting per-stage execution_mode.

    Consecutive stages marked execution_mode='parallel' run concurrently in
    separate threads; sequential stages (the default) run one after another.
    """

    def _now() -> datetime:
        return datetime.now(UTC)

    with app.app_context():
        run = db.session.get(PipelineRun, pipeline_run_id)
        if not run:
            return

        stage_runs = sorted(run.stage_runs, key=lambda sr: sr.stage.order)
        pipeline_warning = False
        pipeline = run.pipeline

        context_env: dict[str, str] = {
            "CDT_PIPELINE_RUN_ID": run.id,
            "CDT_PIPELINE_ID": run.pipeline_id,
            "CDT_PIPELINE_NAME": pipeline.name if pipeline else "",
            "CDT_COMMIT_SHA": run.commit_sha or "",
            "CDT_ARTIFACT_ID": run.artifact_id or "",
            "CDT_TRIGGERED_BY": run.triggered_by or "",
            "CDT_GIT_REPO": (pipeline.git_repo or "") if pipeline else "",
            "CDT_GIT_BRANCH": (pipeline.git_branch or "main") if pipeline else "main",
        }

        groups = _group_stage_runs(stage_runs)
        pipeline_so_far = "Succeeded"

        for group in groups:
            if len(group) == 1:
                # Sequential — execute inline
                sr = group[0]
                stage = sr.stage
                # Check stage run_condition
                if not _evaluate_run_condition(
                    stage.run_condition if stage else None, pipeline_so_far
                ):
                    sr.status = "Skipped"
                    sr.finished_at = _now()
                    for tr in sr.task_runs:
                        tr.status = "Skipped"
                        tr.finished_at = _now()
                    db.session.commit()
                    failed, warned = False, False
                else:
                    sr.status = RunStatus.RUNNING
                    sr.started_at = _now()
                    db.session.commit()
                    failed, warned = _execute_stage(
                        app, run.id, sr.id, context_env, pipeline_so_far
                    )
            else:
                # Parallel group — mark all running, then fan-out via threads
                results: dict[str, tuple[bool, bool]] = {}
                threads = []
                for sr in group:
                    sr.status = RunStatus.RUNNING
                    sr.started_at = _now()
                db.session.commit()

                def _run_and_collect(sr_id: str) -> None:
                    f, w = _execute_stage(
                        app, pipeline_run_id, sr_id, dict(context_env), pipeline_so_far
                    )
                    results[sr_id] = (f, w)

                for sr in group:
                    t = threading.Thread(target=_run_and_collect, args=(sr.id,), daemon=True)
                    t.start()
                    threads.append(t)
                for t in threads:
                    t.join()

                failed = any(r[0] for r in results.values())
                warned = any(r[1] for r in results.values())

            # Update rolling status for next stage's run_condition evaluation
            if failed:
                pipeline_so_far = "Failed"
            elif warned:
                pipeline_so_far = "Warning"

            if failed:
                # Cancel all remaining stage-runs not yet started
                started_ids = {sr.id for sr in group}
                for rem_sr in stage_runs:
                    if rem_sr.id not in started_ids and rem_sr.status not in (
                        RunStatus.SUCCEEDED,
                        RunStatus.FAILED,
                        "Warning",
                        "Cancelled",
                    ):
                        rem_sr.status = "Cancelled"
                        for rem_tr in rem_sr.task_runs:
                            rem_tr.status = "Cancelled"
                db.session.commit()
                run.status = RunStatus.FAILED
                run.finished_at = _now()
                db.session.commit()
                _post_run_hooks(run)
                pipeline_run_finished(run)
                return

            if warned:
                pipeline_warning = True

        run.status = "Warning" if pipeline_warning else RunStatus.SUCCEEDED
        run.finished_at = _now()
        db.session.commit()
        _post_run_hooks(run)
        pipeline_run_finished(run)


def restart_from_stage(
    pipeline_run_id: str,
    stage_run_id: str,
    triggered_by: str = "system",
    app: Any = None,
) -> PipelineRun:
    """Create a new PipelineRun that re-executes from the given stage onwards.

    Copies commit_sha/artifact_id from the original run and seeds StageRun/TaskRun
    records only for stages at or after the target stage (earlier stages are seeded
    as Succeeded so they appear in the flow graph).
    """
    original = db.get_or_404(PipelineRun, pipeline_run_id)
    original_sr = db.get_or_404(StageRun, stage_run_id)

    # Determine the order of the restart point
    restart_order = original_sr.stage.order if original_sr.stage else 0

    pipeline = db.get_or_404(Pipeline, original.pipeline_id)

    new_run = PipelineRun(
        id=pipeline_run_id(),
        pipeline_id=original.pipeline_id,
        status=RunStatus.RUNNING,
        commit_sha=original.commit_sha,
        artifact_id=original.artifact_id,
        compliance_rating=pipeline.compliance_rating,
        compliance_score=pipeline.compliance_score,
        triggered_by=triggered_by,
        runtime_properties=original.runtime_properties or "{}",
        started_at=datetime.now(UTC),
    )
    db.session.add(new_run)

    for stage in sorted(pipeline.stages, key=lambda s: s.order):
        if stage.order < restart_order:
            # Keep earlier stages as already-succeeded placeholders
            sr = StageRun(
                id=resource_id("srun"),
                pipeline_run_id=new_run.id,
                stage_id=stage.id,
                status=RunStatus.SUCCEEDED,
                runtime_properties="{}",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
            db.session.add(sr)
            db.session.flush()
            for task in sorted(stage.tasks, key=lambda t: t.order):
                tr = TaskRun(
                    id=resource_id("trun"),
                    task_id=task.id,
                    stage_run_id=sr.id,
                    status=RunStatus.SUCCEEDED,
                    logs="(skipped — restarted from later stage)",
                    started_at=datetime.now(UTC),
                    finished_at=datetime.now(UTC),
                )
                db.session.add(tr)
        else:
            sr = StageRun(
                id=resource_id("srun"),
                pipeline_run_id=new_run.id,
                stage_id=stage.id,
                status=RunStatus.PENDING,
                runtime_properties="{}",
            )
            db.session.add(sr)
            db.session.flush()
            for task in sorted(stage.tasks, key=lambda t: t.order):
                tr = TaskRun(
                    id=resource_id("trun"),
                    task_id=task.id,
                    stage_run_id=sr.id,
                    status="Pending",
                    logs="",
                )
                db.session.add(tr)

    db.session.commit()

    record_event(
        "pipeline.run.restarted",
        triggered_by,
        "pipeline_run",
        new_run.id,
        "create",
        detail={"original_run_id": pipeline_run_id, "restart_from_stage": stage_run_id},
    )

    if app and pipeline.stages:
        thread = threading.Thread(
            target=_execute_pipeline_async,
            args=(app, new_run.id),
            daemon=True,
        )
        thread.start()

    return new_run


def update_run_status(run: PipelineRun | ReleaseRun, new_status: str) -> PipelineRun | ReleaseRun:
    """Transition a run to a new status."""
    run.status = new_status
    if new_status in TERMINAL_STATUSES:
        run.finished_at = datetime.now(UTC)
    db.session.commit()
    return run


def _post_run_hooks(run: PipelineRun) -> None:
    """Run side-effects after a pipeline run reaches a terminal state.

    Currently performs two updates:
    1. **App Dictionary** — if the pipeline is linked to an application and the
       run carries an artifact_id or commit_sha, update that application's
       ``build_version`` to reflect the latest successful build.
    2. **Compliance score** — recalculate the pipeline's compliance score from
       the current ratio of required/best-practice/runtime tasks so the dashboard
       shows up-to-date numbers without a manual refresh.
    """
    import logging  # noqa: PLC0415

    log = logging.getLogger(__name__)

    pipeline = run.pipeline
    if not pipeline:
        return

    # 1. Update App Dictionary build_version on successful runs
    if run.status == RunStatus.SUCCEEDED and pipeline.application_id:
        new_version = run.artifact_id or run.commit_sha
        if new_version:
            app_artifact = db.session.get(ApplicationArtifact, pipeline.application_id)
            if app_artifact:
                app_artifact.build_version = new_version
                log.info(
                    "app_dict_updated",
                    extra={
                        "application_id": app_artifact.id,
                        "application_name": app_artifact.name,
                        "build_version": new_version,
                        "pipeline_run_id": run.id,
                    },
                )

    # 2. Recalculate compliance score
    try:
        from app.services.pipeline_service import update_compliance_score  # noqa: PLC0415

        stages = pipeline.stages or []
        tasks = [t for s in stages for t in (s.tasks or [])]
        total = len(tasks)
        if total > 0:
            mandatory = sum(1 for t in tasks if getattr(t, "is_required", False)) / total * 100
            update_compliance_score(
                product_id=pipeline.product_id,
                pipeline_id=pipeline.id,
                mandatory_pct=mandatory,
                best_practice_pct=0.0,
                runtime_pct=0.0,
                metadata_pct=0.0,
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("compliance_rescore_failed pipeline=%s error=%s", pipeline.id, exc)

    db.session.commit()


def start_release_run(
    release_id: str,
    triggered_by: str = "system",
    app: Any = None,
) -> ReleaseRun:
    """Create a ReleaseRun and execute its application group pipelines."""
    release = db.get_or_404(Release, release_id)
    run = ReleaseRun(
        id=release_run_id(),
        release_id=release_id,
        status=RunStatus.RUNNING,
        triggered_by=triggered_by,
    )
    db.session.add(run)
    db.session.commit()
    record_event(
        "release.run.started",
        triggered_by,
        "release_run",
        run.id,
        "create",
        detail={"release_id": release_id},
    )

    groups = sorted(release.application_groups, key=lambda g: g.order)
    if app and groups:
        thread = threading.Thread(
            target=_execute_release_async,
            args=(app, run.id, triggered_by),
            daemon=True,
        )
        thread.start()
    elif not groups:
        run.status = RunStatus.SUCCEEDED
        run.finished_at = datetime.now(UTC)
        db.session.commit()

    return run


def _execute_release_async(app: Any, rrun_id: str, triggered_by: str) -> None:
    """Execute release application groups sequentially; pipelines within each group
    run in parallel or sequentially based on the group's execution_mode."""
    with app.app_context():
        from app.models.release import ReleaseRun as _RR

        rrun = db.session.get(_RR, rrun_id)
        if not rrun:
            return

        release = rrun.release
        groups = sorted(release.application_groups, key=lambda g: g.order)

        for group in groups:
            pipeline_ids = json.loads(group.pipeline_ids or "[]")
            if not pipeline_ids:
                continue

            if group.execution_mode == "parallel":
                # Start all pipelines in the group simultaneously
                pipeline_runs = []
                for pid in pipeline_ids:
                    pr = start_pipeline_run(
                        pipeline_id=pid,
                        triggered_by=triggered_by,
                        app=app,
                    )
                    pr.release_run_id = rrun.id
                    db.session.commit()
                    pipeline_runs.append(pr)
                # Poll until all complete
                _wait_for_pipeline_runs(app, [pr.id for pr in pipeline_runs])
            else:
                # Sequential: run each pipeline one at a time
                for pid in pipeline_ids:
                    pr = start_pipeline_run(
                        pipeline_id=pid,
                        triggered_by=triggered_by,
                        app=app,
                    )
                    pr.release_run_id = rrun.id
                    db.session.commit()
                    _wait_for_pipeline_runs(app, [pr.id])

        rrun.status = RunStatus.SUCCEEDED
        rrun.finished_at = datetime.now(UTC)
        db.session.commit()


def _wait_for_pipeline_runs(app: Any, run_ids: list[str], poll_interval: float = 2.0) -> None:
    """Block until all given pipeline runs reach a terminal status."""
    import time

    with app.app_context():
        while True:
            pending = []
            for rid in run_ids:
                pr = db.session.get(PipelineRun, rid)
                if pr and pr.status not in TERMINAL_STATUSES:
                    pending.append(rid)
            if not pending:
                break
            time.sleep(poll_interval)
