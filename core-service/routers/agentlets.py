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

"""Agentlet CRUD router."""

from __future__ import annotations

import re
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.models import ExecutionType
from synteles_db.repos.agentlets import AgentletRepo

from auth import TokenClaims, trusted_claims_with_org
from db import get_db

router = APIRouter()

_AGENTLET_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")


def _validate_agentlet_id(agentlet_id: str) -> bool:
    return bool(agentlet_id and _AGENTLET_ID_RE.match(agentlet_id))


class CreateAgentletRequest(BaseModel):
    id: str
    YAML: str = ""
    description: str = ""
    execution_backend: ExecutionType = ExecutionType.standard


class UpdateAgentletRequest(BaseModel):
    YAML: str | None = None
    description: str | None = None
    execution_backend: ExecutionType | None = None


@router.get("/api/agentlets")
async def list_agentlets(
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id_param: Annotated[str | None, Query(alias="org_id")] = None,
) -> list[dict[str, Any]]:
    org_id = claims.org_id
    if org_id_param and org_id_param != org_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this organization")
    agentlets = await AgentletRepo(db).list_by_org(UUID(org_id))
    return [
        {
            "id": a.name,
            "description": a.description,
            "created_at": a.created_at.isoformat(),
            "updated_at": a.updated_at.isoformat(),
        }
        for a in agentlets
    ]


@router.post("/api/agentlets", status_code=201)
async def create_agentlet(
    body: CreateAgentletRequest,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    if not _validate_agentlet_id(body.id):
        raise HTTPException(
            status_code=400,
            detail=(
                "id is required and must start with a letter or digit; may contain letters, "
                "digits, underscores, and hyphens (max 128 characters)"
            ),
        )
    org_id = claims.org_id
    try:
        agentlet = await AgentletRepo(db).create(
            org_id=UUID(org_id),
            user_id=UUID(claims.user_id),
            name=body.id,
            description=body.description,
            yaml_definition=body.YAML,
            execution_backend=body.execution_backend,
        )
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409, detail="Agentlet with given ID already exists in this organization"
        ) from None
    return {
        "id": body.id,
        "yaml": agentlet.yaml_definition,
        "description": agentlet.description,
        "execution_backend": agentlet.execution_backend,
        "created_at": agentlet.created_at.isoformat(),
        "updated_at": agentlet.updated_at.isoformat(),
    }


@router.get("/api/agentlets/{agentlet_id}")
async def get_agentlet(
    agentlet_id: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id_param: Annotated[str | None, Query(alias="org_id")] = None,
) -> dict[str, Any]:
    org_id = claims.org_id
    if org_id_param and org_id_param != org_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this organization")
    agentlet = await AgentletRepo(db).get_by_org_and_name(UUID(org_id), agentlet_id)
    if not agentlet:
        raise HTTPException(status_code=404, detail="Agentlet not found")
    return {
        "description": agentlet.description,
        "YAML": agentlet.yaml_definition,
        "execution_backend": agentlet.execution_backend,
        "created_at": agentlet.created_at.isoformat(),
        "updated_at": agentlet.updated_at.isoformat(),
    }


@router.patch("/api/agentlets/{agentlet_id}")
async def update_agentlet(
    agentlet_id: str,
    body: UpdateAgentletRequest,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    org_id = claims.org_id
    agentlet = await AgentletRepo(db).get_by_org_and_name(UUID(org_id), agentlet_id)
    if not agentlet:
        raise HTTPException(status_code=404, detail="Agentlet not found")
    await AgentletRepo(db).update(
        agentlet,
        description=body.description,
        yaml_definition=body.YAML,
        execution_backend=body.execution_backend,
    )
    await db.commit()
    return {"message": "Agentlet updated"}


@router.delete("/api/agentlets/{agentlet_id}", status_code=204)
async def delete_agentlet(
    agentlet_id: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    org_id = claims.org_id
    agentlet = await AgentletRepo(db).get_by_org_and_name(UUID(org_id), agentlet_id)
    if not agentlet:
        raise HTTPException(status_code=404, detail="Agentlet not found")
    try:
        await AgentletRepo(db).delete(agentlet)
        await db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409, detail="Cannot delete agentlet with existing executions"
        ) from None
    return Response(status_code=204)
