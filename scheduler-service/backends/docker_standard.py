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

"""Docker-backed standard execution backend for short-lived agentlet containers."""

from __future__ import annotations

from backends.base import ExecutionBackendRunner, ExecutionConfig, ExecutionStatus
from backends.docker_runtime import DockerRuntime


class DockerStandardBackend(ExecutionBackendRunner):
    """Runs agentlet containers via Docker. One container per execution."""

    def __init__(self) -> None:
        self._runtime = DockerRuntime()

    async def submit(self, config: ExecutionConfig) -> str:
        return self._runtime.run_container(config.image, config.execution_id, config.env)

    async def status(self, job_ref: str) -> ExecutionStatus:
        return self._runtime.container_status(job_ref)

    async def logs(self, job_ref: str) -> str:
        return self._runtime.container_logs(job_ref)

    async def stop(self, job_ref: str) -> None:
        self._runtime.stop_container(job_ref)
