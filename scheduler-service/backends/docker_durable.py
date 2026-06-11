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

"""Docker-backed durable execution backend — Temporal workflow + per-execution agent-worker container."""

from __future__ import annotations

import logging

from temporalio.client import WorkflowExecutionStatus
from temporalio.service import RPCError

from backends.base import ExecutionBackendRunner, ExecutionConfig, ExecutionStatus
from backends.docker_runtime import DockerRuntime
from config import AGENTLET_DURABLE_IMAGE, TEMPORAL_ADDRESS
from temporal_client import get_temporal_client

logger = logging.getLogger(__name__)


def _workflow_id(execution_id: str) -> str:
    """Canonical Temporal workflow ID for a given execution."""
    return f"synteles-{execution_id}"


def _container_name(execution_id: str) -> str:
    """Deterministic agent-worker container name for a given execution."""
    return f"agent-{execution_id}"


_TEMPORAL_STATUS_MAP: dict[WorkflowExecutionStatus, ExecutionStatus] = {
    WorkflowExecutionStatus.RUNNING: ExecutionStatus.RUNNING,
    WorkflowExecutionStatus.COMPLETED: ExecutionStatus.COMPLETED,
    WorkflowExecutionStatus.FAILED: ExecutionStatus.FAILED,
    WorkflowExecutionStatus.CANCELED: ExecutionStatus.STOPPED,
    WorkflowExecutionStatus.TERMINATED: ExecutionStatus.STOPPED,
    WorkflowExecutionStatus.CONTINUED_AS_NEW: ExecutionStatus.RUNNING,
    WorkflowExecutionStatus.TIMED_OUT: ExecutionStatus.FAILED,
}


class DockerDurableBackend(ExecutionBackendRunner):
    """Runs durable Temporal workflows via a per-execution agent-worker container.

    job_ref is the execution_id. Temporal workflow ID and container name are derived
    from it via _workflow_id() and _container_name() — both forward-only computations
    with no string parsing.

    submit() flow:
      1. Start the Temporal AgentWorkflow on a per-execution task queue.
      2. Launch the agent-worker container — registers AgentWorkflow + MCP servers,
         polls the per-execution task queue, picks up and runs the workflow.
      3. Return execution_id as job_ref.
    """

    def __init__(self) -> None:
        self._runtime = DockerRuntime()

    async def submit(self, config: ExecutionConfig) -> str:
        wf_id = _workflow_id(config.execution_id)
        task_queue = f"synteles-agent-{config.execution_id}"

        client = await get_temporal_client()
        await client.start_workflow(
            "AgentWorkflow",
            config.execution_id,
            id=wf_id,
            task_queue=task_queue,
        )
        logger.info("Started Temporal workflow %s on queue %s", wf_id, task_queue)

        container_env = {
            "TEMPORAL_ADDRESS": TEMPORAL_ADDRESS,
            "TEMPORAL_TASK_QUEUE": task_queue,
            "EXECUTION_ID": config.execution_id,
            **config.env,
        }
        cname = _container_name(config.execution_id)
        self._runtime.run_container(AGENTLET_DURABLE_IMAGE, cname, container_env)
        logger.info("Launched agent-worker container %s", cname)

        return config.execution_id

    async def status(self, job_ref: str) -> ExecutionStatus:
        try:
            client = await get_temporal_client()
            handle = client.get_workflow_handle(_workflow_id(job_ref))
            description = await handle.describe()
            status = description.status
            return (
                _TEMPORAL_STATUS_MAP.get(status, ExecutionStatus.RUNNING)
                if status is not None
                else ExecutionStatus.RUNNING
            )
        except RPCError as exc:
            # Transient RPC errors should not permanently fail the execution.
            # The monitor timeout mechanism handles truly stuck workflows.
            logger.warning("Could not query Temporal workflow for %s: %s", job_ref, exc)
            return ExecutionStatus.RUNNING

    async def logs(self, job_ref: str) -> str:
        return self._runtime.container_logs(_container_name(job_ref))

    def container_alive(self, job_ref: str) -> bool:
        return self._runtime.container_status(_container_name(job_ref)) == ExecutionStatus.RUNNING

    async def query_is_input_needed(self, job_ref: str) -> bool | None:
        try:
            client = await get_temporal_client()
            handle = client.get_workflow_handle(_workflow_id(job_ref))
            return bool(await handle.query("is_input_needed"))
        except RPCError as exc:
            logger.warning("Could not query is_input_needed for %s: %s", job_ref, exc)
            return None

    async def stop(self, job_ref: str) -> None:
        try:
            client = await get_temporal_client()
            handle = client.get_workflow_handle(_workflow_id(job_ref))
            await handle.cancel()
        except RPCError as exc:
            logger.warning("Could not cancel Temporal workflow for %s: %s", job_ref, exc)

        cname = _container_name(job_ref)
        self._runtime.stop_container(cname)
        logger.info("Stopped agent-worker container %s", cname)
