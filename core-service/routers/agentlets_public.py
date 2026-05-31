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

"""Public agentlet endpoint (API key authentication)."""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

import yaml
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.repos.agentlets import AgentletRepo

from auth import TokenClaims, trusted_claims
from db import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


def _inject_attrs(agentlet_yaml: str, attrs: dict[str, Any]) -> str:
    try:
        data: Any = yaml.safe_load(agentlet_yaml)
        if not isinstance(data, dict):
            return agentlet_yaml
        if "attributes" not in data:
            data["attributes"] = {}
        data["attributes"].update(attrs)
        result: str = yaml.dump(data, default_flow_style=False, sort_keys=False)
        return result
    except yaml.YAMLError as exc:
        logger.error("Failed to parse/inject attributes into YAML: %s", exc)
        return agentlet_yaml


@router.get("/api/public/agentlets/{agentlet_id}", response_model=None)
async def get_public_agentlet(
    agentlet_id: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims)],
    db: Annotated[AsyncSession, Depends(get_db)],
    accept: Annotated[str, Header()] = "",
    format: Annotated[str | None, Query()] = None,
) -> dict[str, Any] | PlainTextResponse:
    if not agentlet_id or not agentlet_id.strip():
        raise HTTPException(status_code=404, detail="Agentlet not found")

    agentlet = await AgentletRepo(db).get_by_org_and_name(UUID(claims.org_id), agentlet_id)
    if not agentlet or str(agentlet.user_id) != claims.user_id:
        raise HTTPException(status_code=404, detail="Agentlet not found")

    agentlet_yaml = agentlet.yaml_definition
    if not agentlet_yaml:
        logger.error("Agentlet %s in org %s has no YAML definition", agentlet_id, claims.org_id)
        raise HTTPException(status_code=404, detail="Agentlet YAML definition not found")

    agentlet_yaml_with_attrs = _inject_attrs(
        agentlet_yaml,
        {"synteles.org.id": claims.org_id},
    )

    want_yaml = "yaml" in accept.lower() or format == "yaml"
    if want_yaml:
        return PlainTextResponse(
            content=agentlet_yaml_with_attrs,
            media_type="application/x-yaml",
        )

    return {
        "description": agentlet.description,
        "YAML": agentlet_yaml_with_attrs,
    }
