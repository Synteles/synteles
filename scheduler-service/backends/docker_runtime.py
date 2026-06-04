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

"""Docker container runtime — low-level container lifecycle operations."""

from __future__ import annotations

import docker
import docker.errors

from backends.base import ExecutionStatus
from config import DOCKER_NETWORK


class DockerRuntime:
    """Manages Docker container lifecycle: run, stop, status, logs."""

    def __init__(self) -> None:
        self._client: docker.DockerClient = docker.from_env()
        self._network: str = DOCKER_NETWORK

    def run_container(self, image: str, name: str, env: dict[str, str]) -> str:
        """Start a detached container and return its container ID."""
        container = self._client.containers.run(
            image,
            detach=True,
            name=name,
            environment=env,
            network=self._network or None,
        )
        return str(container.id)

    def stop_container(self, name_or_id: str) -> None:
        """Stop and remove a container by name or ID. No-op if not found."""
        try:
            container = self._client.containers.get(name_or_id)
            if container.status == "running":
                container.stop(timeout=10)
            container.remove(force=True)
        except docker.errors.NotFound:
            pass

    def container_status(self, name_or_id: str) -> ExecutionStatus:
        """Return the current ExecutionStatus of a container."""
        try:
            container = self._client.containers.get(name_or_id)
            container.reload()
            if container.status == "exited":
                exit_code: int = container.attrs["State"]["ExitCode"]
                return ExecutionStatus.COMPLETED if exit_code == 0 else ExecutionStatus.FAILED
            return ExecutionStatus.RUNNING
        except docker.errors.NotFound:
            return ExecutionStatus.FAILED

    def container_logs(self, name_or_id: str) -> str:
        """Return combined stdout/stderr logs. Returns empty string if not found."""
        try:
            container = self._client.containers.get(name_or_id)
            raw: bytes = container.logs(stdout=True, stderr=True)
            return raw.decode("utf-8", errors="replace")
        except docker.errors.NotFound:
            return ""
