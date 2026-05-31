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

"""Unit tests for auth module helpers."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from auth import _claims_from_payload, oidc_auth, trusted_claims
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_jwks_client(monkeypatch):
    import auth as auth_module

    monkeypatch.setattr(auth_module, "_JWKS_CLIENT", None)


# ─── _claims_from_payload ──────────────────────────────────────────────────


def test_claims_direct_org_id():
    claims = _claims_from_payload({"sub": "user-123", "org_id": "org-abc"})
    assert claims.user_id == "user-123"
    assert claims.org_id == "org-abc"


def test_claims_org_from_custom_metadata():
    meta = json.dumps({"org_id": "org-from-meta"})
    claims = _claims_from_payload({"sub": "user-456", "custom:metadata": meta})
    assert claims.org_id == "org-from-meta"


def test_claims_no_org_id():
    claims = _claims_from_payload({"sub": "user-789"})
    assert claims.user_id == "user-789"
    assert claims.org_id is None


def test_claims_missing_sub_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        _claims_from_payload({})
    assert exc_info.value.status_code == 401


def test_claims_metadata_invalid_json_silently_ignored():
    claims = _claims_from_payload({"sub": "user-000", "custom:metadata": "not-json"})
    assert claims.org_id is None


def test_claims_direct_org_id_takes_precedence_over_metadata():
    meta = json.dumps({"org_id": "org-meta"})
    claims = _claims_from_payload({"sub": "u", "org_id": "org-direct", "custom:metadata": meta})
    assert claims.org_id == "org-direct"


def test_claims_empty_org_id_falls_back_to_metadata():
    meta = json.dumps({"org_id": "org-meta"})
    claims = _claims_from_payload({"sub": "u", "org_id": "", "custom:metadata": meta})
    assert claims.org_id == "org-meta"


# ─── oidc_auth ─────────────────────────────────────────────────────────────


async def test_oidc_auth_missing_bearer_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        await oidc_auth("NotBearer token123")
    assert exc_info.value.status_code == 401


async def test_oidc_auth_no_issuer_raises_401(monkeypatch):
    monkeypatch.setenv("OIDC_ISSUER_URL", "")
    token = jwt.encode({"sub": "user-oidc", "org_id": "org-oidc"}, "a" * 32, algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        await oidc_auth(f"Bearer {token}")
    assert exc_info.value.status_code == 401


# ─── trusted_claims ────────────────────────────────────────────────────────


async def test_trusted_claims_returns_token_claims():
    result = await trusted_claims(x_user_id="u-123", x_org_id="o-abc")
    assert result.user_id == "u-123"
    assert result.org_id == "o-abc"


async def test_trusted_claims_missing_user_id_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        await trusted_claims(x_user_id=None, x_org_id="o-abc")
    assert exc_info.value.status_code == 401


async def test_trusted_claims_empty_org_id_returns_none():
    result = await trusted_claims(x_user_id="u-123", x_org_id="")
    assert result.org_id is None


# ─── /auth/verify ──────────────────────────────────────────────────────────


def test_verify_no_headers_returns_401():
    res = client.get("/auth/verify")
    assert res.status_code == 401


def test_verify_invalid_authorization_returns_401():
    res = client.get("/auth/verify", headers={"Authorization": "notbearer xyz"})
    assert res.status_code == 401


def test_verify_jwt_returns_identity_headers():
    import jwt as pyjwt

    token = pyjwt.encode({"sub": "u-123", "org_id": "o-abc"}, "secret", algorithm="HS256")

    mock_signing_key = MagicMock()
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

    with (
        patch("auth._get_jwks_client", return_value=mock_client),
        patch("auth.jwt.decode", return_value={"sub": "u-123", "org_id": "o-abc"}),
        patch("auth.resolve_org_id", new=AsyncMock(return_value="o-abc")),
    ):
        res = client.get("/auth/verify", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    assert res.headers["x-user-id"] == "u-123"
    assert res.headers["x-org-id"] == "o-abc"


def test_verify_jwt_unprovisioned_user_still_returns_200():
    """verify passes through when org not yet in DB (first login / not provisioned)."""
    import jwt as pyjwt

    token = pyjwt.encode({"sub": "u-new", "org_id": ""}, "secret", algorithm="HS256")

    mock_signing_key = MagicMock()
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

    from fastapi import HTTPException as _HTTPException

    with (
        patch("auth._get_jwks_client", return_value=mock_client),
        patch("auth.jwt.decode", return_value={"sub": "u-new"}),
        patch("auth.resolve_org_id", new=AsyncMock(side_effect=_HTTPException(status_code=401))),
    ):
        res = client.get("/auth/verify", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    assert res.headers["x-user-id"] == "u-new"
    assert res.headers["x-org-id"] == ""


def test_verify_api_key_returns_identity_headers():
    user_id, org_id = uuid4(), uuid4()

    with patch("auth.ApiKeyRepo") as mock_repo:
        mock_key = MagicMock()
        mock_key.user_id = user_id
        mock_key.org_id = org_id
        mock_repo.return_value.find_active_by_hash = AsyncMock(return_value=mock_key)
        mock_repo.return_value.update_last_used = AsyncMock()

        res = client.get("/auth/verify", headers={"X-API-Key": "sk-someapikey"})

    assert res.status_code == 200
    assert res.headers["x-user-id"] == str(user_id)
    assert res.headers["x-org-id"] == str(org_id)


def test_verify_api_key_takes_priority_over_bearer():
    """X-API-Key is used when both headers are present."""
    user_id, org_id = uuid4(), uuid4()

    with patch("auth.ApiKeyRepo") as mock_repo:
        mock_key = MagicMock()
        mock_key.user_id = user_id
        mock_key.org_id = org_id
        mock_repo.return_value.find_active_by_hash = AsyncMock(return_value=mock_key)
        mock_repo.return_value.update_last_used = AsyncMock()

        res = client.get(
            "/auth/verify",
            headers={"X-API-Key": "sk-someapikey", "Authorization": "Bearer somejwt"},
        )

    assert res.status_code == 200
    assert res.headers["x-user-id"] == str(user_id)
