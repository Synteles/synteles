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

"""Model preset router — user-scoped model configuration presets."""

from __future__ import annotations

import re
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.repos.model_presets import ModelPresetRepo

from auth import TokenClaims, oidc_auth
from db import get_db

router = APIRouter()

_PRESET_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")
_KNOWN_PROVIDERS = {
    "bedrock",
    "anthropic",
    "openai",
    "azure_ai",
    "azure",
    "vertex_ai",
    "gemini",
    "sagemaker",
}
_MAX_DESCRIPTION_LENGTH = 500
_MAX_MODEL_ID_LENGTH = 512
_MAX_SECRET_NAME_LENGTH = 128


def _format_preset(p: Any) -> dict[str, Any]:
    cfg = p.config or {}
    return {
        "name": p.name,
        "description": cfg.get("description", ""),
        "provider": cfg.get("provider", ""),
        "model_id": cfg.get("model_id", ""),
        "secret_name": cfg.get("secret_name") or None,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


class CreateModelPresetRequest(BaseModel):
    name: str
    description: str = ""
    provider: str
    model_id: str
    secret_name: str | None = None


class UpdateModelPresetRequest(BaseModel):
    description: str | None = None
    model_id: str | None = None
    secret_name: str | None = None


@router.post("/api/models", status_code=201)
async def create_model_preset(
    body: CreateModelPresetRequest,
    claims: Annotated[TokenClaims, Depends(oidc_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    name = body.name.strip()
    description = body.description.strip()
    provider = body.provider.strip()
    model_id = body.model_id.strip()
    secret_name = (body.secret_name or "").strip() or None

    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not _PRESET_NAME_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail="name must start with a letter or digit; may contain letters, digits, underscores, and hyphens (max 128 characters)",
        )
    if len(description) > _MAX_DESCRIPTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"description must not exceed {_MAX_DESCRIPTION_LENGTH} characters",
        )
    if not provider:
        raise HTTPException(status_code=400, detail="provider is required")
    if provider not in _KNOWN_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"provider must be one of: {', '.join(sorted(_KNOWN_PROVIDERS))}",
        )
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id is required")
    if len(model_id) > _MAX_MODEL_ID_LENGTH:
        raise HTTPException(
            status_code=400, detail=f"model_id must not exceed {_MAX_MODEL_ID_LENGTH} characters"
        )
    if secret_name and len(secret_name) > _MAX_SECRET_NAME_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"secret_name must not exceed {_MAX_SECRET_NAME_LENGTH} characters",
        )

    config: dict[str, Any] = {
        "description": description,
        "provider": provider,
        "model_id": model_id,
    }
    if secret_name:
        config["secret_name"] = secret_name

    try:
        preset = await ModelPresetRepo(db).create(
            user_id=UUID(claims.user_id),
            name=name,
            config=config,
        )
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409, detail=f"Model preset '{name}' already exists"
        ) from None

    return _format_preset(preset)


@router.get("/api/models")
async def list_model_presets(
    claims: Annotated[TokenClaims, Depends(oidc_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    presets = await ModelPresetRepo(db).list_by_user(UUID(claims.user_id))
    return [_format_preset(p) for p in presets]


@router.get("/api/models/{preset_name}")
async def get_model_preset(
    preset_name: str,
    claims: Annotated[TokenClaims, Depends(oidc_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    preset = await ModelPresetRepo(db).get(UUID(claims.user_id), preset_name)
    if not preset:
        raise HTTPException(status_code=404, detail="Model preset not found")
    return _format_preset(preset)


@router.patch("/api/models/{preset_name}")
async def update_model_preset(
    preset_name: str,
    body: UpdateModelPresetRequest,
    claims: Annotated[TokenClaims, Depends(oidc_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    if body.description is None and body.model_id is None and body.secret_name is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of 'description', 'model_id', or 'secret_name' must be provided",
        )
    if body.description is not None and len(body.description) > _MAX_DESCRIPTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"description must not exceed {_MAX_DESCRIPTION_LENGTH} characters",
        )
    if body.model_id is not None:
        if not body.model_id.strip():
            raise HTTPException(status_code=400, detail="model_id must be a non-empty string")
        if len(body.model_id) > _MAX_MODEL_ID_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"model_id must not exceed {_MAX_MODEL_ID_LENGTH} characters",
            )
    if body.secret_name and len(body.secret_name) > _MAX_SECRET_NAME_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"secret_name must not exceed {_MAX_SECRET_NAME_LENGTH} characters",
        )

    repo = ModelPresetRepo(db)
    preset = await repo.get(UUID(claims.user_id), preset_name)
    if not preset:
        raise HTTPException(status_code=404, detail="Model preset not found")

    cfg = dict(preset.config or {})
    if body.description is not None:
        cfg["description"] = body.description
    if body.model_id is not None:
        cfg["model_id"] = body.model_id.strip()
    if body.secret_name is not None:
        if body.secret_name == "":  # nosec B105
            cfg.pop("secret_name", None)
        else:
            cfg["secret_name"] = body.secret_name

    await repo.update(preset, config=cfg)
    await db.commit()
    return {"message": "Model preset updated"}


@router.delete("/api/models/{preset_name}", status_code=204)
async def delete_model_preset(
    preset_name: str,
    claims: Annotated[TokenClaims, Depends(oidc_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    repo = ModelPresetRepo(db)
    preset = await repo.get(UUID(claims.user_id), preset_name)
    if not preset:
        raise HTTPException(status_code=404, detail="Model preset not found")
    await repo.delete(preset)
    await db.commit()
    return Response(status_code=204)
