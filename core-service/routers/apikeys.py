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

"""API key management router."""

from __future__ import annotations

import hashlib
import re
import secrets
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.repos.apikeys import ApiKeyRepo

from auth import TokenClaims, oidc_auth, resolve_org_id
from db import get_db

router = APIRouter()

_KEY_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")


class CreateApiKeyRequest(BaseModel):
    key_name: str


@router.post("/api/users/apikeys")
async def create_api_key(
    body: CreateApiKeyRequest,
    claims: Annotated[TokenClaims, Depends(oidc_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    org_id = await resolve_org_id(claims, db)

    if not body.key_name:
        raise HTTPException(status_code=400, detail="key_name is required")
    if not _KEY_NAME_RE.match(body.key_name):
        raise HTTPException(
            status_code=400,
            detail=(
                "key_name must start with a letter or digit; may contain letters, digits, "
                "underscores, and hyphens (max 128 characters)"
            ),
        )

    api_key = secrets.token_urlsafe(32)
    # SHA256 is safe here: token_urlsafe(32) produces 256 bits of entropy,
    # making brute-force against the stored hash infeasible.  # nosec B324
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()  # codeql[py/weak-sensitive-data-hashing]

    key = await ApiKeyRepo(db).create(
        org_id=UUID(org_id),
        user_id=UUID(claims.user_id),
        name=body.key_name,
        key_hash=key_hash,
    )
    await db.commit()

    return {
        "key_id": str(key.id),
        "key": api_key,
        "key_name": body.key_name,
        "created_at": key.created_at.isoformat(),
    }


@router.get("/api/users/apikeys")
async def list_api_keys(
    claims: Annotated[TokenClaims, Depends(oidc_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    org_id = await resolve_org_id(claims, db)
    keys = await ApiKeyRepo(db).list_by_user(UUID(org_id), UUID(claims.user_id))
    return [
        {
            "key_id": str(k.id),
            "key_name": k.name,
            "created_at": k.created_at.isoformat(),
            "last_used": k.last_used.isoformat() if k.last_used else None,
        }
        for k in keys
    ]


@router.delete("/api/users/apikeys/{apikey_id}", status_code=204)
async def delete_api_key(
    apikey_id: str,
    claims: Annotated[TokenClaims, Depends(oidc_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    try:
        key_uuid = UUID(apikey_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="API key not found") from None
    org_id = await resolve_org_id(claims, db)
    key = await ApiKeyRepo(db).get_by_id_and_user(key_uuid, UUID(claims.user_id), UUID(org_id))
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    await ApiKeyRepo(db).revoke(key)
    await db.commit()
    return Response(status_code=204)
