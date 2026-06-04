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

"""Tests for monitor._upload_logs_to_s3, monitor._finalize, monitor._poll, monitor_loop."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from synteles_db.models import ExecStatus, StandardExecStatus

from backends.base import ExecutionStatus

# ── _upload_logs_to_s3 ──────────────────────────────────────────────────────


def test_upload_logs_success() -> None:
    mock_s3 = MagicMock()
    with (
        patch("monitor.get_s3", return_value=mock_s3),
        patch("monitor.S3_LOGS_BUCKET", "test-bucket"),
    ):
        from monitor import _upload_logs_to_s3

        uri = _upload_logs_to_s3("exec-id-123", "hello logs")

    assert uri == "s3://test-bucket/executions/exec-id-123/logs.txt"
    mock_s3.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="executions/exec-id-123/logs.txt",
        Body=b"hello logs",
        ContentType="text/plain",
    )


def test_upload_logs_failure_returns_none() -> None:
    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = Exception("S3 error")
    with (
        patch("monitor.get_s3", return_value=mock_s3),
        patch("monitor.S3_LOGS_BUCKET", "test-bucket"),
    ):
        from monitor import _upload_logs_to_s3

        uri = _upload_logs_to_s3("exec-id-123", "hello logs")

    assert uri is None


# ── _finalize ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_finalize_with_logs() -> None:
    """_finalize uploads logs, updates DB, commits, stops container."""
    execution = MagicMock()
    execution.id = "exec-uuid-1"
    execution.job_ref = "container-id-1"

    backend = MagicMock()
    backend.logs = AsyncMock(return_value="some logs")
    backend.stop = AsyncMock()

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    db = MagicMock()
    db.commit = AsyncMock()

    with (
        patch("monitor.ExecutionRepo", return_value=mock_repo),
        patch("monitor._upload_logs_to_s3", return_value="s3://bucket/key"),
    ):
        from monitor import _finalize

        await _finalize(execution, ExecStatus.completed, backend, db)

    backend.logs.assert_awaited_once_with("container-id-1")
    mock_repo.update_status.assert_awaited_once()
    db.commit.assert_awaited_once()
    backend.stop.assert_awaited_once_with("container-id-1")


@pytest.mark.asyncio
async def test_finalize_empty_logs_skips_upload() -> None:
    """When backend.logs() returns '', no S3 upload and logs_s3_uri is None."""
    execution = MagicMock()
    execution.id = "exec-uuid-2"
    execution.job_ref = "container-id-2"

    backend = MagicMock()
    backend.logs = AsyncMock(return_value="")
    backend.stop = AsyncMock()

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    db = MagicMock()
    db.commit = AsyncMock()

    with (
        patch("monitor.ExecutionRepo", return_value=mock_repo),
        patch("monitor._upload_logs_to_s3") as mock_upload,
    ):
        from monitor import _finalize

        await _finalize(execution, ExecStatus.failed, backend, db)

    mock_upload.assert_not_called()
    call_kwargs = mock_repo.update_status.call_args
    assert call_kwargs.kwargs.get("logs_s3_uri") is None


@pytest.mark.asyncio
async def test_finalize_no_job_ref_skips_backend() -> None:
    """When job_ref is None, skip logs/stop entirely."""
    execution = MagicMock()
    execution.id = "exec-uuid-3"
    execution.job_ref = None

    backend = MagicMock()
    backend.logs = AsyncMock()
    backend.stop = AsyncMock()

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    db = MagicMock()
    db.commit = AsyncMock()

    with (
        patch("monitor.ExecutionRepo", return_value=mock_repo),
        patch("monitor._upload_logs_to_s3"),
    ):
        from monitor import _finalize

        await _finalize(execution, ExecStatus.stopped, backend, db)

    backend.logs.assert_not_called()
    backend.stop.assert_not_called()
    db.commit.assert_awaited_once()


# ── _poll ────────────────────────────────────────────────────────────────────
#
# _poll() now uses two separate sessions per execution:
#   1. A short-lived listing session: ExecutionRepo(db).list_active()
#   2. A fresh per-execution session: ExecutionRepo(db).get_by_id(execution.id)
#      followed by _finalize(fresh, db_status, backend, db)
#
# Strategy: patch _finalize as AsyncMock and assert it was called with the
# correct db_status. Use side_effect on AsyncSessionLocal to yield a listing
# db for the first call and a finalizing db for subsequent calls.


def _make_session_factory(list_db: MagicMock, finalize_db: MagicMock) -> MagicMock:
    """Return a mock for AsyncSessionLocal that yields list_db first, then finalize_db."""
    call_count = 0

    def factory() -> MagicMock:
        nonlocal call_count
        call_count += 1
        return list_db if call_count == 1 else finalize_db

    mock = MagicMock(side_effect=factory)
    return mock


def _make_async_ctx(db: MagicMock) -> MagicMock:
    """Wrap a mock db in an async context manager."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=db)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.mark.asyncio
async def test_poll_finalises_completed() -> None:
    """A COMPLETED container triggers _finalize with ExecStatus.completed."""
    from uuid import uuid4

    exec_id = uuid4()
    execution = MagicMock()
    execution.id = exec_id
    execution.job_ref = "container-1"
    execution.timeout_at = None
    execution.execution_type = "standard"

    fresh_execution = MagicMock()

    backend = MagicMock()
    backend.status = AsyncMock(return_value=ExecutionStatus.COMPLETED)

    list_db = MagicMock()
    finalize_db = MagicMock()

    list_repo = MagicMock()
    list_repo.list_active = AsyncMock(return_value=[execution])

    finalize_repo = MagicMock()
    finalize_repo.get_by_id = AsyncMock(return_value=fresh_execution)

    list_ctx = _make_async_ctx(list_db)
    finalize_ctx = _make_async_ctx(finalize_db)

    call_count = 0

    def session_factory() -> MagicMock:
        nonlocal call_count
        call_count += 1
        return list_ctx if call_count == 1 else finalize_ctx

    def repo_factory(db: MagicMock) -> MagicMock:
        return list_repo if db is list_db else finalize_repo

    with (
        patch("monitor.get_backend", return_value=backend),
        patch("monitor.AsyncSessionLocal", side_effect=session_factory),
        patch("monitor.ExecutionRepo", side_effect=repo_factory),
        patch("monitor._finalize", new_callable=AsyncMock) as mock_finalize,
    ):
        from monitor import _poll

        await _poll()

    mock_finalize.assert_called_once()
    args = mock_finalize.call_args
    assert args.args[0] is fresh_execution
    assert args.args[1] == ExecStatus.completed
    assert args.args[2] is backend
    assert args.args[3] is finalize_db


@pytest.mark.asyncio
async def test_poll_finalises_failed() -> None:
    """A FAILED container triggers _finalize with ExecStatus.failed."""
    from uuid import uuid4

    exec_id = uuid4()
    execution = MagicMock()
    execution.id = exec_id
    execution.job_ref = "container-2"
    execution.timeout_at = None
    execution.execution_type = "standard"

    fresh_execution = MagicMock()

    backend = MagicMock()
    backend.status = AsyncMock(return_value=ExecutionStatus.FAILED)

    list_db = MagicMock()
    finalize_db = MagicMock()

    list_repo = MagicMock()
    list_repo.list_active = AsyncMock(return_value=[execution])

    finalize_repo = MagicMock()
    finalize_repo.get_by_id = AsyncMock(return_value=fresh_execution)

    list_ctx = _make_async_ctx(list_db)
    finalize_ctx = _make_async_ctx(finalize_db)

    call_count = 0

    def session_factory() -> MagicMock:
        nonlocal call_count
        call_count += 1
        return list_ctx if call_count == 1 else finalize_ctx

    def repo_factory(db: MagicMock) -> MagicMock:
        return list_repo if db is list_db else finalize_repo

    with (
        patch("monitor.get_backend", return_value=backend),
        patch("monitor.AsyncSessionLocal", side_effect=session_factory),
        patch("monitor.ExecutionRepo", side_effect=repo_factory),
        patch("monitor._finalize", new_callable=AsyncMock) as mock_finalize,
    ):
        from monitor import _poll

        await _poll()

    mock_finalize.assert_called_once()
    args = mock_finalize.call_args
    assert args.args[0] is fresh_execution
    assert args.args[1] == ExecStatus.failed
    assert args.args[2] is backend
    assert args.args[3] is finalize_db


@pytest.mark.asyncio
async def test_poll_skips_running() -> None:
    """A RUNNING container is not finalised."""
    execution = MagicMock()
    execution.job_ref = "container-3"
    execution.timeout_at = None
    execution.execution_type = "standard"

    backend = MagicMock()
    backend.status = AsyncMock(return_value=ExecutionStatus.RUNNING)

    list_db = MagicMock()
    list_repo = MagicMock()
    list_repo.list_active = AsyncMock(return_value=[execution])
    list_ctx = _make_async_ctx(list_db)

    def session_factory() -> MagicMock:
        return list_ctx

    def repo_factory(db: MagicMock) -> MagicMock:
        return list_repo

    with (
        patch("monitor.get_backend", return_value=backend),
        patch("monitor.AsyncSessionLocal", side_effect=session_factory),
        patch("monitor.ExecutionRepo", side_effect=repo_factory),
        patch("monitor._finalize", new_callable=AsyncMock) as mock_finalize,
    ):
        from monitor import _poll

        await _poll()

    mock_finalize.assert_not_called()


@pytest.mark.asyncio
async def test_poll_finalises_timed_out() -> None:
    """An execution past timeout_at is stopped regardless of container status."""
    from datetime import UTC as _UTC
    from uuid import uuid4

    past = datetime(2020, 1, 1, tzinfo=_UTC)
    exec_id = uuid4()

    execution = MagicMock()
    execution.id = exec_id
    execution.job_ref = "container-4"
    execution.timeout_at = past
    execution.execution_type = "standard"

    fresh_execution = MagicMock()

    backend = MagicMock()
    backend.status = AsyncMock()

    list_db = MagicMock()
    finalize_db = MagicMock()

    list_repo = MagicMock()
    list_repo.list_active = AsyncMock(return_value=[execution])

    finalize_repo = MagicMock()
    finalize_repo.get_by_id = AsyncMock(return_value=fresh_execution)

    list_ctx = _make_async_ctx(list_db)
    finalize_ctx = _make_async_ctx(finalize_db)

    call_count = 0

    def session_factory() -> MagicMock:
        nonlocal call_count
        call_count += 1
        return list_ctx if call_count == 1 else finalize_ctx

    def repo_factory(db: MagicMock) -> MagicMock:
        return list_repo if db is list_db else finalize_repo

    with (
        patch("monitor.get_backend", return_value=backend),
        patch("monitor.AsyncSessionLocal", side_effect=session_factory),
        patch("monitor.ExecutionRepo", side_effect=repo_factory),
        patch("monitor._finalize", new_callable=AsyncMock) as mock_finalize,
    ):
        from monitor import _poll

        await _poll()

    mock_finalize.assert_called_once()
    args = mock_finalize.call_args
    assert args.args[0] is fresh_execution
    assert args.args[1] == ExecStatus.stopped
    assert args.args[2] is backend
    assert args.args[3] is finalize_db
    backend.status.assert_not_called()  # timeout short-circuits status check


@pytest.mark.asyncio
async def test_poll_skips_no_job_ref() -> None:
    """An execution without job_ref is skipped entirely."""
    execution = MagicMock()
    execution.job_ref = None

    backend = MagicMock()
    list_db = MagicMock()
    list_repo = MagicMock()
    list_repo.list_active = AsyncMock(return_value=[execution])
    list_ctx = _make_async_ctx(list_db)

    def session_factory() -> MagicMock:
        return list_ctx

    def repo_factory(db: MagicMock) -> MagicMock:
        return list_repo

    with (
        patch("monitor.get_backend", return_value=backend),
        patch("monitor.AsyncSessionLocal", side_effect=session_factory),
        patch("monitor.ExecutionRepo", side_effect=repo_factory),
        patch("monitor._finalize", new_callable=AsyncMock) as mock_finalize,
    ):
        from monitor import _poll

        await _poll()

    mock_finalize.assert_not_called()


# ── monitor_loop ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_monitor_loop_calls_poll_and_continues_on_error() -> None:
    """monitor_loop() calls _poll() on each iteration; errors don't kill the loop."""
    call_count = 0

    async def fake_poll() -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("transient error")
        if call_count >= 2:
            raise asyncio.CancelledError()

    with (
        patch("monitor._poll", side_effect=fake_poll),
        patch("monitor.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        from monitor import monitor_loop

        with pytest.raises(asyncio.CancelledError):
            await monitor_loop()

    assert call_count == 2
    mock_sleep.assert_awaited()
