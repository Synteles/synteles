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

"""MCP preset (Connectors) router — org-scoped."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.repos.connectors import ConnectorRepo

from auth import TokenClaims, trusted_claims_with_org
from db import get_db

router = APIRouter()

_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")


def _validate_name(name: str) -> str | None:
    if not name:
        return "name is required"
    if not _NAME_RE.match(name):
        return (
            "name must start with a letter or digit; may contain letters, digits, "
            "underscores, and hyphens (max 128 characters)"
        )
    return None


def _validate_mcp_config(mcp_config: str) -> str | None:
    if not mcp_config:
        return "mcp_config is required"
    try:
        parsed = json.loads(mcp_config)
    except json.JSONDecodeError as exc:
        return f"mcp_config is not valid JSON: {exc}"
    if "mcpServers" not in parsed:
        return "mcp_config must contain a top-level 'mcpServers' key"
    return None


def _format_connector(c: Any) -> dict[str, Any]:
    cfg = c.config or {}
    return {
        "name": c.name,
        "description": cfg.get("description", ""),
        "mcp_config": cfg.get("mcp_config", ""),
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


class CreateMcpPresetRequest(BaseModel):
    name: str
    description: str = ""
    mcp_config: str


class UpdateMcpPresetRequest(BaseModel):
    description: str | None = None
    mcp_config: str | None = None


@router.post("/api/connectors", status_code=201)
async def create_preset(
    body: CreateMcpPresetRequest,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    org_id = claims.org_id

    if err := _validate_name(body.name):
        raise HTTPException(status_code=400, detail=err)
    if err := _validate_mcp_config(body.mcp_config):
        raise HTTPException(status_code=400, detail=err)
    if len(body.description) > 500:
        raise HTTPException(status_code=400, detail="description must be 500 chars or fewer")

    config: dict[str, Any] = {"description": body.description, "mcp_config": body.mcp_config}
    try:
        connector = await ConnectorRepo(db).create(
            org_id=UUID(org_id),
            user_id=UUID(claims.user_id),
            name=body.name,
            config=config,
        )
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409, detail=f"Preset '{body.name}' already exists"
        ) from None

    return _format_connector(connector)


@router.get("/api/connectors")
async def list_presets(
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    org_id = claims.org_id
    connectors = await ConnectorRepo(db).list_by_org(UUID(org_id))
    return {"presets": [_format_connector(c) for c in connectors]}


@router.get("/api/connectors/{name}")
async def get_preset(
    name: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    org_id = claims.org_id
    connector = await ConnectorRepo(db).get(UUID(org_id), name)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")
    return _format_connector(connector)


@router.patch("/api/connectors/{name}")
async def update_preset(
    name: str,
    body: UpdateMcpPresetRequest,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    org_id = claims.org_id
    connector = await ConnectorRepo(db).get(UUID(org_id), name)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")

    if body.description is not None and len(body.description) > 500:
        raise HTTPException(status_code=400, detail="description must be 500 chars or fewer")
    if body.mcp_config is not None:
        if err := _validate_mcp_config(body.mcp_config):
            raise HTTPException(status_code=400, detail=err)

    cfg = dict(connector.config or {})
    if body.description is not None:
        cfg["description"] = body.description
    if body.mcp_config is not None:
        cfg["mcp_config"] = body.mcp_config

    await ConnectorRepo(db).update(connector, config=cfg)
    await db.commit()
    return _format_connector(connector)


@router.delete("/api/connectors/{name}")
async def delete_preset(
    name: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    org_id = claims.org_id
    connector = await ConnectorRepo(db).get(UUID(org_id), name)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")
    await ConnectorRepo(db).delete(connector)
    await db.commit()
    return {"message": f"Preset '{name}' deleted"}
