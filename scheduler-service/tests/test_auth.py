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

"""Unit tests for auth.py."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import jwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from auth import (
    TokenClaims,
    _claims_from_payload,
    apikey_auth,
    auth_router,
    oidc_auth,
    resolve_org_id,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_jwt(payload: dict) -> str:  # type: ignore[type-arg]
    """Encode a JWT with HS256 — no signature verification path used in tests."""
    return jwt.encode(payload, "secret", algorithm="HS256")


# ---------------------------------------------------------------------------
# _claims_from_payload
# ---------------------------------------------------------------------------


def test_claims_from_payload_basic() -> None:
    payload = {"sub": "user-1", "org_id": "org-1"}
    claims = _claims_from_payload(payload)
    assert claims.user_id == "user-1"
    assert claims.org_id == "org-1"


def test_claims_from_payload_no_org_id() -> None:
    payload = {"sub": "user-1"}
    claims = _claims_from_payload(payload)
    assert claims.user_id == "user-1"
    assert claims.org_id is None


def test_claims_from_payload_org_id_from_custom_metadata() -> None:
    meta = json.dumps({"org_id": "org-from-meta"})
    payload = {"sub": "user-1", "custom:metadata": meta}
    claims = _claims_from_payload(payload)
    assert claims.org_id == "org-from-meta"


def test_claims_from_payload_malformed_metadata() -> None:
    payload = {"sub": "user-1", "custom:metadata": "not-json"}
    claims = _claims_from_payload(payload)
    assert claims.org_id is None


def test_claims_from_payload_missing_sub_raises_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _claims_from_payload({})
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# oidc_auth
# ---------------------------------------------------------------------------


async def test_oidc_auth_no_bearer_raises_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await oidc_auth("not-a-bearer-token")
    assert exc_info.value.status_code == 401


async def test_oidc_auth_no_jwks_client_raises_401() -> None:
    token = _make_jwt({"sub": "user-1", "org_id": "org-1"})
    with patch("auth._JWKS_CLIENT", None), patch("auth.os.environ.get", return_value=""):
        with pytest.raises(HTTPException) as exc_info:
            await oidc_auth(f"Bearer {token}")
    assert exc_info.value.status_code == 401


async def test_oidc_auth_missing_sub_raises_401() -> None:
    token = _make_jwt({"some": "payload"})
    with patch("auth._JWKS_CLIENT", None):
        with pytest.raises(HTTPException) as exc_info:
            await oidc_auth(f"Bearer {token}")
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# apikey_auth
# ---------------------------------------------------------------------------


async def test_apikey_auth_no_bearer_raises_401() -> None:
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await apikey_auth(db, "Token abc")
    assert exc_info.value.status_code == 401


async def test_apikey_auth_valid_key_returns_claims() -> None:
    db = AsyncMock()
    mock_key = MagicMock()
    mock_key.id = UUID("00000000-0000-0000-0000-000000000001")
    mock_key.user_id = UUID("00000000-0000-0000-0000-000000000002")
    mock_key.org_id = UUID("00000000-0000-0000-0000-000000000003")

    mock_repo = MagicMock()
    mock_repo.find_active_by_hash = AsyncMock(return_value=mock_key)
    mock_repo.update_last_used = AsyncMock()

    with patch("auth.ApiKeyRepo", return_value=mock_repo):
        claims = await apikey_auth(db, "Bearer my-api-key")

    assert claims.user_id == "00000000-0000-0000-0000-000000000002"
    assert claims.org_id == "00000000-0000-0000-0000-000000000003"


async def test_apikey_auth_key_not_found_raises_401() -> None:
    db = AsyncMock()
    mock_repo = MagicMock()
    mock_repo.find_active_by_hash = AsyncMock(return_value=None)

    with patch("auth.ApiKeyRepo", return_value=mock_repo):
        with pytest.raises(HTTPException) as exc_info:
            await apikey_auth(db, "Bearer bad-key")
    assert exc_info.value.status_code == 401


async def test_apikey_auth_key_missing_org_raises_401() -> None:
    db = AsyncMock()
    mock_key = MagicMock()
    mock_key.org_id = None

    mock_repo = MagicMock()
    mock_repo.find_active_by_hash = AsyncMock(return_value=mock_key)

    with patch("auth.ApiKeyRepo", return_value=mock_repo):
        with pytest.raises(HTTPException) as exc_info:
            await apikey_auth(db, "Bearer some-key")
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# resolve_org_id
# ---------------------------------------------------------------------------


async def test_resolve_org_id_from_claims() -> None:
    claims = TokenClaims(user_id="user-1", org_id="org-from-claims")
    db = AsyncMock()
    result = await resolve_org_id(claims, db)
    assert result == "org-from-claims"


async def test_resolve_org_id_from_db() -> None:
    claims = TokenClaims(user_id="00000000-0000-0000-0000-000000000001", org_id=None)
    db = AsyncMock()
    mock_repo = MagicMock()
    mock_repo.get_first_org_id = AsyncMock(
        return_value=UUID("00000000-0000-0000-0000-000000000099")
    )

    with patch("auth.UserRepo", return_value=mock_repo):
        result = await resolve_org_id(claims, db)
    assert result == "00000000-0000-0000-0000-000000000099"


async def test_resolve_org_id_not_found_raises_401() -> None:
    claims = TokenClaims(user_id="00000000-0000-0000-0000-000000000001", org_id=None)
    db = AsyncMock()
    mock_repo = MagicMock()
    mock_repo.get_first_org_id = AsyncMock(return_value=None)

    with patch("auth.UserRepo", return_value=mock_repo):
        with pytest.raises(HTTPException) as exc_info:
            await resolve_org_id(claims, db)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# verify endpoint
# ---------------------------------------------------------------------------


def test_verify_endpoint_returns_ok_with_headers() -> None:
    app = FastAPI()
    app.include_router(auth_router)

    mock_claims = TokenClaims(user_id="user-abc", org_id="org-xyz")

    app.dependency_overrides[oidc_auth] = lambda: mock_claims

    client = TestClient(app)
    response = client.get("/auth/verify", headers={"Authorization": "Bearer token"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.headers["x-user-id"] == "user-abc"
    assert response.headers["x-org-id"] == "org-xyz"
