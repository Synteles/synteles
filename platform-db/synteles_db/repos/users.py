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

from synteles_db.models import User, UserOrg


class UserRepo:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, user_id: UUID) -> User | None:
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_first_org_id(self, user_id: UUID) -> UUID | None:
        result = await self._db.execute(
            select(UserOrg.org_id).where(UserOrg.user_id == user_id).limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_org(self, org_id: UUID) -> list[User]:
        result = await self._db.execute(
            select(User).join(UserOrg, User.id == UserOrg.user_id).where(UserOrg.org_id == org_id)
        )
        return list(result.scalars().all())

    async def is_org_member(self, user_id: UUID, org_id: UUID) -> bool:
        result = await self._db.execute(
            select(UserOrg).where(UserOrg.user_id == user_id, UserOrg.org_id == org_id)
        )
        return result.scalar_one_or_none() is not None

    async def create(self, user_id: UUID) -> User:
        user = User(id=user_id)
        self._db.add(user)
        await self._db.flush()
        return user
