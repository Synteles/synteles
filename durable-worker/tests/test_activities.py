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

"""Unit tests for call_http_mcp_tool, call_llm_step, call_mcp_tool, and _download_input_files."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import litellm
import pytest
import respx
from temporalio.exceptions import ApplicationError

from activities import _download_input_files, call_http_mcp_tool, call_llm_step, call_mcp_tool


def _make_content(text: str) -> MagicMock:
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
    captured: dict[str, Any] = {}

    def fake_streamablehttp_client(url: str, headers: dict[str, str]) -> AsyncMock:
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


# ---------------------------------------------------------------------------
# I7: SSE branch must pass headers to sse_client
# ---------------------------------------------------------------------------


async def test_call_http_mcp_tool_sse_passes_headers() -> None:
    """SSE transport must pass auth headers to sse_client — tokens must reach SSE servers."""
    captured: dict[str, Any] = {}

    def fake_sse_client(url: str, headers: dict[str, str]) -> AsyncMock:
        captured["url"] = url
        captured["headers"] = headers
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
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
        patch("activities.sse_client", side_effect=fake_sse_client),
        patch("activities.ClientSession", return_value=cm_session),
    ):
        await call_http_mcp_tool(
            url="http://crm:9000/sse",
            transport="sse",
            headers={"Authorization": "Bearer secret"},
            tool_name="get_contact",
            arguments={"id": "1"},
        )

    assert captured["headers"] == {"Authorization": "Bearer secret"}
    assert captured["url"] == "http://crm:9000/sse"


# ---------------------------------------------------------------------------
# I4: call_llm_step must raise non-retryable ApplicationError for 4xx errors
# ---------------------------------------------------------------------------


async def test_call_llm_step_bad_request_raises_non_retryable() -> None:
    """400 BadRequest from the LLM must become a non-retryable ApplicationError."""
    err = litellm.BadRequestError(message="bad schema", model="gpt-4o", llm_provider="openai")  # type: ignore[attr-defined]

    with patch("activities.litellm.acompletion", side_effect=err):
        with pytest.raises(ApplicationError) as exc_info:
            await call_llm_step(
                messages=[{"role": "user", "content": "hi"}], tools=[], model="openai/gpt-4o"
            )

    assert exc_info.value.non_retryable is True


async def test_call_llm_step_auth_error_raises_non_retryable() -> None:
    """401 AuthenticationError from the LLM must become a non-retryable ApplicationError."""
    err = litellm.AuthenticationError(message="invalid key", model="gpt-4o", llm_provider="openai")  # type: ignore[attr-defined]

    with patch("activities.litellm.acompletion", side_effect=err):
        with pytest.raises(ApplicationError) as exc_info:
            await call_llm_step(
                messages=[{"role": "user", "content": "hi"}], tools=[], model="openai/gpt-4o"
            )

    assert exc_info.value.non_retryable is True


async def test_call_llm_step_permission_denied_raises_non_retryable() -> None:
    """403 PermissionDeniedError from the LLM must become a non-retryable ApplicationError."""
    mock_resp = httpx.Response(403, request=httpx.Request("POST", "http://test"))
    err = litellm.PermissionDeniedError(  # type: ignore[attr-defined]
        message="permission denied", model="gpt-4o", llm_provider="openai", response=mock_resp
    )

    with patch("activities.litellm.acompletion", side_effect=err):
        with pytest.raises(ApplicationError) as exc_info:
            await call_llm_step(
                messages=[{"role": "user", "content": "hi"}], tools=[], model="openai/gpt-4o"
            )

    assert exc_info.value.non_retryable is True


async def test_call_llm_step_transient_error_propagates_normally() -> None:
    """Transient errors (RateLimitError, ServiceUnavailableError) must propagate as-is for retry."""
    err = litellm.RateLimitError(message="rate limited", model="gpt-4o", llm_provider="openai")  # type: ignore[attr-defined]

    with patch("activities.litellm.acompletion", side_effect=err):
        with pytest.raises(litellm.RateLimitError):  # type: ignore[attr-defined]
            await call_llm_step(
                messages=[{"role": "user", "content": "hi"}], tools=[], model="openai/gpt-4o"
            )


# ---------------------------------------------------------------------------
# I4 (continued): call_llm_step success paths
# ---------------------------------------------------------------------------


def _make_response(
    content: str | None, tool_calls: list[dict[str, Any]] | None = None
) -> MagicMock:
    tc_mocks = []
    if tool_calls:
        for tc in tool_calls:
            tc_mock = MagicMock()
            tc_mock.id = tc["id"]
            tc_mock.function.name = tc["name"]
            tc_mock.function.arguments = tc["arguments"]
            tc_mocks.append(tc_mock)

    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tc_mocks if tc_mocks else None

    choice = MagicMock()
    choice.message = msg

    resp = MagicMock()
    resp.choices = [choice]
    return resp


async def test_call_llm_step_returns_text_without_tool_calls() -> None:
    """Successful LLM response with plain text and no tool calls."""
    with patch("activities.litellm.acompletion", return_value=_make_response("Hello!")):
        result = await call_llm_step(
            messages=[{"role": "user", "content": "hi"}], tools=[], model="openai/gpt-4o"
        )

    assert result == {"role": "assistant", "content": "Hello!", "tool_calls": None}


async def test_call_llm_step_returns_tool_calls() -> None:
    """LLM response with tool calls maps IDs and arguments into the result dict."""
    tcs = [{"id": "call_1", "name": "search", "arguments": '{"q":"hello"}'}]
    with patch("activities.litellm.acompletion", return_value=_make_response(None, tcs)):
        result = await call_llm_step(
            messages=[{"role": "user", "content": "search"}],
            tools=[{"type": "function", "function": {"name": "search"}}],
            model="openai/gpt-4o",
        )

    assert result["tool_calls"] is not None
    assert result["tool_calls"][0]["id"] == "call_1"
    assert result["tool_calls"][0]["function"]["name"] == "search"
    assert result["tool_calls"][0]["function"]["arguments"] == '{"q":"hello"}'


# ---------------------------------------------------------------------------
# call_mcp_tool
# ---------------------------------------------------------------------------


def _make_mcp_session(content_items: list[Any]) -> tuple[AsyncMock, AsyncMock, AsyncMock]:
    result_mock = MagicMock()
    result_mock.content = content_items

    session_mock = AsyncMock()
    session_mock.call_tool.return_value = result_mock

    cm_session = AsyncMock()
    cm_session.__aenter__ = AsyncMock(return_value=session_mock)
    cm_session.__aexit__ = AsyncMock(return_value=None)

    inner_cm = AsyncMock()
    inner_cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
    inner_cm.__aexit__ = AsyncMock(return_value=None)

    return cm_session, inner_cm, session_mock


async def test_call_mcp_tool_returns_text_content() -> None:
    """call_mcp_tool returns concatenated text from MCP tool result."""
    content = MagicMock()
    content.text = "tool output"
    cm_session, inner_cm, session_mock = _make_mcp_session([content])

    with (
        patch("mcp.client.stdio.stdio_client", return_value=inner_cm),
        patch("activities.ClientSession", return_value=cm_session),
    ):
        result = await call_mcp_tool(
            command="python",
            args=["-m", "tool"],
            env={"KEY": "val"},
            tool_name="do_thing",
            arguments={"x": 1},
        )

    assert result == "tool output"
    session_mock.call_tool.assert_called_once_with("do_thing", {"x": 1})


async def test_call_mcp_tool_stringifies_non_text_content() -> None:
    """Content items without a .text attribute are converted via str()."""

    class _BinaryBlob:
        def __str__(self) -> str:
            return "binary-data"

    cm_session, inner_cm, _ = _make_mcp_session([_BinaryBlob()])

    with (
        patch("mcp.client.stdio.stdio_client", return_value=inner_cm),
        patch("activities.ClientSession", return_value=cm_session),
    ):
        result = await call_mcp_tool(
            command="reader",
            args=[],
            env={},
            tool_name="get_blob",
            arguments={},
        )

    assert result == "binary-data"


async def test_call_mcp_tool_multiple_content_parts_joined() -> None:
    """Multiple content items are joined with newlines."""
    c1, c2 = MagicMock(), MagicMock()
    c1.text = "part1"
    c2.text = "part2"
    cm_session, inner_cm, _ = _make_mcp_session([c1, c2])

    with (
        patch("mcp.client.stdio.stdio_client", return_value=inner_cm),
        patch("activities.ClientSession", return_value=cm_session),
    ):
        result = await call_mcp_tool(
            command="tool",
            args=[],
            env={},
            tool_name="multi",
            arguments={},
        )

    assert result == "part1\npart2"


# ---------------------------------------------------------------------------
# call_http_mcp_tool — non-text content fallback (line 393)
# ---------------------------------------------------------------------------


async def test_call_http_mcp_tool_sse_stringifies_non_text_content() -> None:
    """SSE branch: content items without .text attribute are stringified."""

    class _BinaryContent:
        def __str__(self) -> str:
            return "binary"

    result_mock = MagicMock()
    result_mock.content = [_BinaryContent()]

    session_mock = AsyncMock()
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
            tool_name="get_binary",
            arguments={},
        )

    assert result == "binary"


# ---------------------------------------------------------------------------
# _download_input_files
# ---------------------------------------------------------------------------


@respx.mock
async def test_download_input_files_fetches_file_to_dest_dir(
    tmp_path: Path,
) -> None:
    """Files are downloaded from presigned URLs into the destination directory."""
    respx.get("http://store:9000/report.pdf").respond(200, content=b"PDF content")
    files = [{"name": "report.pdf", "url": "http://store:9000/report.pdf"}]

    await _download_input_files(files, trusted_netloc="store:9000", dest_dir=str(tmp_path))

    assert (tmp_path / "report.pdf").read_bytes() == b"PDF content"


async def test_download_input_files_raises_on_untrusted_host(tmp_path: Path) -> None:
    """SSRF guard: URLs with a host different from trusted_netloc raise ValueError."""
    files = [{"name": "evil.pdf", "url": "http://evil.com/evil.pdf"}]

    with pytest.raises(ValueError, match="does not match"):
        await _download_input_files(files, trusted_netloc="store:9000", dest_dir=str(tmp_path))


async def test_download_input_files_skips_entry_without_name(tmp_path: Path) -> None:
    """Entries missing 'name' are silently skipped — no file created."""
    files = [{"url": "http://store:9000/file.pdf"}]

    await _download_input_files(files, trusted_netloc="store:9000", dest_dir=str(tmp_path))

    assert list(tmp_path.iterdir()) == []  # noqa: ASYNC240


async def test_download_input_files_skips_entry_without_url(tmp_path: Path) -> None:
    """Entries missing 'url' are silently skipped — no file created."""
    files = [{"name": "file.pdf"}]

    await _download_input_files(files, trusted_netloc="store:9000", dest_dir=str(tmp_path))

    assert list(tmp_path.iterdir()) == []  # noqa: ASYNC240
