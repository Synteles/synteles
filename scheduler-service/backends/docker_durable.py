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

from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.service import RPCError

from backends.base import ExecutionBackend, ExecutionConfig, ExecutionStatus
from backends.docker_runtime import DockerRuntime
from config import AGENT_WORKER_IMAGE, TEMPORAL_ADDRESS

logger = logging.getLogger(__name__)

_TEMPORAL_STATUS_MAP: dict[WorkflowExecutionStatus, ExecutionStatus] = {
    WorkflowExecutionStatus.RUNNING: ExecutionStatus.RUNNING,
    WorkflowExecutionStatus.COMPLETED: ExecutionStatus.COMPLETED,
    WorkflowExecutionStatus.FAILED: ExecutionStatus.FAILED,
    WorkflowExecutionStatus.CANCELED: ExecutionStatus.STOPPED,
    WorkflowExecutionStatus.TERMINATED: ExecutionStatus.STOPPED,
    WorkflowExecutionStatus.CONTINUED_AS_NEW: ExecutionStatus.RUNNING,
    WorkflowExecutionStatus.TIMED_OUT: ExecutionStatus.FAILED,
}


class DockerDurableBackend(ExecutionBackend):
    """Runs durable Temporal workflows via a per-execution agent-worker container.

    submit() flow:
      1. Start the Temporal AgentWorkflow on a per-execution task queue.
      2. Launch the agent-worker container — registers AgentWorkflow + MCP servers,
         polls the per-execution task queue, picks up and runs the workflow.
      3. Return the Temporal workflow ID as job_ref.

    The agent-worker container name is deterministic (agent-{execution_id}) so
    stop() can clean it up without storing a separate container ID in the DB.
    """

    def __init__(self) -> None:
        self._runtime = DockerRuntime()

    async def submit(self, config: ExecutionConfig) -> str:
        workflow_id = f"synteles-{config.execution_id}"
        task_queue = f"synteles-agent-{config.execution_id}"

        client = await Client.connect(TEMPORAL_ADDRESS)
        await client.start_workflow(
            "AgentWorkflow",
            config.env,
            id=workflow_id,
            task_queue=task_queue,
        )
        logger.info("Started Temporal workflow %s on queue %s", workflow_id, task_queue)

        # Phase 4: launch per-execution agent-worker container.
        # Container receives execution secrets + MCP server config as env vars.
        container_env = {
            "TEMPORAL_ADDRESS": TEMPORAL_ADDRESS,
            "TEMPORAL_TASK_QUEUE": task_queue,
            "EXECUTION_ID": config.execution_id,
            **config.env,
        }
        container_name = f"agent-{config.execution_id}"
        self._runtime.run_container(AGENT_WORKER_IMAGE, container_name, container_env)
        logger.info("Launched agent-worker container %s", container_name)

        return workflow_id

    async def status(self, job_ref: str) -> ExecutionStatus:
        """Poll Temporal for workflow status. job_ref is the Temporal workflow ID."""
        try:
            client = await Client.connect(TEMPORAL_ADDRESS)
            handle = client.get_workflow_handle(job_ref)
            description = await handle.describe()
            return _TEMPORAL_STATUS_MAP.get(description.status, ExecutionStatus.RUNNING)
        except RPCError as exc:
            logger.warning("Could not query Temporal workflow %s: %s", job_ref, exc)
            return ExecutionStatus.FAILED

    async def logs(self, job_ref: str) -> str:
        """Fetch logs from the agent-worker container."""
        execution_id = job_ref.removeprefix("synteles-")
        return self._runtime.container_logs(f"agent-{execution_id}")

    async def stop(self, job_ref: str) -> None:
        """Cancel the Temporal workflow and stop the agent-worker container."""
        try:
            client = await Client.connect(TEMPORAL_ADDRESS)
            handle = client.get_workflow_handle(job_ref)
            await handle.cancel()
        except RPCError as exc:
            logger.warning("Could not cancel Temporal workflow %s: %s", job_ref, exc)

        execution_id = job_ref.removeprefix("synteles-")
        container_name = f"agent-{execution_id}"
        self._runtime.stop_container(container_name)
        logger.info("Stopped agent-worker container %s", container_name)
