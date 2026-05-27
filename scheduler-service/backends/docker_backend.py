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

"""Docker execution backend."""

from __future__ import annotations

import docker
import docker.errors

from backends.base import ExecutionBackend, ExecutionConfig, ExecutionStatus
from config import DOCKER_NETWORK


class DockerBackend(ExecutionBackend):
    """Execution backend that runs agentlet containers via Docker."""

    def __init__(self) -> None:
        self._client: docker.DockerClient = docker.from_env()
        # DOCKER_NETWORK is referenced here to satisfy the import requirement;
        # it will be used in submit() (Task 3).
        self._network: str = DOCKER_NETWORK

    async def submit(self, config: ExecutionConfig) -> str:
        """Submit an execution job by running a Docker container.

        Args:
            config: Execution parameters including image, env vars, and ID.

        Returns:
            The Docker container ID as the job reference.
        """
        container = self._client.containers.run(
            config.image,
            detach=True,
            name=config.execution_id,
            environment=config.env,
            network=self._network or None,
        )
        return str(container.id)

    async def status(self, job_ref: str) -> ExecutionStatus:
        """Return the current status of a Docker container.

        Args:
            job_ref: Docker container ID or name.

        Returns:
            ExecutionStatus based on the container's current state.
        """
        try:
            container = self._client.containers.get(job_ref)
            container.reload()
            if container.status == "exited":
                exit_code: int = container.attrs["State"]["ExitCode"]
                return ExecutionStatus.COMPLETED if exit_code == 0 else ExecutionStatus.FAILED
            # "running", "created", "restarting", "paused", and any future status → RUNNING
            return ExecutionStatus.RUNNING
        except docker.errors.NotFound:
            return ExecutionStatus.FAILED

    async def logs(self, job_ref: str) -> str:
        """Return the combined stdout/stderr log output for a container.

        Args:
            job_ref: Docker container ID or name.

        Returns:
            Decoded log string, or empty string if the container is not found.
        """
        try:
            container = self._client.containers.get(job_ref)
            raw: bytes = container.logs(stdout=True, stderr=True)
            return raw.decode("utf-8", errors="replace")
        except docker.errors.NotFound:
            return ""

    async def stop(self, job_ref: str) -> None:
        """Stop and remove a Docker container.

        Stops the container only if it is currently running, then removes it
        unconditionally. If the container does not exist, the call is a no-op.

        Args:
            job_ref: Docker container ID or name.
        """
        try:
            container = self._client.containers.get(job_ref)
            if container.status == "running":
                container.stop(timeout=10)
            container.remove(force=True)
        except docker.errors.NotFound:
            pass
