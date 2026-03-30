"""Business logic for PipelineRun and ReleaseRun lifecycle management."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import RunStatus
from app.extensions import db
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


def _build_runtime_context(run: PipelineRun) -> dict:
    """Build the full pipelineRuntime context dict for injection into task scripts."""
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

    return {**pipeline_rt, "stageRuntime": stage_runtime}


def _execute_pipeline_async(app: Any, pipeline_run_id: str) -> None:
    """Background thread: execute all stages and tasks in order."""

    def _now() -> datetime:
        return datetime.now(UTC)

    with app.app_context():
        run = db.session.get(PipelineRun, pipeline_run_id)
        if not run:
            return

        stage_runs = sorted(run.stage_runs, key=lambda sr: sr.stage.order)
        pipeline_warning = False

        # Build base context env vars accessible as $RW_* in all task scripts
        pipeline = run.pipeline
        context_env: dict[str, str] = {
            "RW_PIPELINE_RUN_ID": run.id,
            "RW_PIPELINE_ID": run.pipeline_id,
            "RW_PIPELINE_NAME": pipeline.name if pipeline else "",
            "RW_COMMIT_SHA": run.commit_sha or "",
            "RW_ARTIFACT_ID": run.artifact_id or "",
            "RW_TRIGGERED_BY": run.triggered_by or "",
            "RW_GIT_REPO": (pipeline.git_repo or "") if pipeline else "",
            "RW_GIT_BRANCH": (pipeline.git_branch or "main") if pipeline else "main",
        }

        for sr in stage_runs:
            sr.status = RunStatus.RUNNING
            sr.started_at = _now()
            db.session.commit()

            context_env["RW_STAGE_RUN_ID"] = sr.id
            context_env["RW_STAGE_ID"] = sr.stage_id
            context_env["RW_STAGE_NAME"] = sr.stage.name if sr.stage else ""

            task_runs = sorted(sr.task_runs, key=lambda tr: tr.task.order)
            stage_failed = False
            stage_warning = False

            for tr in task_runs:
                task = tr.task
                tr.status = "Running"
                tr.started_at = _now()
                db.session.commit()

                # Build full runtime context from accumulated outputs so far
                runtime_ctx = _build_runtime_context(run)
                user_input = {}
                if tr.user_input:
                    try:
                        user_input = json.loads(tr.user_input)
                    except (ValueError, TypeError):
                        user_input = {}

                task_env = {
                    **context_env,
                    "RW_TASK_RUN_ID": tr.id,
                    "RW_TASK_ID": task.id,
                    "RW_TASK_NAME": task.name,
                    # Full runtime context as JSON string
                    "RW_RUNTIME": json.dumps(runtime_ctx),
                    "RW_USER_INPUT": json.dumps(user_input),
                }

                if _in_kubernetes():
                    rc, logs = _run_script_k8s(
                        task.run_language, task.run_code, task.timeout, tr.id
                    )
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

                if status == "Warning":
                    stage_warning = True
                elif status == "Failed" and task.on_error == "fail":
                    stage_failed = True
                    # Cancel remaining tasks in this stage
                    for remaining in task_runs[task_runs.index(tr) + 1 :]:
                        remaining.status = "Cancelled"
                        remaining.finished_at = _now()
                    db.session.commit()
                    break

            if stage_failed:
                sr.status = RunStatus.FAILED
                sr.finished_at = _now()
                db.session.commit()
                stage_run_finished(sr)
                # Cancel remaining stages
                remaining_stages = stage_runs[stage_runs.index(sr) + 1 :]
                for rem_sr in remaining_stages:
                    rem_sr.status = "Cancelled"
                    for rem_tr in rem_sr.task_runs:
                        rem_tr.status = "Cancelled"
                db.session.commit()
                run.status = RunStatus.FAILED
                run.finished_at = _now()
                db.session.commit()
                pipeline_run_finished(run)
                return

            sr.status = "Warning" if stage_warning else RunStatus.SUCCEEDED
            sr.finished_at = _now()
            db.session.commit()
            stage_run_finished(sr)

            if stage_warning:
                pipeline_warning = True

        run.status = "Warning" if pipeline_warning else RunStatus.SUCCEEDED
        run.finished_at = _now()
        db.session.commit()
        pipeline_run_finished(run)


def update_run_status(run: PipelineRun | ReleaseRun, new_status: str) -> PipelineRun | ReleaseRun:
    """Transition a run to a new status."""
    run.status = new_status
    if new_status in TERMINAL_STATUSES:
        run.finished_at = datetime.now(UTC)
    db.session.commit()
    return run


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
