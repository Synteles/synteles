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

from synteles_db.models import ModelPreset


class ModelPresetRepo:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, user_id: UUID, name: str) -> ModelPreset | None:
        result = await self._db.execute(
            select(ModelPreset).where(ModelPreset.user_id == user_id, ModelPreset.name == name)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: UUID) -> list[ModelPreset]:
        result = await self._db.execute(
            select(ModelPreset)
            .where(ModelPreset.user_id == user_id)
            .order_by(ModelPreset.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, *, user_id: UUID, name: str, config: dict[str, Any]) -> ModelPreset:
        preset = ModelPreset(id=uuid.uuid4(), user_id=user_id, name=name, config=config)
        self._db.add(preset)
        await self._db.flush()
        return preset

    async def update(self, preset: ModelPreset, *, config: dict[str, Any]) -> None:
        preset.config = config
        preset.updated_at = datetime.now(UTC)
        await self._db.flush()

    async def delete(self, preset: ModelPreset) -> None:
        await self._db.delete(preset)
        await self._db.flush()
