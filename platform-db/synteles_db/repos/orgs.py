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

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from synteles_db.models import Organization


class OrgRepo:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, org_id: UUID) -> Organization | None:
        result = await self._db.execute(select(Organization).where(Organization.id == org_id))
        return result.scalar_one_or_none()

    async def create(self, org_id: UUID, name: str) -> Organization:
        org = Organization(id=org_id, name=name)
        self._db.add(org)
        await self._db.flush()
        return org
