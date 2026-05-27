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

"""Database and storage client factories for scheduler-service."""

from __future__ import annotations

import os
from types import TracebackType
from typing import Any

import boto3
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from synteles_db.session import get_db as get_db

_s3_client: Any = None

# Lazily-initialised async session factory.  Used as an async context manager:
#   async with AsyncSessionLocal() as db: ...
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    # Intentional second connection pool: synteles_db.session._get_session_factory()
    # is private and vends FastAPI request-scoped sessions via get_db().  The monitor
    # runs as a long-lived background task (not a FastAPI request), so it needs its
    # own pool with independent lifecycle management.
    global _async_session_factory
    if _async_session_factory is None:
        url = os.environ.get("DATABASE_URL", "")
        if not url:
            raise RuntimeError("DATABASE_URL env var is required")
        engine = create_async_engine(url, pool_pre_ping=True)
        _async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _async_session_factory


class AsyncSessionLocal:
    """Async context manager that vends an ``AsyncSession`` from the shared pool.

    Usage::

        async with AsyncSessionLocal() as db:
            ...
    """

    async def __aenter__(self) -> AsyncSession:
        self._session = _get_async_session_factory()()
        return await self._session.__aenter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self._session.__aexit__(exc_type, exc_val, exc_tb)


def get_s3() -> Any:
    """Return a cached S3 client (supports S3_ENDPOINT_URL for MinIO / local dev)."""
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
