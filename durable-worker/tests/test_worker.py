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

"""Unit tests for worker.py startup validation."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_config import HttpServerRef, StdioServerRef
from manifest import HttpMCPToolSpec, StdioMCPToolSpec
from worker import _fetch_mcp_schemas, _resolve_headers


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


# ---------------------------------------------------------------------------
# _resolve_headers
# ---------------------------------------------------------------------------


def test_resolve_headers_no_placeholders() -> None:
    result = _resolve_headers({"X-Custom": "static-value"}, api_key_env=None)
    assert result == {"X-Custom": "static-value"}


def test_resolve_headers_expands_env_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_TOKEN", "abc123")
    result = _resolve_headers({"Authorization": "Bearer ${MY_TOKEN}"}, api_key_env=None)
    assert result == {"Authorization": "Bearer abc123"}


def test_resolve_headers_missing_env_var_resolves_to_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_VAR", raising=False)
    result = _resolve_headers({"X-Key": "${MISSING_VAR}"}, api_key_env=None)
    assert result == {"X-Key": ""}


def test_resolve_headers_api_key_env_adds_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCH_KEY", "secret")
    result = _resolve_headers({}, api_key_env="SEARCH_KEY")
    assert result == {"Authorization": "Bearer secret"}


def test_resolve_headers_api_key_env_skipped_when_authorization_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTHER_KEY", "other")
    result = _resolve_headers({"Authorization": "Bearer existing"}, api_key_env="OTHER_KEY")
    assert result == {"Authorization": "Bearer existing"}


def test_resolve_headers_api_key_env_missing_skips_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ABSENT_KEY", raising=False)
    result = _resolve_headers({}, api_key_env="ABSENT_KEY")
    assert result == {}


# ---------------------------------------------------------------------------
# _fetch_mcp_schemas — HTTP/SSE dispatch
# ---------------------------------------------------------------------------


def _make_tool(name: str, description: str = "", schema: dict | None = None):
    tool = MagicMock()
    tool.name = name
    tool.description = description
    tool.inputSchema = schema or {}
    return tool


async def test_fetch_mcp_schemas_http_returns_http_server_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = HttpMCPToolSpec(name="search", url="http://mcp:8000/mcp", transport="http")

    session_mock = AsyncMock()
    session_mock.list_tools.return_value = MagicMock(tools=[_make_tool("search_web")])

    cm_session = AsyncMock()
    cm_session.__aenter__ = AsyncMock(return_value=session_mock)
    cm_session.__aexit__ = AsyncMock(return_value=None)

    inner_cm = AsyncMock()
    inner_cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    inner_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("worker.streamablehttp_client", return_value=inner_cm),
        patch("worker.ClientSession", return_value=cm_session),
    ):
        schemas, tool_map = await _fetch_mcp_schemas([spec])

    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "search_web"
    assert "search_web" in tool_map
    ref = tool_map["search_web"]
    assert isinstance(ref, HttpServerRef)
    assert ref.url == "http://mcp:8000/mcp"
    assert ref.transport == "http"


async def test_fetch_mcp_schemas_sse_returns_http_server_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = HttpMCPToolSpec(name="crm", url="http://crm:9000/sse", transport="sse")

    session_mock = AsyncMock()
    session_mock.list_tools.return_value = MagicMock(tools=[_make_tool("get_contact")])

    cm_session = AsyncMock()
    cm_session.__aenter__ = AsyncMock(return_value=session_mock)
    cm_session.__aexit__ = AsyncMock(return_value=None)

    inner_cm = AsyncMock()
    inner_cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
    inner_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("worker.sse_client", return_value=inner_cm),
        patch("worker.ClientSession", return_value=cm_session),
    ):
        schemas, tool_map = await _fetch_mcp_schemas([spec])

    assert "get_contact" in tool_map
    ref = tool_map["get_contact"]
    assert isinstance(ref, HttpServerRef)
    assert ref.transport == "sse"


async def test_fetch_mcp_schemas_http_connection_failure_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = HttpMCPToolSpec(name="failing", url="http://dead:9999/mcp", transport="http")

    inner_cm = AsyncMock()
    inner_cm.__aenter__ = AsyncMock(side_effect=ConnectionRefusedError("refused"))
    inner_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("worker.streamablehttp_client", return_value=inner_cm):
        schemas, tool_map = await _fetch_mcp_schemas([spec])

    assert schemas == []
    assert tool_map == {}


async def test_fetch_mcp_schemas_resolves_headers_before_connecting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TOKEN", "tok123")
    spec = HttpMCPToolSpec(
        name="search",
        url="http://mcp:8000/mcp",
        transport="http",
        headers={"X-Key": "${API_TOKEN}"},
    )

    captured_headers: dict = {}

    def fake_streamablehttp_client(url: str, headers: dict):
        captured_headers.update(headers)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    session_mock = AsyncMock()
    session_mock.list_tools.return_value = MagicMock(tools=[])
    cm_session = AsyncMock()
    cm_session.__aenter__ = AsyncMock(return_value=session_mock)
    cm_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("worker.streamablehttp_client", side_effect=fake_streamablehttp_client),
        patch("worker.ClientSession", return_value=cm_session),
    ):
        await _fetch_mcp_schemas([spec])

    assert captured_headers.get("X-Key") == "tok123"
