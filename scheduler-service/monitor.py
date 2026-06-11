# Copyright 2026 Emin Askerov
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Async execution monitor — polls active executions and finalises completed ones."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.models import DurableExecStatus, Execution, ExecutionBackend, StandardExecStatus
from synteles_db.repos.executions import ExecutionRepo

from backends import get_backend
from backends.base import ExecutionBackendRunner, ExecutionStatus
from config import MONITOR_INTERVAL_SECONDS, S3_LOGS_BUCKET, SIGNAL_WAIT_TIMEOUT_SECONDS
from db import AsyncSessionLocal, get_s3

logger = logging.getLogger(__name__)


def _upload_logs_to_s3(execution_id: str, logs: str) -> str | None:
    """Upload logs text to S3 and return the s3:// URI, or None on failure.

    Args:
        execution_id: The execution UUID as a string, used to construct the S3 key.
        logs: The log content to upload.

    Returns:
        The ``s3://`` URI of the uploaded object, or ``None`` if the upload failed.
    """
    key = f"executions/{execution_id}/logs.txt"
    try:
        get_s3().put_object(
            Bucket=S3_LOGS_BUCKET,
            Key=key,
            Body=logs.encode("utf-8"),
            ContentType="text/plain",
        )
        return f"s3://{S3_LOGS_BUCKET}/{key}"
    except Exception as exc:
        logger.warning("Failed to upload logs for %s: %s", execution_id, exc)
        return None


async def _finalize(
    execution: Execution,
    db_status: StandardExecStatus | DurableExecStatus,
    backend: ExecutionBackendRunner,
    db: AsyncSession,
) -> None:
    """Retrieve logs, upload to S3, update DB status, then stop the job.

    For standard executions: stops the Docker container.
    For durable executions: cancels the Temporal workflow and stops the agent-worker container.
    """
    logs_s3_uri: str | None = None
    if execution.job_ref:
        logs = await backend.logs(execution.job_ref)
        if logs:
            logs_s3_uri = _upload_logs_to_s3(str(execution.id), logs)
    await ExecutionRepo(db).update_status(
        execution,
        db_status,
        completed_at=datetime.now(UTC),
        logs_s3_uri=logs_s3_uri,
    )
    await db.commit()
    if execution.job_ref:
        await backend.stop(execution.job_ref)


async def _sync_durable_signal_status(
    execution: Execution, backend: ExecutionBackendRunner
) -> None:
    """Sync DB status with the AgentWorkflow's is_input_needed query result.

    running → waiting_for_signal when the workflow pauses for user input.
    waiting_for_signal → running when the signal has been delivered and work resumes.
    """
    is_input_needed = await backend.query_is_input_needed(execution.job_ref)
    if is_input_needed is None:
        return

    db_status = execution.status
    if is_input_needed and db_status == DurableExecStatus.running:
        async with AsyncSessionLocal() as db:
            fresh = await ExecutionRepo(db).get_by_id(execution.id)
            if fresh and fresh.status == DurableExecStatus.running:
                signal_timeout_at = datetime.now(UTC) + timedelta(
                    seconds=SIGNAL_WAIT_TIMEOUT_SECONDS
                )
                await ExecutionRepo(db).update_status(
                    fresh,
                    DurableExecStatus.waiting_for_signal,
                    timeout_at=signal_timeout_at,
                )
                await db.commit()
                logger.info(
                    "Execution %s is waiting for user input (signal timeout at %s)",
                    execution.id,
                    signal_timeout_at,
                )
    elif not is_input_needed and db_status == DurableExecStatus.waiting_for_signal:
        async with AsyncSessionLocal() as db:
            fresh = await ExecutionRepo(db).get_by_id(execution.id)
            if fresh and fresh.status == DurableExecStatus.waiting_for_signal:
                await ExecutionRepo(db).update_status(fresh, DurableExecStatus.running)
                await db.commit()
                logger.info("Execution %s resumed after signal", execution.id)


async def _poll() -> None:
    """Check all active executions once and finalise any that have finished."""
    now = datetime.now(UTC)
    # Fetch the list of active executions in one short-lived session
    async with AsyncSessionLocal() as db:
        executions = await ExecutionRepo(db).list_active()

    # Build one backend instance per execution type present in this tick's batch.
    # get_backend() calls DockerRuntime() → docker.from_env(); doing it per-execution
    # would open a Docker socket connection for every active execution on every poll.
    backends = {
        ExecutionBackend(e.execution_type): get_backend(ExecutionBackend(e.execution_type))
        for e in executions
        if e.job_ref
    }

    # Finalise each execution in its own independent session
    for execution in executions:
        if not execution.job_ref:
            continue
        try:
            exec_type = ExecutionBackend(execution.execution_type)
            backend = backends[exec_type]
            stopped = (
                DurableExecStatus.stopped
                if exec_type == ExecutionBackend.durable
                else StandardExecStatus.stopped
            )
            completed = (
                DurableExecStatus.completed
                if exec_type == ExecutionBackend.durable
                else StandardExecStatus.completed
            )
            failed = (
                DurableExecStatus.failed
                if exec_type == ExecutionBackend.durable
                else StandardExecStatus.failed
            )
            if execution.timeout_at and execution.timeout_at < now:
                async with AsyncSessionLocal() as db:
                    fresh = await ExecutionRepo(db).get_by_id(execution.id)
                    if fresh:
                        await _finalize(fresh, stopped, backend, db)
                continue
            status = await backend.status(execution.job_ref)
            if status == ExecutionStatus.COMPLETED:
                async with AsyncSessionLocal() as db:
                    fresh = await ExecutionRepo(db).get_by_id(execution.id)
                    if fresh:
                        await _finalize(fresh, completed, backend, db)
            elif status == ExecutionStatus.FAILED:
                async with AsyncSessionLocal() as db:
                    fresh = await ExecutionRepo(db).get_by_id(execution.id)
                    if fresh:
                        await _finalize(fresh, failed, backend, db)
            elif status == ExecutionStatus.RUNNING and exec_type == ExecutionBackend.durable:
                await _sync_durable_signal_status(execution, backend)
                if not backend.container_alive(execution.job_ref):
                    async with AsyncSessionLocal() as db:
                        fresh = await ExecutionRepo(db).get_by_id(execution.id)
                        if fresh:
                            from worker_restart import ensure_worker_running

                            await ensure_worker_running(fresh, db)
        except Exception as exc:
            logger.error("Failed to finalize execution %s: %s", execution.id, exc)


async def monitor_loop() -> None:
    """Run the poll loop forever, catching all errors so the loop never dies."""
    while True:
        try:
            await _poll()
        except Exception as exc:
            logger.error("Monitor poll error: %s", exc)
        await asyncio.sleep(MONITOR_INTERVAL_SECONDS)
