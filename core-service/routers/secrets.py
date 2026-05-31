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

"""Secrets router — user-scoped secrets stored encrypted in PostgreSQL."""

from __future__ import annotations

import re
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.crypto import decrypt, encrypt
from synteles_db.repos.secrets import SecretRepo

from auth import TokenClaims, trusted_claims
from db import get_db

router = APIRouter()

_SECRET_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")
_MAX_DESCRIPTION_LENGTH = 1000
_RESERVED_SECRET_NAMES: frozenset[str] = frozenset({"default"})


def _validate_name(name: str) -> None:
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not _SECRET_NAME_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail="name must start with alphanumeric and contain only letters, digits, dashes, or underscores (max 128 chars)",
        )
    if name in _RESERVED_SECRET_NAMES:
        raise HTTPException(
            status_code=400, detail=f"'{name}' is a reserved secret name and cannot be used"
        )


class CreateSecretRequest(BaseModel):
    name: str
    description: str = ""
    value: dict[str, str]


class UpdateSecretRequest(BaseModel):
    description: str | None = None
    value: dict[str, str] | None = None


@router.post("/api/secrets", status_code=201)
async def create_secret(
    body: CreateSecretRequest,
    claims: Annotated[TokenClaims, Depends(trusted_claims)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    name = body.name.strip()
    description = body.description.strip()
    _validate_name(name)
    if len(description) > _MAX_DESCRIPTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"description must not exceed {_MAX_DESCRIPTION_LENGTH} characters",
        )
    if not body.value:
        raise HTTPException(status_code=400, detail="value must be a non-empty JSON object")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in body.value.items()):
        raise HTTPException(status_code=400, detail="value keys and values must be strings")

    nonce, ciphertext = encrypt(body.value)
    try:
        secret = await SecretRepo(db).create(
            user_id=UUID(claims.user_id),
            name=name,
            description=description,
            encrypted_value=ciphertext,
            nonce=nonce,
            key_count=len(body.value),
        )
        await db.commit()
    except IntegrityError:
        raise HTTPException(status_code=409, detail=f"Secret '{name}' already exists") from None

    return {
        "name": name,
        "description": description,
        "key_count": len(body.value),
        "created_at": secret.created_at.isoformat(),
    }


@router.get("/api/secrets")
async def list_secrets(
    claims: Annotated[TokenClaims, Depends(trusted_claims)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    secrets = await SecretRepo(db).list_by_user(UUID(claims.user_id))
    return [
        {
            "name": s.name,
            "description": s.description or "",
            "key_count": s.key_count,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in secrets
    ]


@router.get("/api/secrets/{secret_name}")
async def get_secret(
    secret_name: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims)],
    db: Annotated[AsyncSession, Depends(get_db)],
    reveal_value: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    secret = await SecretRepo(db).get(UUID(claims.user_id), secret_name)
    if not secret:
        raise HTTPException(status_code=404, detail="Secret not found")

    value = decrypt(secret.nonce, secret.encrypted_value)
    result: dict[str, Any] = {
        "name": secret.name,
        "description": secret.description or "",
        "key_names": list(value.keys()),
        "created_at": secret.created_at.isoformat(),
        "updated_at": secret.updated_at.isoformat(),
    }
    if reveal_value:
        result["value"] = value
    return result


@router.patch("/api/secrets/{secret_name}")
async def update_secret(
    secret_name: str,
    body: UpdateSecretRequest,
    claims: Annotated[TokenClaims, Depends(trusted_claims)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    if body.description is None and body.value is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of 'description' or 'value' must be provided",
        )
    if body.description is not None and len(body.description) > _MAX_DESCRIPTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"description must not exceed {_MAX_DESCRIPTION_LENGTH} characters",
        )
    if body.value is not None:
        if not body.value:
            raise HTTPException(status_code=400, detail="value must be a non-empty JSON object")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in body.value.items()):
            raise HTTPException(status_code=400, detail="value keys and values must be strings")

    secret = await SecretRepo(db).get(UUID(claims.user_id), secret_name)
    if not secret:
        raise HTTPException(status_code=404, detail="Secret not found")

    nonce, ciphertext = (None, None)
    if body.value is not None:
        nonce, ciphertext = encrypt(body.value)

    await SecretRepo(db).update(
        secret,
        description=body.description,
        encrypted_value=ciphertext,
        nonce=nonce,
        key_count=len(body.value) if body.value is not None else None,
    )
    await db.commit()

    return {
        "name": secret_name,
        "description": body.description
        if body.description is not None
        else (secret.description or ""),
        "key_count": secret.key_count,
        "updated_at": secret.updated_at.isoformat(),
    }


@router.delete("/api/secrets/{secret_name}", status_code=204)
async def delete_secret(
    secret_name: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    secret = await SecretRepo(db).get(UUID(claims.user_id), secret_name)
    if not secret:
        raise HTTPException(status_code=404, detail="Secret not found")
    await SecretRepo(db).delete(secret)
    await db.commit()
    return Response(status_code=204)
