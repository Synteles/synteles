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

"""Database and storage client factories for core-service."""

from __future__ import annotations

import os
from typing import Any

import boto3
from synteles_db.session import get_db as get_db

_s3_client: Any = None
_s3_public_client: Any = None


def get_s3() -> Any:
    """Return a cached S3 client for internal API calls (uses S3_ENDPOINT_URL)."""
    global _s3_client
    if _s3_client is None:
        kwargs: dict[str, Any] = {
            "region_name": os.environ.get("AWS_REGION", "eu-central-1"),
        }
        endpoint_url = os.environ.get("S3_ENDPOINT_URL")
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
            kwargs["aws_access_key_id"] = os.environ["S3_ACCESS_KEY"]
            kwargs["aws_secret_access_key"] = os.environ["S3_SECRET_KEY"]
        _s3_client = boto3.client("s3", **kwargs)
    return _s3_client


def get_s3_public() -> Any:
    """Return a cached S3 client for presigned URL generation.

    Uses S3_PUBLIC_ENDPOINT_URL when set (e.g. http://localhost:9000 for dev),
    so generated presigned URLs are reachable by external clients. Falls back
    to S3_ENDPOINT_URL (same as get_s3) when not set.
    """
    global _s3_public_client
    if _s3_public_client is None:
        kwargs: dict[str, Any] = {
            "region_name": os.environ.get("AWS_REGION", "eu-central-1"),
        }
        endpoint_url = os.environ.get("S3_PUBLIC_ENDPOINT_URL") or os.environ.get("S3_ENDPOINT_URL")
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
            kwargs["aws_access_key_id"] = os.environ["S3_ACCESS_KEY"]
            kwargs["aws_secret_access_key"] = os.environ["S3_SECRET_KEY"]
        _s3_public_client = boto3.client("s3", **kwargs)
    return _s3_public_client
