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

"""Conversation CRUD router with S3-backed blob storage."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.repos.conversations import ConversationRepo

from auth import TokenClaims, trusted_claims_with_org
from db import get_db, get_s3

router = APIRouter()
logger = logging.getLogger(__name__)

_CONVERSATION_TTL_DAYS = 90
_PRESIGNED_URL_EXPIRY_SECONDS = 300
_TITLE_MAX_LENGTH = 80


def _s3_display_key(user_id: str, conv_id: str) -> str:
    return f"conversations/{user_id}/{conv_id}/display.json"


def _s3_state_key(user_id: str, conv_id: str) -> str:
    return f"conversations/{user_id}/{conv_id}/agent_state.json"


def _expires_at() -> datetime:
    return datetime.now(UTC) + timedelta(days=_CONVERSATION_TTL_DAYS)


def _put_s3_json(s3_client: Any, bucket: str, key: str, data: Any) -> None:
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data),
        ContentType="application/json",
    )


def _delete_s3_object(s3_client: Any, bucket: str, key: str) -> None:
    try:
        s3_client.delete_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("NoSuchKey", "404"):
            raise


def _presigned_url(s3_client: Any, bucket: str, key: str) -> str:
    return str(
        s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=_PRESIGNED_URL_EXPIRY_SECONDS,
        )
    )


class CreateConversationRequest(BaseModel):
    title: str = ""
    display_messages: list[Any]
    agent_state: Any


class UpdateConversationRequest(BaseModel):
    title: str | None = None
    display_messages: list[Any] | None = None
    agent_state: Any | None = None


@router.get("/api/conversations")
async def list_conversations(
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    org_id = claims.org_id
    convs = await ConversationRepo(db).list_by_user(UUID(org_id), UUID(claims.user_id))
    return {
        "conversations": [
            {
                "conversation_id": str(c.id),
                "title": c.title or "",
                "message_count": c.message_count,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in convs
        ]
    }


@router.post("/api/conversations", status_code=201)
async def create_conversation(
    body: CreateConversationRequest,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    from config import S3_LOGS_BUCKET

    org_id = claims.org_id
    title = str(body.title)[:_TITLE_MAX_LENGTH]
    conv = await ConversationRepo(db).create(
        org_id=UUID(org_id),
        user_id=UUID(claims.user_id),
        title=title,
        message_count=len(body.display_messages),
        expires_at=_expires_at(),
    )
    await db.commit()

    s3_client = get_s3()
    _put_s3_json(
        s3_client,
        S3_LOGS_BUCKET,
        _s3_display_key(claims.user_id, str(conv.id)),
        body.display_messages,
    )
    _put_s3_json(
        s3_client, S3_LOGS_BUCKET, _s3_state_key(claims.user_id, str(conv.id)), body.agent_state
    )

    return {
        "conversation_id": str(conv.id),
        "title": title,
        "message_count": conv.message_count,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
    }


@router.get("/api/conversations/{conv_id}")
async def get_conversation(
    conv_id: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    from config import S3_LOGS_BUCKET

    org_id = claims.org_id
    conv = await ConversationRepo(db).get(UUID(org_id), UUID(claims.user_id), UUID(conv_id))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    s3_client = get_s3()
    display_url = _presigned_url(
        s3_client, S3_LOGS_BUCKET, _s3_display_key(claims.user_id, conv_id)
    )
    state_url = _presigned_url(s3_client, S3_LOGS_BUCKET, _s3_state_key(claims.user_id, conv_id))

    return {
        "conversation_id": conv_id,
        "title": conv.title or "",
        "message_count": conv.message_count,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "display_url": display_url,
        "agent_state_url": state_url,
    }


@router.patch("/api/conversations/{conv_id}")
async def update_conversation(
    conv_id: str,
    body: UpdateConversationRequest,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    from config import S3_LOGS_BUCKET

    org_id = claims.org_id
    conv = await ConversationRepo(db).get(UUID(org_id), UUID(claims.user_id), UUID(conv_id))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    s3_client = get_s3()
    message_count: int | None = None

    if body.display_messages is not None:
        message_count = len(body.display_messages)
        _put_s3_json(
            s3_client,
            S3_LOGS_BUCKET,
            _s3_display_key(claims.user_id, conv_id),
            body.display_messages,
        )

    if body.agent_state is not None:
        _put_s3_json(
            s3_client, S3_LOGS_BUCKET, _s3_state_key(claims.user_id, conv_id), body.agent_state
        )

    await ConversationRepo(db).update(
        conv,
        title=str(body.title)[:_TITLE_MAX_LENGTH] if body.title is not None else None,
        message_count=message_count,
        expires_at=_expires_at(),
    )
    await db.commit()
    return {"conversation_id": conv_id, "updated_at": conv.updated_at.isoformat()}


@router.delete("/api/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    from config import S3_LOGS_BUCKET

    org_id = claims.org_id
    conv = await ConversationRepo(db).get(UUID(org_id), UUID(claims.user_id), UUID(conv_id))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await ConversationRepo(db).delete(conv)
    await db.commit()

    s3_client = get_s3()
    _delete_s3_object(s3_client, S3_LOGS_BUCKET, _s3_display_key(claims.user_id, conv_id))
    _delete_s3_object(s3_client, S3_LOGS_BUCKET, _s3_state_key(claims.user_id, conv_id))

    return {"conversation_id": conv_id, "deleted": True}
