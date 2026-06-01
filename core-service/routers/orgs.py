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

"""Organisation details router."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.repos.orgs import OrgRepo
from synteles_db.repos.users import UserRepo

from auth import TokenClaims, trusted_claims_with_org
from db import get_db

router = APIRouter()


@router.get("/api/organizations/{org_id}")
async def get_organization(
    org_id: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    caller_org_id = claims.org_id
    if caller_org_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this organization")

    org = await OrgRepo(db).get(UUID(org_id))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    users = await UserRepo(db).list_by_org(UUID(org_id))
    return {
        "org_name": org.name,
        "users": [str(u.id) for u in users],
    }
