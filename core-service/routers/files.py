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

"""Files router — presigned upload/download URLs for agentlet file exchange."""

from __future__ import annotations

import logging
import os
import re
import uuid
from typing import Annotated, Any
from uuid import UUID

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.repos.executions import ExecutionRepo

from auth import TokenClaims, trusted_claims
from db import get_db, get_s3, get_s3_public

router = APIRouter()
logger = logging.getLogger(__name__)

_MAX_FILES = 20
_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
_PRESIGNED_URL_EXPIRY_SECONDS = 3600  # 1 hour
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class FileEntry(BaseModel):
    name: str


class CreateUploadSessionRequest(BaseModel):
    files: list[FileEntry]


@router.post("/api/files", status_code=201)
async def create_upload_session(
    body: CreateUploadSessionRequest,
    claims: Annotated[TokenClaims, Depends(trusted_claims)],
) -> dict[str, Any]:
    from config import S3_UPLOADS_BUCKET

    if not body.files:
        raise HTTPException(status_code=400, detail="'files' must not be empty")
    if len(body.files) > _MAX_FILES:
        raise HTTPException(
            status_code=400, detail=f"Too many files. Maximum {_MAX_FILES} files allowed."
        )

    for f in body.files:
        if not f.name:
            raise HTTPException(
                status_code=400, detail="Each file entry must have a non-empty 'name' field"
            )
        if "/" in f.name or "\\" in f.name or f.name.startswith("."):
            raise HTTPException(status_code=400, detail=f"Invalid file name: {f.name!r}")

    upload_id = str(uuid.uuid4())
    s3_client = get_s3_public()
    upload_urls = []

    for f in body.files:
        name = f.name
        key = f"{upload_id}/{name}"
        is_image = os.path.splitext(name)[1].lower() in _IMAGE_EXTENSIONS
        conditions: list[Any] = [["content-length-range", 1, _MAX_FILE_SIZE_BYTES]]
        if is_image:
            conditions.append(["starts-with", "$Content-Type", "image/"])
        try:
            presigned = s3_client.generate_presigned_post(
                Bucket=S3_UPLOADS_BUCKET,
                Key=key,
                Conditions=conditions,
                ExpiresIn=_PRESIGNED_URL_EXPIRY_SECONDS,
            )
            upload_urls.append(
                {
                    "name": name,
                    "s3_uri": f"s3://{S3_UPLOADS_BUCKET}/{key}",
                    "upload_url": presigned["url"],
                    "upload_fields": presigned["fields"],
                    "type": "image" if is_image else "document",
                }
            )
        except ClientError as exc:
            logger.error("Failed to generate presigned POST for %s: %s", name, exc)
            raise HTTPException(status_code=500, detail="Failed to generate upload URL") from exc

    return {"upload_id": upload_id, "files": upload_urls}


@router.get("/api/executions/{execution_id}/files")
async def get_execution_files(
    execution_id: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    from config import S3_LOGS_BUCKET

    if not _UUID_RE.match(execution_id):
        raise HTTPException(status_code=400, detail="Invalid execution_id format")

    org_id = claims.org_id
    execution = await ExecutionRepo(db).get_by_id(UUID(execution_id))
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    if str(execution.org_id) != org_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this execution")
    if str(execution.user_id) != claims.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this execution")

    s3_client = get_s3()  # internal endpoint — for API calls (list, head)
    s3_public = get_s3_public()  # public endpoint — for presigned URL generation
    input_prefix = f"executions/{execution_id}/input/"
    input_files: list[dict[str, Any]] = []

    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_LOGS_BUCKET, Prefix=input_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                file_name = key[len(input_prefix) :]
                if not file_name:
                    continue
                try:
                    presigned_url = s3_public.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": S3_LOGS_BUCKET, "Key": key},
                        ExpiresIn=_PRESIGNED_URL_EXPIRY_SECONDS,
                    )
                    input_files.append(
                        {
                            "name": file_name,
                            "size": obj.get("Size", 0),
                            "download_url": presigned_url,
                            "type": "image"
                            if os.path.splitext(file_name)[1].lower() in _IMAGE_EXTENSIONS
                            else "document",
                        }
                    )
                except ClientError as exc:
                    logger.warning("Failed to generate presigned GET for %s: %s", key, exc)
    except ClientError as exc:
        logger.error("S3 list error for input files: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to list input files") from exc

    output_key = f"executions/{execution_id}/output/output.zip"
    output_download_url = None
    try:
        s3_client.head_object(Bucket=S3_LOGS_BUCKET, Key=output_key)
        output_download_url = s3_public.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_LOGS_BUCKET, "Key": output_key},
            ExpiresIn=_PRESIGNED_URL_EXPIRY_SECONDS,
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("404", "NoSuchKey"):
            logger.warning("S3 head_object error for output.zip: %s", exc)

    return {
        "execution_id": execution_id,
        "input_files": input_files,
        "output_zip": {
            "exists": output_download_url is not None,
            "download_url": output_download_url,
        },
    }
