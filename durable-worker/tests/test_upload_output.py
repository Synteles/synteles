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

"""Unit tests for the upload_output Temporal activity."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import respx
from temporalio.testing import ActivityEnvironment

from activities import upload_output


# ---------------------------------------------------------------------------
# Early-return cases (no ActivityEnvironment needed — no heartbeat called)
# ---------------------------------------------------------------------------


async def test_upload_output_noop_when_url_empty() -> None:
    """No-op when output_url is the empty string."""
    await upload_output("")  # must return without touching the filesystem


async def test_upload_output_noop_when_output_dir_missing(tmp_path: Path) -> None:
    """No-op when /tmp/output doesn't exist — nothing to upload."""
    missing_dir = str(tmp_path / "nonexistent")

    with patch("activities.os.path.isdir", return_value=False):
        await upload_output("https://bucket/output.zip")


async def test_upload_output_noop_when_output_dir_empty(tmp_path: Path) -> None:
    """No-op when /tmp/output is present but has no files."""
    with (
        patch("activities.os.path.isdir", return_value=True),
        patch("activities.os.walk", return_value=[(str(tmp_path), [], [])]),
    ):
        await upload_output("https://bucket/output.zip")


# ---------------------------------------------------------------------------
# Upload path (ActivityEnvironment needed for heartbeat calls)
# ---------------------------------------------------------------------------


@respx.mock
async def test_upload_output_zips_and_puts_to_presigned_url(tmp_path: Path) -> None:
    """Files in /tmp/output are zipped and PUT to the presigned URL on success."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "result.txt").write_text("hello")
    zip_path = str(tmp_path / "output.zip")

    respx.put("https://bucket.example.com/output.zip").respond(200)

    env = ActivityEnvironment()
    with (
        patch("activities.os.path.isdir", return_value=True),
        patch(
            "activities.os.walk",
            return_value=[(str(output_dir), [], ["result.txt"])],
        ),
        patch("activities.os.path.join", side_effect=os.path.join),
        patch("activities.os.path.relpath", side_effect=os.path.relpath),
        patch("activities.os.path.getsize", return_value=512),
        patch("activities._zipfile.ZipFile") as mock_zf_cls,
        patch("builtins.open", return_value=open(os.devnull, "rb")),
    ):
        mock_zf = mock_zf_cls.return_value.__enter__.return_value
        await env.run(upload_output, "https://bucket.example.com/output.zip")

    assert respx.calls.call_count == 1
    req = respx.calls.last.request
    assert req.method == "PUT"
    assert "Content-Type" in req.headers


@respx.mock
async def test_upload_output_raises_on_non_200_response(tmp_path: Path) -> None:
    """RuntimeError is raised so Temporal can retry when S3 returns an error status."""
    respx.put("https://bucket.example.com/output.zip").respond(500, text="Internal Server Error")

    env = ActivityEnvironment()
    with (
        patch("activities.os.path.isdir", return_value=True),
        patch(
            "activities.os.walk",
            return_value=[(str(tmp_path), [], ["file.txt"])],
        ),
        patch("activities.os.path.join", side_effect=os.path.join),
        patch("activities.os.path.relpath", side_effect=os.path.relpath),
        patch("activities.os.path.getsize", return_value=100),
        patch("activities._zipfile.ZipFile"),
        patch("builtins.open", return_value=open(os.devnull, "rb")),
    ):
        with pytest.raises(RuntimeError, match="500"):
            await env.run(upload_output, "https://bucket.example.com/output.zip")
