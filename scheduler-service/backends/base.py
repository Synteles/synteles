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

"""Abstract execution backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


class ExecutionStatus(StrEnum):
    """Canonical execution status values."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class ExecutionConfig:
    """Parameters required to submit a new execution job."""

    execution_id: str
    image: str
    env: dict[str, str]
    timeout_seconds: int
    cpu: str = "256"
    memory: str = "512"


class ExecutionBackend(ABC):
    """Abstract interface for execution backends (ECS, Docker, K8s, …)."""

    @abstractmethod
    async def submit(self, config: ExecutionConfig) -> str:
        """Submit an execution and return the backend job reference (task ARN, container ID, etc.)."""
        ...

    @abstractmethod
    async def status(self, job_ref: str) -> ExecutionStatus:
        """Return the current status of a backend job."""
        ...

    @abstractmethod
    async def logs(self, job_ref: str) -> str:
        """Return combined log output for a completed or running job."""
        ...

    @abstractmethod
    async def stop(self, job_ref: str) -> None:
        """Request graceful termination of an active job."""
        ...
