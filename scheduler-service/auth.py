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

"""Authentication dependencies and forward-auth endpoint for scheduler-service.

Intentional copy of core-service/auth.py for service independence.
Both services share identical auth logic but are deployed and scaled separately.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from jwt import PyJWKClient
from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.repos.apikeys import ApiKeyRepo
from synteles_db.repos.users import UserRepo

from db import get_db

auth_router = APIRouter()


@dataclass
class TokenClaims:
    user_id: str
    org_id: str | None


_JWKS_CLIENT: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient | None:
    global _JWKS_CLIENT
    issuer_url = os.environ.get("OIDC_ISSUER_URL", "")
    jwks_url = os.environ.get("OIDC_JWKS_URL", "")
    if not issuer_url and not jwks_url:
        return None
    if _JWKS_CLIENT is None:
        effective_url = jwks_url or f"{issuer_url}/protocol/openid-connect/certs"
        _JWKS_CLIENT = PyJWKClient(effective_url, cache_keys=True)
    return _JWKS_CLIENT


def _claims_from_payload(payload: dict[str, Any]) -> TokenClaims:
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing sub claim")
    org_id: str | None = payload.get("org_id") or None
    if not org_id:
        meta = payload.get("custom:metadata")
        if meta:
            try:
                org_id = json.loads(meta).get("org_id") or None
            except Exception:  # nosec B110 — malformed metadata is silently ignored
                pass
    return TokenClaims(user_id=str(user_id), org_id=org_id)


async def oidc_auth(authorization: Annotated[str | None, Header()] = None) -> TokenClaims:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    client = _get_jwks_client()
    if client is None:
        raise HTTPException(status_code=401, detail="OIDC not configured")
    try:
        from config import OIDC_AUDIENCE

        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=OIDC_AUDIENCE or None,
            options={"verify_aud": bool(OIDC_AUDIENCE)},
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token") from None
    return _claims_from_payload(payload)


async def apikey_auth(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> TokenClaims:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    api_key = authorization.removeprefix("Bearer ").strip()
    # SHA256 is safe here: tokens are issued exclusively via create_api_key
    # using token_urlsafe(32) (256-bit entropy).  # nosec B324
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()  # lgtm[py/weak-sensitive-data-hashing]
    try:
        repo = ApiKeyRepo(db)
        key = await repo.find_active_by_hash(key_hash)
        if not key or key.org_id is None:
            raise HTTPException(status_code=401, detail="Unauthorized")
        await repo.update_last_used(key.id)
        return TokenClaims(user_id=str(key.user_id), org_id=str(key.org_id))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized") from None


async def resolve_org_id(claims: TokenClaims, db: AsyncSession) -> str:
    if claims.org_id:
        return claims.org_id
    org_id = await UserRepo(db).get_first_org_id(UUID(claims.user_id))
    if org_id:
        return str(org_id)
    raise HTTPException(status_code=401, detail="Unable to determine organization")


@auth_router.get("/auth/verify")
async def verify(
    claims: Annotated[TokenClaims, Depends(oidc_auth)],
    response: Response,
) -> dict[str, Any]:
    response.headers["X-User-Id"] = claims.user_id
    response.headers["X-Org-Id"] = claims.org_id or ""
    return {"ok": True}
