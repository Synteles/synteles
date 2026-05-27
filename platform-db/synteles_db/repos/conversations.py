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

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from synteles_db.models import Conversation


class ConversationRepo:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_by_user(self, org_id: UUID, user_id: UUID) -> list[Conversation]:
        result = await self._db.execute(
            select(Conversation)
            .where(Conversation.org_id == org_id, Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, org_id: UUID, user_id: UUID, conv_id: UUID) -> Conversation | None:
        result = await self._db.execute(
            select(Conversation).where(
                Conversation.id == conv_id,
                Conversation.org_id == org_id,
                Conversation.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        org_id: UUID,
        user_id: UUID,
        title: str,
        message_count: int,
        expires_at: datetime,
    ) -> Conversation:
        conv = Conversation(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            title=title or None,
            message_count=message_count,
            expires_at=expires_at,
        )
        self._db.add(conv)
        await self._db.flush()
        return conv

    async def update(
        self,
        conv: Conversation,
        *,
        title: str | None = None,
        message_count: int | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        if title is not None:
            conv.title = title or None
        if message_count is not None:
            conv.message_count = message_count
        if expires_at is not None:
            conv.expires_at = expires_at
        conv.updated_at = datetime.now(UTC)
        await self._db.flush()

    async def delete(self, conv: Conversation) -> None:
        await self._db.delete(conv)
        await self._db.flush()

    async def delete_expired(self) -> int:
        result = await self._db.execute(
            delete(Conversation).where(
                Conversation.expires_at.isnot(None),
                Conversation.expires_at < datetime.now(UTC),
            )
        )
        return result.rowcount  # type: ignore[attr-defined, no-any-return]
