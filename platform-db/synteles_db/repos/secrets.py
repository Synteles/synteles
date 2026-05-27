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

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from synteles_db.models import Secret


class SecretRepo:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, user_id: UUID, name: str) -> Secret | None:
        result = await self._db.execute(
            select(Secret).where(Secret.user_id == user_id, Secret.name == name)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: UUID) -> list[Secret]:
        result = await self._db.execute(
            select(Secret).where(Secret.user_id == user_id).order_by(Secret.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_user_names(self, user_id: UUID, names: list[str]) -> list[Secret]:
        if not names:
            return []
        result = await self._db.execute(
            select(Secret).where(Secret.user_id == user_id, Secret.name.in_(names))
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        user_id: UUID,
        name: str,
        description: str,
        encrypted_value: bytes,
        nonce: bytes,
        key_count: int,
    ) -> Secret:
        secret = Secret(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            description=description or None,
            encrypted_value=encrypted_value,
            nonce=nonce,
            key_count=key_count,
        )
        self._db.add(secret)
        try:
            await self._db.flush()
        except IntegrityError:
            await self._db.rollback()
            raise
        return secret

    async def update(
        self,
        secret: Secret,
        *,
        description: str | None = None,
        encrypted_value: bytes | None = None,
        nonce: bytes | None = None,
        key_count: int | None = None,
    ) -> None:
        if description is not None:
            secret.description = description or None
        if encrypted_value is not None:
            secret.encrypted_value = encrypted_value
        if nonce is not None:
            secret.nonce = nonce
        if key_count is not None:
            secret.key_count = key_count
        secret.updated_at = datetime.now(UTC)
        await self._db.flush()

    async def delete(self, secret: Secret) -> None:
        await self._db.delete(secret)
        await self._db.flush()
