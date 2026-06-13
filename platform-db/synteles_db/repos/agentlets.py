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

from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from synteles_db.models import Agentlet, ExecutionBackend


class AgentletRepo:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_by_org(self, org_id: UUID) -> list[Agentlet]:
        result = await self._db.execute(
            select(Agentlet).where(Agentlet.org_id == org_id).order_by(Agentlet.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_org_and_name(self, org_id: UUID, name: str) -> Agentlet | None:
        result = await self._db.execute(
            select(Agentlet).where(Agentlet.org_id == org_id, Agentlet.name == name)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, agentlet_id: UUID) -> Agentlet | None:
        result = await self._db.execute(select(Agentlet).where(Agentlet.id == agentlet_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        org_id: UUID,
        user_id: UUID,
        name: str,
        description: str,
        yaml_definition: str,
        execution_backend: ExecutionBackend = ExecutionBackend.standard,
    ) -> Agentlet:
        agentlet = Agentlet(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            name=name,
            description=description or None,
            yaml_definition=yaml_definition,
            execution_backend=execution_backend,
        )
        self._db.add(agentlet)
        await self._db.flush()
        return agentlet

    async def update(
        self,
        agentlet: Agentlet,
        *,
        description: str | None = None,
        yaml_definition: str | None = None,
        execution_backend: ExecutionBackend | None = None,
    ) -> None:
        if description is not None:
            agentlet.description = description or None
        if yaml_definition is not None:
            agentlet.yaml_definition = yaml_definition
        if execution_backend is not None:
            agentlet.execution_backend = execution_backend
        await self._db.flush()

    async def delete(self, agentlet: Agentlet) -> None:
        await self._db.delete(agentlet)
        await self._db.flush()
