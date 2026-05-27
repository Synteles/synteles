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


def get_backend() -> ExecutionBackend:
    """Return the configured execution backend."""
    from config import EXECUTION_BACKEND

    if EXECUTION_BACKEND == "docker":
        from backends.docker_backend import DockerBackend

        return DockerBackend()
    raise ValueError(f"Unknown EXECUTION_BACKEND: {EXECUTION_BACKEND!r}")
