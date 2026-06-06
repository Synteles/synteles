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

"""Unit tests for worker.py helpers and startup validation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from manifest import MCPToolSpec
from worker import _make_stdio_factory

# ---------------------------------------------------------------------------
# _make_stdio_factory
# ---------------------------------------------------------------------------


def test_make_stdio_factory_returns_callable() -> None:
    tool = MCPToolSpec(name="my_tool", command="python", args=["-m", "my_tool"])
    factory = _make_stdio_factory(tool)
    assert callable(factory)


def test_make_stdio_factory_captures_tool_by_value() -> None:
    """Each factory should independently capture its own tool config."""
    tool_a = MCPToolSpec(name="tool_a", command="cmd_a", args=["--flag"])
    tool_b = MCPToolSpec(name="tool_b", command="cmd_b")

    factory_a = _make_stdio_factory(tool_a)
    factory_b = _make_stdio_factory(tool_b)

    mock_server = MagicMock()
    with patch("worker.MCPServerStdio", return_value=mock_server) as mock_cls:
        factory_a()
        call_a = mock_cls.call_args

        factory_b()
        call_b = mock_cls.call_args

    assert call_a.kwargs["params"]["command"] == "cmd_a"
    assert call_b.kwargs["params"]["command"] == "cmd_b"


def test_make_stdio_factory_passes_name() -> None:
    tool = MCPToolSpec(name="doc_reader", command="python")
    with patch("worker.MCPServerStdio") as mock_cls:
        _make_stdio_factory(tool)()
    assert mock_cls.call_args.kwargs["name"] == "doc_reader"


def test_make_stdio_factory_passes_args() -> None:
    tool = MCPToolSpec(name="t", command="cmd", args=["-m", "server"])
    with patch("worker.MCPServerStdio") as mock_cls:
        _make_stdio_factory(tool)()
    assert mock_cls.call_args.kwargs["params"]["args"] == ["-m", "server"]


def test_make_stdio_factory_empty_args() -> None:
    tool = MCPToolSpec(name="t", command="cmd")
    with patch("worker.MCPServerStdio") as mock_cls:
        _make_stdio_factory(tool)()
    assert mock_cls.call_args.kwargs["params"]["args"] == []


# ---------------------------------------------------------------------------
# main() — env var validation
# ---------------------------------------------------------------------------


async def test_main_raises_when_manifest_url_missing() -> None:
    with patch("worker.SYNTELES_MANIFEST_URL", ""):
        with pytest.raises(RuntimeError, match="SYNTELES_MANIFEST_URL"):
            from worker import main

            await main()


async def test_main_raises_when_task_queue_missing() -> None:
    with (
        patch("worker.SYNTELES_MANIFEST_URL", "http://example.com/manifest.json"),
        patch("worker.TEMPORAL_TASK_QUEUE", ""),
    ):
        with pytest.raises(RuntimeError, match="TEMPORAL_TASK_QUEUE"):
            from worker import main

            await main()


async def test_main_raises_when_execution_id_missing() -> None:
    with (
        patch("worker.SYNTELES_MANIFEST_URL", "http://example.com/manifest.json"),
        patch("worker.TEMPORAL_TASK_QUEUE", "my-queue"),
        patch("worker.EXECUTION_ID", ""),
    ):
        with pytest.raises(RuntimeError, match="EXECUTION_ID"):
            from worker import main

            await main()
