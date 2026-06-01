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

"""Unit tests for the agentlets router."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from auth import TokenClaims, trusted_claims
from db import get_db
from routers.agentlets import _validate_agentlet_id

_USER_ID = str(uuid4())
_ORG_ID = str(uuid4())
_NOW = datetime(2025, 6, 1, tzinfo=UTC)


def _make_agentlet(name: str = "my-agentlet") -> MagicMock:
    a = MagicMock()
    a.name = name
    a.description = "test description"
    a.yaml_definition = "version: 1"
    a.created_at = _NOW
    a.updated_at = _NOW
    return a


@pytest.fixture
def mock_db() -> AsyncMock:
    db = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def client(mock_db: AsyncMock):
    from main import app

    def fake_auth() -> TokenClaims:
        return TokenClaims(user_id=_USER_ID, org_id=_ORG_ID)

    def fake_db():
        yield mock_db

    app.dependency_overrides[trusted_claims] = fake_auth
    app.dependency_overrides[get_db] = fake_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ─── _validate_agentlet_id ─────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["abc", "A1", "hello_world", "my-agentlet-1", "a" * 128])
def test_validate_agentlet_id_valid(value: str) -> None:
    assert _validate_agentlet_id(value) is True


@pytest.mark.parametrize("value", ["", "_bad", "-bad", "a" * 129, "has space", "has.dot"])
def test_validate_agentlet_id_invalid(value: str) -> None:
    assert _validate_agentlet_id(value) is False


# ─── GET /api/agentlets ────────────────────────────────────────────────────


def test_list_agentlets_returns_empty_list(client: TestClient) -> None:
    with patch("routers.agentlets.AgentletRepo") as mock_repo:
        mock_repo.return_value.list_by_org = AsyncMock(return_value=[])
        response = client.get("/api/agentlets")
    assert response.status_code == 200
    assert response.json() == []


def test_list_agentlets_returns_items(client: TestClient) -> None:
    with patch("routers.agentlets.AgentletRepo") as mock_repo:
        mock_repo.return_value.list_by_org = AsyncMock(
            return_value=[_make_agentlet("a1"), _make_agentlet("a2")]
        )
        response = client.get("/api/agentlets")
    assert response.status_code == 200
    assert len(response.json()) == 2


# ─── POST /api/agentlets ───────────────────────────────────────────────────


def test_create_agentlet_invalid_id_returns_400(client: TestClient) -> None:
    response = client.post("/api/agentlets", json={"id": "_invalid", "YAML": ""})
    assert response.status_code == 400


def test_create_agentlet_success_returns_201(client: TestClient) -> None:
    with patch("routers.agentlets.AgentletRepo") as mock_repo:
        mock_repo.return_value.create = AsyncMock(return_value=_make_agentlet("new-agent"))
        response = client.post(
            "/api/agentlets", json={"id": "new-agent", "YAML": "version: 1", "description": "hi"}
        )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "new-agent"
    assert body["yaml"] == "version: 1"


def test_create_agentlet_duplicate_returns_409(client: TestClient) -> None:
    with patch("routers.agentlets.AgentletRepo") as mock_repo:
        mock_repo.return_value.create = AsyncMock(
            side_effect=IntegrityError("duplicate", None, Exception("unique"))
        )
        response = client.post("/api/agentlets", json={"id": "dup-agent", "YAML": ""})
    assert response.status_code == 409


# ─── GET /api/agentlets/{id} ───────────────────────────────────────────────


def test_get_agentlet_not_found_returns_404(client: TestClient) -> None:
    with patch("routers.agentlets.AgentletRepo") as mock_repo:
        mock_repo.return_value.get_by_org_and_name = AsyncMock(return_value=None)
        response = client.get("/api/agentlets/nonexistent")
    assert response.status_code == 404


def test_get_agentlet_success_returns_200(client: TestClient) -> None:
    with patch("routers.agentlets.AgentletRepo") as mock_repo:
        mock_repo.return_value.get_by_org_and_name = AsyncMock(
            return_value=_make_agentlet("my-agentlet")
        )
        response = client.get("/api/agentlets/my-agentlet")
    assert response.status_code == 200
    assert response.json()["YAML"] == "version: 1"


# ─── PATCH /api/agentlets/{id} ─────────────────────────────────────────────


def test_update_agentlet_not_found_returns_404(client: TestClient) -> None:
    with patch("routers.agentlets.AgentletRepo") as mock_repo:
        mock_repo.return_value.get_by_org_and_name = AsyncMock(return_value=None)
        response = client.patch("/api/agentlets/nonexistent", json={"YAML": "version: 2"})
    assert response.status_code == 404


def test_update_agentlet_success_returns_200(client: TestClient) -> None:
    with patch("routers.agentlets.AgentletRepo") as mock_repo:
        mock_repo.return_value.get_by_org_and_name = AsyncMock(
            return_value=_make_agentlet("my-agentlet")
        )
        mock_repo.return_value.update = AsyncMock()
        response = client.patch("/api/agentlets/my-agentlet", json={"YAML": "version: 2"})
    assert response.status_code == 200


# ─── DELETE /api/agentlets/{id} ────────────────────────────────────────────


def test_delete_agentlet_not_found_returns_404(client: TestClient) -> None:
    with patch("routers.agentlets.AgentletRepo") as mock_repo:
        mock_repo.return_value.get_by_org_and_name = AsyncMock(return_value=None)
        response = client.delete("/api/agentlets/nonexistent")
    assert response.status_code == 404


def test_delete_agentlet_success_returns_204(client: TestClient) -> None:
    with patch("routers.agentlets.AgentletRepo") as mock_repo:
        mock_repo.return_value.get_by_org_and_name = AsyncMock(return_value=_make_agentlet())
        mock_repo.return_value.delete = AsyncMock()
        response = client.delete("/api/agentlets/my-agentlet")
    assert response.status_code == 204
