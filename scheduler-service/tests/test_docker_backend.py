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

"""Tests for DockerBackend.status() and DockerBackend.logs()."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import docker.errors
import pytest

from backends.base import ExecutionStatus
from backends.docker_backend import DockerBackend


@pytest.fixture
def mock_client() -> MagicMock:  # type: ignore[misc]
    with patch("backends.docker_backend.docker.from_env") as mock_from_env:
        client = MagicMock()
        mock_from_env.return_value = client
        yield client


@pytest.fixture
def backend(mock_client: MagicMock) -> DockerBackend:
    return DockerBackend()


# ---------------------------------------------------------------------------
# status() tests
# ---------------------------------------------------------------------------


async def test_status_running(backend: DockerBackend, mock_client: MagicMock) -> None:
    container = MagicMock()
    container.status = "running"
    mock_client.containers.get.return_value = container

    assert await backend.status("abc123") == ExecutionStatus.RUNNING
    container.reload.assert_called_once()


async def test_status_created(backend: DockerBackend, mock_client: MagicMock) -> None:
    container = MagicMock()
    container.status = "created"
    mock_client.containers.get.return_value = container

    assert await backend.status("abc123") == ExecutionStatus.RUNNING


async def test_status_restarting(backend: DockerBackend, mock_client: MagicMock) -> None:
    container = MagicMock()
    container.status = "restarting"
    mock_client.containers.get.return_value = container

    assert await backend.status("abc123") == ExecutionStatus.RUNNING


async def test_status_exited_zero(backend: DockerBackend, mock_client: MagicMock) -> None:
    container = MagicMock()
    container.status = "exited"
    container.attrs = {"State": {"ExitCode": 0}}
    mock_client.containers.get.return_value = container

    assert await backend.status("abc123") == ExecutionStatus.COMPLETED


async def test_status_exited_nonzero(backend: DockerBackend, mock_client: MagicMock) -> None:
    container = MagicMock()
    container.status = "exited"
    container.attrs = {"State": {"ExitCode": 1}}
    mock_client.containers.get.return_value = container

    assert await backend.status("abc123") == ExecutionStatus.FAILED


async def test_status_not_found(backend: DockerBackend, mock_client: MagicMock) -> None:
    mock_client.containers.get.side_effect = docker.errors.NotFound("not found")

    assert await backend.status("abc123") == ExecutionStatus.FAILED


# ---------------------------------------------------------------------------
# logs() tests
# ---------------------------------------------------------------------------


async def test_logs_returns_decoded_bytes(backend: DockerBackend, mock_client: MagicMock) -> None:
    container = MagicMock()
    container.logs.return_value = b"hello\nworld"
    mock_client.containers.get.return_value = container

    result = await backend.logs("abc123")

    assert result == "hello\nworld"
    container.logs.assert_called_once_with(stdout=True, stderr=True)


async def test_logs_not_found_returns_empty(backend: DockerBackend, mock_client: MagicMock) -> None:
    mock_client.containers.get.side_effect = docker.errors.NotFound("not found")

    assert await backend.logs("abc123") == ""


# ---------------------------------------------------------------------------
# submit() tests
# ---------------------------------------------------------------------------


async def test_submit_returns_container_id(backend: DockerBackend, mock_client: MagicMock) -> None:
    container = MagicMock()
    container.id = "deadbeef"
    mock_client.containers.run.return_value = container

    from backends.base import ExecutionConfig

    config = ExecutionConfig(
        execution_id="exec-1",
        image="synteles/agentlet-core:latest",
        env={"KEY": "VALUE"},
        timeout_seconds=300,
    )
    result = await backend.submit(config)

    assert result == "deadbeef"
    mock_client.containers.run.assert_called_once_with(
        "synteles/agentlet-core:latest",
        detach=True,
        name="exec-1",
        environment={"KEY": "VALUE"},
        network=None,  # DOCKER_NETWORK="" → None
    )


async def test_submit_with_network(backend: DockerBackend, mock_client: MagicMock) -> None:
    backend._network = "platform-infra_default"
    container = MagicMock()
    container.id = "cafebabe"
    mock_client.containers.run.return_value = container

    from backends.base import ExecutionConfig

    config = ExecutionConfig(
        execution_id="exec-2",
        image="synteles/agentlet-core:latest",
        env={},
        timeout_seconds=300,
    )
    await backend.submit(config)

    mock_client.containers.run.assert_called_once_with(
        "synteles/agentlet-core:latest",
        detach=True,
        name="exec-2",
        environment={},
        network="platform-infra_default",
    )


# ---------------------------------------------------------------------------
# stop() tests
# ---------------------------------------------------------------------------


async def test_stop_running_container(backend: DockerBackend, mock_client: MagicMock) -> None:
    container = MagicMock()
    container.status = "running"
    mock_client.containers.get.return_value = container

    await backend.stop("abc123")

    container.stop.assert_called_once_with(timeout=10)
    container.remove.assert_called_once_with(force=True)


async def test_stop_stopped_container(backend: DockerBackend, mock_client: MagicMock) -> None:
    container = MagicMock()
    container.status = "exited"
    mock_client.containers.get.return_value = container

    await backend.stop("abc123")

    container.stop.assert_not_called()
    container.remove.assert_called_once_with(force=True)


async def test_stop_not_found_is_noop(backend: DockerBackend, mock_client: MagicMock) -> None:
    mock_client.containers.get.side_effect = docker.errors.NotFound("not found")

    await backend.stop("abc123")  # must not raise
