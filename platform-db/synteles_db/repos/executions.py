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
from sqlalchemy.ext.asyncio import AsyncSession

from synteles_db.models import (
    DurableExecStatus,
    Execution,
    ExecutionType,
    StandardExecStatus,
)

# Backward-compatible alias used by callers that still import ExecStatus.
ExecStatus = StandardExecStatus


class ExecutionRepo:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, execution_id: UUID) -> Execution | None:
        result = await self._db.execute(select(Execution).where(Execution.id == execution_id))
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Execution]:
        """Return all executions in an active state across both execution types."""
        active_statuses = [
            StandardExecStatus.deploying,
            StandardExecStatus.running,
            DurableExecStatus.deploying,
            DurableExecStatus.running,
            DurableExecStatus.waiting_for_signal,
        ]
        result = await self._db.execute(
            select(Execution).where(Execution.status.in_(active_statuses))
        )
        return list(result.scalars().all())

    async def list_by_org(
        self,
        org_id: UUID,
        *,
        agentlet_name: str | None = None,
        status: str | None = None,
        created_at_start: datetime | None = None,
        created_at_end: datetime | None = None,
        completed_at_start: datetime | None = None,
        completed_at_end: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Execution]:
        q = (
            select(Execution)
            .where(Execution.org_id == org_id)
            .order_by(Execution.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if agentlet_name:
            q = q.where(Execution.agentlet_name == agentlet_name)
        if status:
            q = q.where(Execution.status == status)
        if created_at_start:
            q = q.where(Execution.created_at >= created_at_start)
        if created_at_end:
            q = q.where(Execution.created_at <= created_at_end)
        if completed_at_start:
            q = q.where(Execution.completed_at >= completed_at_start)
        if completed_at_end:
            q = q.where(Execution.completed_at <= completed_at_end)
        result = await self._db.execute(q)
        return list(result.scalars().all())

    async def create(
        self,
        *,
        org_id: UUID,
        user_id: UUID,
        agentlet_id: UUID,
        agentlet_name: str,
        status: StandardExecStatus | DurableExecStatus,
        timeout_at: datetime,
        prompt: str,
        execution_type: ExecutionType = ExecutionType.standard,
    ) -> Execution:
        execution = Execution(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            agentlet_id=agentlet_id,
            agentlet_name=agentlet_name,
            execution_type=execution_type,
            status=status,
            timeout_at=timeout_at,
            prompt=prompt,
        )
        self._db.add(execution)
        await self._db.flush()
        return execution

    async def update_job_ref(
        self,
        execution: Execution,
        job_ref: str,
        status: StandardExecStatus | DurableExecStatus,
        *,
        workflow_id: str | None = None,
    ) -> None:
        execution.job_ref = job_ref
        execution.status = status
        execution.updated_at = datetime.now(UTC)
        if workflow_id is not None:
            execution.workflow_id = workflow_id
        await self._db.flush()

    async def update_status(
        self,
        execution: Execution,
        status: StandardExecStatus | DurableExecStatus,
        *,
        job_ref: str | None = None,
        error: str | None = None,
        logs_s3_uri: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        execution.status = status
        execution.updated_at = datetime.now(UTC)
        if job_ref is not None:
            execution.job_ref = job_ref
        if error is not None:
            execution.error = error
        if logs_s3_uri is not None:
            execution.logs_s3_uri = logs_s3_uri
        if completed_at is not None:
            execution.completed_at = completed_at
        await self._db.flush()

    async def update_workflow_id(self, execution: Execution, workflow_id: str) -> None:
        execution.workflow_id = workflow_id
        execution.updated_at = datetime.now(UTC)
        await self._db.flush()

    async def list_waiting_for_signal(self, org_id: UUID) -> list[Execution]:
        """Return durable executions currently paused awaiting a human signal."""
        result = await self._db.execute(
            select(Execution)
            .where(
                Execution.org_id == org_id,
                Execution.execution_type == ExecutionType.durable,
                Execution.status == DurableExecStatus.waiting_for_signal,
            )
            .order_by(Execution.updated_at.asc())
        )
        return list(result.scalars().all())

    async def delete_expired(self, cutoff: datetime) -> int:
        from sqlalchemy import delete

        result = await self._db.execute(delete(Execution).where(Execution.created_at < cutoff))
        return result.rowcount  # type: ignore[attr-defined, no-any-return]
