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

"""Tests for cancel_execution route."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from synteles_db.models import ExecStatus, ExecutionBackend

from auth import TokenClaims


@pytest.fixture
def app() -> FastAPI:
    from routers.management import router

    _app = FastAPI()
    _app.include_router(router)
    return _app


@pytest.fixture
def mock_claims() -> MagicMock:
    claims = MagicMock(spec=TokenClaims)
    claims.sub = "user-1"
    claims.org_id = "00000000-0000-0000-0000-000000000001"
    return claims


def _make_execution(status: ExecStatus, exec_id: UUID | None = None) -> MagicMock:
    execution = MagicMock()
    execution.id = exec_id or uuid4()
    execution.org_id = UUID("00000000-0000-0000-0000-000000000001")
    execution.status = status
    execution.execution_type = ExecutionBackend.standard
    execution.completed_at = None
    execution.job_ref = "container-xyz"
    return execution


async def test_cancel_active_execution_calls_finalize(app: FastAPI, mock_claims: MagicMock) -> None:
    exec_id = uuid4()
    execution = _make_execution(ExecStatus.running, exec_id)

    mock_db = AsyncMock()
    mock_backend = MagicMock()

    from auth import trusted_claims
    from db import get_db

    app.dependency_overrides[trusted_claims] = lambda: mock_claims
    app.dependency_overrides[get_db] = lambda: mock_db

    with (
        patch("routers.management.ExecutionRepo") as mock_repo_cls,
        patch("routers.management.get_backend", return_value=mock_backend),
        patch("routers.management._finalize", new_callable=AsyncMock) as mock_finalize,
    ):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=execution)
        mock_repo_cls.return_value = mock_repo

        client = TestClient(app, raise_server_exceptions=True)
        response = client.post(f"/api/executions/{exec_id}/cancel")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_finalize.assert_awaited_once_with(execution, ExecStatus.stopped, mock_backend, mock_db)


async def test_cancel_terminal_execution_skips_finalize(
    app: FastAPI, mock_claims: MagicMock
) -> None:
    exec_id = uuid4()
    execution = _make_execution(ExecStatus.completed, exec_id)

    mock_db = AsyncMock()

    from auth import trusted_claims
    from db import get_db

    app.dependency_overrides[trusted_claims] = lambda: mock_claims
    app.dependency_overrides[get_db] = lambda: mock_db

    with (
        patch("routers.management.ExecutionRepo") as mock_repo_cls,
        patch("routers.management._finalize", new_callable=AsyncMock) as mock_finalize,
    ):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=execution)
        mock_repo_cls.return_value = mock_repo

        client = TestClient(app, raise_server_exceptions=True)
        response = client.post(f"/api/executions/{exec_id}/cancel")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_finalize.assert_not_called()


async def test_cancel_not_found_returns_404(app: FastAPI, mock_claims: MagicMock) -> None:
    mock_db = AsyncMock()

    from auth import trusted_claims
    from db import get_db

    app.dependency_overrides[trusted_claims] = lambda: mock_claims
    app.dependency_overrides[get_db] = lambda: mock_db

    with (
        patch("routers.management.ExecutionRepo") as mock_repo_cls,
    ):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        client = TestClient(app, raise_server_exceptions=True)
        response = client.post(f"/api/executions/{uuid4()}/cancel")

    app.dependency_overrides.clear()

    assert response.status_code == 404
