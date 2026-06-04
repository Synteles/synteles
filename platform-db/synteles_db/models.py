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

"""SQLAlchemy ORM models for the synteles schema."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

_SCHEMA = "synteles"


class Base(DeclarativeBase):
    pass


class ExecutionType(enum.StrEnum):
    standard = "standard"
    durable  = "durable"


class StandardExecStatus(enum.StrEnum):
    deploying = "deploying"
    running   = "running"
    completed = "completed"
    failed    = "failed"
    stopped   = "stopped"


class DurableExecStatus(enum.StrEnum):
    deploying          = "deploying"
    running            = "running"
    waiting_for_signal = "waiting_for_signal"
    completed          = "completed"
    failed             = "failed"
    stopped            = "stopped"


# Backward-compatible alias — scheduler-service imports ExecStatus until Phase 3.
ExecStatus = StandardExecStatus

# Declared with create_type=False — the type is created by the Alembic migration.
_execution_type_sa = SAEnum(
    ExecutionType,
    name="execution_type",
    schema=_SCHEMA,
    create_type=False,
)

_STANDARD_STATUSES = tuple(s.value for s in StandardExecStatus)
_DURABLE_STATUSES  = tuple(s.value for s in DurableExecStatus)


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = {"schema": _SCHEMA}  # noqa: RUF012

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # "metadata" is a reserved name on DeclarativeBase; use metadata_ → column "metadata".
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": _SCHEMA}  # noqa: RUF012

    id: Mapped[UUID] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class UserOrg(Base):
    __tablename__ = "users_orgs"
    __table_args__ = (
        Index(None, "org_id"),
        {"schema": _SCHEMA},
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.id"), primary_key=True)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{_SCHEMA}.organizations.id"), primary_key=True
    )


class Agentlet(Base):
    __tablename__ = "agentlets"
    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_agentlets_org_name"),
        Index(None, "user_id"),
        Index(None, "org_id"),
        {"schema": _SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    org_id: Mapped[UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.organizations.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    yaml_definition: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        Index(None, "key_hash"),
        Index(None, "user_id"),
        Index(None, "org_id"),
        {"schema": _SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    org_id: Mapped[UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.organizations.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False, server_default="'default'")
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (
        Index(None, "status", "updated_at"),
        Index(None, "agentlet_id", "created_at"),
        Index(None, "user_id", "created_at"),
        Index(None, "org_id", "created_at"),
        CheckConstraint(
            f"(execution_type = 'standard' AND status IN {_STANDARD_STATUSES})"
            f" OR (execution_type = 'durable' AND status IN {_DURABLE_STATUSES})",
            name="ck_execution_status",
        ),
        {"schema": _SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    org_id: Mapped[UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.organizations.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.id"), nullable=False)
    agentlet_id: Mapped[UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.agentlets.id"), nullable=False)
    agentlet_name: Mapped[str] = mapped_column(Text, nullable=False, server_default="''")
    execution_type: Mapped[ExecutionType] = mapped_column(
        _execution_type_sa, nullable=False, server_default=ExecutionType.standard
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    job_ref: Mapped[str | None] = mapped_column(Text)
    workflow_id: Mapped[str | None] = mapped_column(Text)
    signal_name: Mapped[str | None] = mapped_column(Text)
    timeout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prompt: Mapped[str] = mapped_column(Text, nullable=False, server_default="''")
    logs_s3_uri: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index(None, "user_id", "created_at"),
        Index(None, "org_id", "created_at"),
        {"schema": _SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    org_id: Mapped[UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.organizations.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class Secret(Base):
    __tablename__ = "secrets"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_secrets_user_name"),
        {"schema": _SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    encrypted_value: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    nonce: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    key_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class ModelPreset(Base):
    __tablename__ = "models"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_models_user_name"),
        Index(None, "user_id"),
        {"schema": _SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # config stores: {"provider": ..., "model_id": ..., "secret_name": ..., "description": ...}
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class Connector(Base):
    __tablename__ = "connectors"
    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_connectors_org_name"),
        Index(None, "org_id"),
        Index(None, "user_id"),
        Index(None, "org_id", "user_id"),
        {"schema": _SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    org_id: Mapped[UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.organizations.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(f"{_SCHEMA}.users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # config stores: {"description": ..., "mcp_config": ...}
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
