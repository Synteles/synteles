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

# scheduler-service/backends/__init__.py
"""Execution backend factory."""

from __future__ import annotations

from backends.base import ExecutionBackend
from synteles_db.models import ExecutionType

_cache: dict[ExecutionType, ExecutionBackend] = {}


def get_backend(execution_type: ExecutionType = ExecutionType.standard) -> ExecutionBackend:
    """Return the backend for the given execution type, reusing a cached instance.

    Backends are stateless (all state flows through job_ref parameters), so a
    single instance per type is safe. Caching avoids docker.from_env() on every
    monitor tick.

    EXECUTION_RUNTIME selects the infrastructure provider (docker | k8s).
    execution_type selects the execution model (standard | durable).
    """
    if execution_type in _cache:
        return _cache[execution_type]

    from config import EXECUTION_RUNTIME

    if EXECUTION_RUNTIME == "docker":
        if execution_type == ExecutionType.durable:
            from backends.docker_durable import DockerDurableBackend

            backend: ExecutionBackend = DockerDurableBackend()
        else:
            from backends.docker_standard import DockerStandardBackend

            backend = DockerStandardBackend()
        _cache[execution_type] = backend
        return backend

    raise ValueError(f"Unknown EXECUTION_RUNTIME: {EXECUTION_RUNTIME!r}")
