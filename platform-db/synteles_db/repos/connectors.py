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
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from synteles_db.models import Connector


class ConnectorRepo:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, org_id: UUID, name: str) -> Connector | None:
        result = await self._db.execute(
            select(Connector).where(Connector.org_id == org_id, Connector.name == name)
        )
        return result.scalar_one_or_none()

    async def list_by_org(self, org_id: UUID) -> list[Connector]:
        result = await self._db.execute(
            select(Connector)
            .where(Connector.org_id == org_id)
            .order_by(Connector.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        org_id: UUID,
        user_id: UUID,
        name: str,
        config: dict[str, Any],
    ) -> Connector:
        connector = Connector(
            id=uuid.uuid4(), org_id=org_id, user_id=user_id, name=name, config=config
        )
        self._db.add(connector)
        await self._db.flush()
        return connector

    async def update(self, connector: Connector, *, config: dict[str, Any]) -> None:
        connector.config = config
        connector.updated_at = datetime.now(UTC)
        await self._db.flush()

    async def delete(self, connector: Connector) -> None:
        await self._db.delete(connector)
        await self._db.flush()
