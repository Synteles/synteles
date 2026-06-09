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

"""Unit tests for call_http_mcp_tool activity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from activities import call_http_mcp_tool


def _make_content(text: str):
    c = MagicMock()
    c.text = text
    return c


async def test_call_http_mcp_tool_http_transport() -> None:
    session_mock = AsyncMock()
    result_mock = MagicMock()
    result_mock.content = [_make_content("result text")]
    session_mock.call_tool.return_value = result_mock

    cm_session = AsyncMock()
    cm_session.__aenter__ = AsyncMock(return_value=session_mock)
    cm_session.__aexit__ = AsyncMock(return_value=None)

    inner_cm = AsyncMock()
    inner_cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    inner_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("activities.streamablehttp_client", return_value=inner_cm),
        patch("activities.ClientSession", return_value=cm_session),
    ):
        result = await call_http_mcp_tool(
            url="http://mcp:8000/mcp",
            transport="http",
            headers={"Authorization": "Bearer tok"},
            tool_name="search_web",
            arguments={"query": "test"},
        )

    assert result == "result text"
    session_mock.call_tool.assert_called_once_with("search_web", {"query": "test"})


async def test_call_http_mcp_tool_sse_transport() -> None:
    session_mock = AsyncMock()
    result_mock = MagicMock()
    result_mock.content = [_make_content("sse result")]
    session_mock.call_tool.return_value = result_mock

    cm_session = AsyncMock()
    cm_session.__aenter__ = AsyncMock(return_value=session_mock)
    cm_session.__aexit__ = AsyncMock(return_value=None)

    inner_cm = AsyncMock()
    inner_cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
    inner_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("activities.sse_client", return_value=inner_cm),
        patch("activities.ClientSession", return_value=cm_session),
    ):
        result = await call_http_mcp_tool(
            url="http://crm:9000/sse",
            transport="sse",
            headers={},
            tool_name="get_contact",
            arguments={"id": "123"},
        )

    assert result == "sse result"
    session_mock.call_tool.assert_called_once_with("get_contact", {"id": "123"})


async def test_call_http_mcp_tool_http_passes_headers() -> None:
    captured: dict = {}

    def fake_streamablehttp_client(url: str, headers: dict):
        captured["url"] = url
        captured["headers"] = headers
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    session_mock = AsyncMock()
    result_mock = MagicMock()
    result_mock.content = []
    session_mock.call_tool.return_value = result_mock

    cm_session = AsyncMock()
    cm_session.__aenter__ = AsyncMock(return_value=session_mock)
    cm_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("activities.streamablehttp_client", side_effect=fake_streamablehttp_client),
        patch("activities.ClientSession", return_value=cm_session),
    ):
        await call_http_mcp_tool(
            url="http://mcp:8000/mcp",
            transport="http",
            headers={"X-Api-Key": "secret"},
            tool_name="do_something",
            arguments={},
        )

    assert captured["headers"] == {"X-Api-Key": "secret"}
    assert captured["url"] == "http://mcp:8000/mcp"


async def test_call_http_mcp_tool_multiple_content_parts_joined() -> None:
    session_mock = AsyncMock()
    result_mock = MagicMock()
    result_mock.content = [_make_content("part1"), _make_content("part2")]
    session_mock.call_tool.return_value = result_mock

    cm_session = AsyncMock()
    cm_session.__aenter__ = AsyncMock(return_value=session_mock)
    cm_session.__aexit__ = AsyncMock(return_value=None)

    inner_cm = AsyncMock()
    inner_cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    inner_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("activities.streamablehttp_client", return_value=inner_cm),
        patch("activities.ClientSession", return_value=cm_session),
    ):
        result = await call_http_mcp_tool(
            url="http://mcp:8000/mcp",
            transport="http",
            headers={},
            tool_name="tool",
            arguments={},
        )

    assert result == "part1\npart2"
