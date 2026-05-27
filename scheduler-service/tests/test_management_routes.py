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

"""Tests for management router — helpers and list/get/logs/public routes.

Does NOT cover cancel_execution (already tested in test_cancel.py).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from synteles_db.models import ExecStatus

from auth import TokenClaims
from routers.management import (
    _calc_elapsed,
    _decode_offset_token,
    _encode_offset_token,
    _format_execution,
    _parse_dt,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

ORG_ID = "00000000-0000-0000-0000-000000000001"
OTHER_ORG_ID = "00000000-0000-0000-0000-000000000002"


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
    claims.org_id = ORG_ID
    return claims


def _make_execution(
    status: ExecStatus = ExecStatus.completed,
    org_id: str = ORG_ID,
    logs_s3_uri: str | None = None,
) -> MagicMock:
    e = MagicMock()
    e.id = uuid4()
    e.org_id = UUID(org_id)
    e.status = status
    e.agentlet_name = "my-agentlet"
    e.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    e.completed_at = datetime(2024, 1, 1, 1, tzinfo=UTC)  # 1 hour later
    e.logs_s3_uri = logs_s3_uri
    e.prompt = "test prompt"
    return e


# ---------------------------------------------------------------------------
# Pure helper tests — _encode_offset_token / _decode_offset_token
# ---------------------------------------------------------------------------


def test_encode_decode_zero() -> None:
    assert _decode_offset_token(_encode_offset_token(0)) == 0


def test_encode_decode_nonzero() -> None:
    assert _decode_offset_token(_encode_offset_token(50)) == 50


def test_decode_invalid_token_returns_zero() -> None:
    assert _decode_offset_token("!!!not-valid-base64!!!") == 0


def test_decode_empty_string_returns_zero() -> None:
    assert _decode_offset_token("") == 0


# ---------------------------------------------------------------------------
# Pure helper tests — _parse_dt
# ---------------------------------------------------------------------------


def test_parse_dt_none_returns_none() -> None:
    assert _parse_dt(None) is None


def test_parse_dt_empty_string_returns_none() -> None:
    assert _parse_dt("") is None


def test_parse_dt_valid_iso_returns_datetime() -> None:
    result = _parse_dt("2024-01-01T00:00:00")
    assert isinstance(result, datetime)
    assert result.year == 2024


def test_parse_dt_invalid_string_returns_none() -> None:
    assert _parse_dt("not-a-date") is None


# ---------------------------------------------------------------------------
# Pure helper tests — _calc_elapsed
# ---------------------------------------------------------------------------


def test_calc_elapsed_no_completed_at_returns_none() -> None:
    created = datetime(2024, 1, 1, tzinfo=UTC)
    assert _calc_elapsed(created, None) is None


def test_calc_elapsed_returns_correct_seconds() -> None:
    created = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    completed = datetime(2024, 1, 1, 0, 0, 45, tzinfo=UTC)
    assert _calc_elapsed(created, completed) == 45


def test_calc_elapsed_one_hour() -> None:
    created = datetime(2024, 1, 1, tzinfo=UTC)
    completed = datetime(2024, 1, 1, 1, tzinfo=UTC)
    assert _calc_elapsed(created, completed) == 3600


# ---------------------------------------------------------------------------
# Pure helper tests — _format_execution
# ---------------------------------------------------------------------------


def test_format_execution_keys_present() -> None:
    e = _make_execution()
    result = _format_execution(e)
    for key in (
        "execution_id",
        "agentlet_id",
        "status",
        "created_at",
        "completed_at",
        "logs_s3_uri",
        "prompt",
    ):
        assert key in result, f"Missing key: {key}"


def test_format_execution_elapsed_present_when_completed_at_set() -> None:
    e = _make_execution()  # completed_at is set to 1 hour after created_at
    result = _format_execution(e)
    assert "elapsed_seconds" in result
    assert result["elapsed_seconds"] == 3600


def test_format_execution_elapsed_absent_when_no_completed_at() -> None:
    e = _make_execution()
    e.completed_at = None
    result = _format_execution(e)
    assert "elapsed_seconds" not in result


def test_format_execution_values() -> None:
    e = _make_execution(status=ExecStatus.completed, logs_s3_uri="s3://bucket/key")
    result = _format_execution(e)
    assert result["agentlet_id"] == "my-agentlet"
    assert result["status"] == ExecStatus.completed.value
    assert result["logs_s3_uri"] == "s3://bucket/key"
    assert result["prompt"] == "test prompt"


# ---------------------------------------------------------------------------
# Route tests — GET /api/executions (list_executions)
# ---------------------------------------------------------------------------


def test_list_executions_happy_path(app: FastAPI, mock_claims: MagicMock) -> None:
    executions = [_make_execution(), _make_execution()]
    mock_db = AsyncMock()

    from auth import oidc_auth
    from db import get_db

    app.dependency_overrides[oidc_auth] = lambda: mock_claims
    app.dependency_overrides[get_db] = lambda: mock_db

    with (
        patch(
            "routers.management.resolve_org_id",
            new_callable=AsyncMock,
            return_value=ORG_ID,
        ),
        patch("routers.management.ExecutionRepo") as mock_repo_cls,
    ):
        mock_repo = MagicMock()
        mock_repo.list_by_org = AsyncMock(return_value=executions)
        mock_repo_cls.return_value = mock_repo

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/api/executions")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "executions" in body
    assert body["count"] == 2
    assert len(body["executions"]) == 2
    assert "next_token" not in body


def test_list_executions_invalid_status_returns_400(app: FastAPI, mock_claims: MagicMock) -> None:
    mock_db = AsyncMock()

    from auth import oidc_auth
    from db import get_db

    app.dependency_overrides[oidc_auth] = lambda: mock_claims
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app, raise_server_exceptions=True)
    response = client.get("/api/executions?status=invalid")

    app.dependency_overrides.clear()

    assert response.status_code == 400


def test_list_executions_pagination_next_token(app: FastAPI, mock_claims: MagicMock) -> None:
    # Return limit+1 items to trigger pagination (default limit=50)
    limit = 50
    executions = [_make_execution() for _ in range(limit + 1)]
    mock_db = AsyncMock()

    from auth import oidc_auth
    from db import get_db

    app.dependency_overrides[oidc_auth] = lambda: mock_claims
    app.dependency_overrides[get_db] = lambda: mock_db

    with (
        patch(
            "routers.management.resolve_org_id",
            new_callable=AsyncMock,
            return_value=ORG_ID,
        ),
        patch("routers.management.ExecutionRepo") as mock_repo_cls,
    ):
        mock_repo = MagicMock()
        mock_repo.list_by_org = AsyncMock(return_value=executions)
        mock_repo_cls.return_value = mock_repo

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/api/executions")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == limit
    assert "next_token" in body
    assert body["next_token"]  # non-empty


# ---------------------------------------------------------------------------
# Route tests — GET /api/executions/{execution_id} (get_execution_status)
# ---------------------------------------------------------------------------


def test_get_execution_status_found(app: FastAPI, mock_claims: MagicMock) -> None:
    execution = _make_execution()
    exec_id = str(execution.id)
    mock_db = AsyncMock()

    from auth import oidc_auth
    from db import get_db

    app.dependency_overrides[oidc_auth] = lambda: mock_claims
    app.dependency_overrides[get_db] = lambda: mock_db

    with (
        patch(
            "routers.management.resolve_org_id",
            new_callable=AsyncMock,
            return_value=ORG_ID,
        ),
        patch("routers.management.ExecutionRepo") as mock_repo_cls,
    ):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=execution)
        mock_repo_cls.return_value = mock_repo

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get(f"/api/executions/{exec_id}")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["execution_id"] == exec_id
    assert body["status"] == ExecStatus.completed.value
    assert body["agentlet_id"] == "my-agentlet"
    assert "created_at" in body


def test_get_execution_status_not_found_returns_404(app: FastAPI, mock_claims: MagicMock) -> None:
    mock_db = AsyncMock()

    from auth import oidc_auth
    from db import get_db

    app.dependency_overrides[oidc_auth] = lambda: mock_claims
    app.dependency_overrides[get_db] = lambda: mock_db

    with (
        patch(
            "routers.management.resolve_org_id",
            new_callable=AsyncMock,
            return_value=ORG_ID,
        ),
        patch("routers.management.ExecutionRepo") as mock_repo_cls,
    ):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get(f"/api/executions/{uuid4()}")

    app.dependency_overrides.clear()

    assert response.status_code == 404


def test_get_execution_status_wrong_org_returns_403(app: FastAPI, mock_claims: MagicMock) -> None:
    # execution belongs to a different org
    execution = _make_execution(org_id=OTHER_ORG_ID)
    exec_id = str(execution.id)
    mock_db = AsyncMock()

    from auth import oidc_auth
    from db import get_db

    app.dependency_overrides[oidc_auth] = lambda: mock_claims
    app.dependency_overrides[get_db] = lambda: mock_db

    with (
        patch(
            "routers.management.resolve_org_id",
            new_callable=AsyncMock,
            return_value=ORG_ID,
        ),
        patch("routers.management.ExecutionRepo") as mock_repo_cls,
    ):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=execution)
        mock_repo_cls.return_value = mock_repo

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get(f"/api/executions/{exec_id}")

    app.dependency_overrides.clear()

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Route tests — GET /api/executions/{execution_id}/logs (get_execution_logs)
# ---------------------------------------------------------------------------


def test_get_execution_logs_text_format(app: FastAPI, mock_claims: MagicMock) -> None:
    logs_uri = "s3://test-logs/executions/abc/logs.txt"
    execution = _make_execution(logs_s3_uri=logs_uri)
    exec_id = str(execution.id)
    mock_db = AsyncMock()

    from auth import oidc_auth
    from db import get_db

    app.dependency_overrides[oidc_auth] = lambda: mock_claims
    app.dependency_overrides[get_db] = lambda: mock_db

    with (
        patch(
            "routers.management.resolve_org_id",
            new_callable=AsyncMock,
            return_value=ORG_ID,
        ),
        patch("routers.management.ExecutionRepo") as mock_repo_cls,
        patch("routers.management.get_s3") as mock_get_s3,
    ):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=execution)
        mock_repo_cls.return_value = mock_repo

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=b"log line 1\nlog line 2"))
        }
        mock_get_s3.return_value = mock_s3

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get(f"/api/executions/{exec_id}/logs")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "log line 1" in response.text
    assert "log line 2" in response.text
    assert response.headers["content-type"].startswith("text/plain")


def test_get_execution_logs_running_no_uri_returns_json(
    app: FastAPI, mock_claims: MagicMock
) -> None:
    execution = _make_execution(status=ExecStatus.running, logs_s3_uri=None)
    exec_id = str(execution.id)
    mock_db = AsyncMock()

    from auth import oidc_auth
    from db import get_db

    app.dependency_overrides[oidc_auth] = lambda: mock_claims
    app.dependency_overrides[get_db] = lambda: mock_db

    with (
        patch(
            "routers.management.resolve_org_id",
            new_callable=AsyncMock,
            return_value=ORG_ID,
        ),
        patch("routers.management.ExecutionRepo") as mock_repo_cls,
    ):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=execution)
        mock_repo_cls.return_value = mock_repo

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get(f"/api/executions/{exec_id}/logs")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["logs_available"] is False


def test_get_execution_logs_terminal_no_uri_returns_410(
    app: FastAPI, mock_claims: MagicMock
) -> None:
    # completed execution with no logs URI → 410 Gone
    execution = _make_execution(status=ExecStatus.completed, logs_s3_uri=None)
    exec_id = str(execution.id)
    mock_db = AsyncMock()

    from auth import oidc_auth
    from db import get_db

    app.dependency_overrides[oidc_auth] = lambda: mock_claims
    app.dependency_overrides[get_db] = lambda: mock_db

    with (
        patch(
            "routers.management.resolve_org_id",
            new_callable=AsyncMock,
            return_value=ORG_ID,
        ),
        patch("routers.management.ExecutionRepo") as mock_repo_cls,
    ):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=execution)
        mock_repo_cls.return_value = mock_repo

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get(f"/api/executions/{exec_id}/logs")

    app.dependency_overrides.clear()

    assert response.status_code == 410


# ---------------------------------------------------------------------------
# Route tests — GET /api/public/executions/{execution_id}
# ---------------------------------------------------------------------------


def test_get_public_execution_status_found(app: FastAPI) -> None:
    execution = _make_execution()
    exec_id = str(execution.id)
    mock_db = AsyncMock()

    # apikey_auth returns TokenClaims with org_id set — no resolve_org_id call needed
    mock_apikey_claims = MagicMock(spec=TokenClaims)
    mock_apikey_claims.org_id = ORG_ID
    mock_apikey_claims.user_id = "api-user-1"

    from auth import apikey_auth
    from db import get_db

    app.dependency_overrides[apikey_auth] = lambda: mock_apikey_claims
    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("routers.management.ExecutionRepo") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=execution)
        mock_repo_cls.return_value = mock_repo

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get(f"/api/public/executions/{exec_id}")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["execution_id"] == exec_id
    assert body["agentlet_id"] == "my-agentlet"
    assert body["status"] == ExecStatus.completed.value
