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
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from synteles_db.models import ApiKey


class ApiKeyRepo:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_active_by_hash(self, key_hash: str) -> ApiKey | None:
        result = await self._db.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, org_id: UUID, user_id: UUID) -> list[ApiKey]:
        result = await self._db.execute(
            select(ApiKey)
            .where(ApiKey.org_id == org_id, ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id_and_user(self, key_id: UUID, user_id: UUID, org_id: UUID) -> ApiKey | None:
        result = await self._db.execute(
            select(ApiKey).where(
                ApiKey.id == key_id,
                ApiKey.user_id == user_id,
                ApiKey.org_id == org_id,
                ApiKey.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, *, org_id: UUID, user_id: UUID, name: str, key_hash: str) -> ApiKey:
        key = ApiKey(id=uuid.uuid4(), org_id=org_id, user_id=user_id, name=name, key_hash=key_hash)
        self._db.add(key)
        await self._db.flush()
        return key

    async def revoke(self, key: ApiKey) -> None:
        key.revoked_at = datetime.now(UTC)
        await self._db.flush()

    async def update_last_used(self, key_id: UUID) -> None:
        await self._db.execute(
            update(ApiKey).where(ApiKey.id == key_id).values(last_used=datetime.now(UTC))
        )
