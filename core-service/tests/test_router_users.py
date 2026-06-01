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

"""Tests for lazy user provisioning in GET /api/users/me."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from auth import TokenClaims, trusted_claims
from db import get_db

_USER_ID = str(uuid4())
_ORG_ID = str(uuid4())


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def client(mock_db):
    from main import app

    def fake_auth():
        return TokenClaims(user_id=_USER_ID, org_id=_ORG_ID)

    def fake_db():
        yield mock_db

    app.dependency_overrides[trusted_claims] = fake_auth
    app.dependency_overrides[get_db] = fake_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ─── GET /api/users/me ─────────────────────────────────────────────────────


def test_get_me_provisions_user_when_not_in_db(client):
    with (
        patch("routers.users.UserRepo") as mock_user_repo,
        patch("routers.users.OrgRepo"),
        patch("routers.users._provision_user", new_callable=AsyncMock) as mock_provision,
    ):
        mock_user_repo.return_value.get = AsyncMock(return_value=None)
        mock_provision.return_value = (uuid4(), "Personal Workspace")

        res = client.get("/api/users/me")

    assert res.status_code == 200
    mock_provision.assert_called_once()


def test_get_me_returns_profile_for_existing_user(client):
    mock_user = MagicMock()
    mock_user.preferences = {"home_org_id": _ORG_ID}

    mock_org = MagicMock()
    mock_org.name = "Acme Corp"

    with (
        patch("routers.users.UserRepo") as mock_user_repo,
        patch("routers.users.OrgRepo") as mock_org_repo,
    ):
        mock_user_repo.return_value.get = AsyncMock(return_value=mock_user)
        mock_user_repo.return_value.get_first_org_id = AsyncMock(return_value=None)
        mock_org_repo.return_value.get = AsyncMock(return_value=mock_org)

        res = client.get("/api/users/me")

    assert res.status_code == 200
    body = res.json()
    assert body["sub"] == _USER_ID
