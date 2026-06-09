# MCP HTTP Transport Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Streamable HTTP and SSE MCP server support to the durable-worker alongside the existing stdio transport.

**Architecture:** Introduce discriminated dataclasses (`StdioMCPToolSpec`/`HttpMCPToolSpec` in `manifest.py`, `StdioServerRef`/`HttpServerRef` in `agent_config.py`). A new `call_http_mcp_tool` Temporal activity handles HTTP/SSE connections. The workflow dispatches to the correct activity via an `isinstance` check on the server ref type.

**Tech Stack:** Python 3.12, `mcp>=1.9` (already installed — ships `mcp.client.streamable_http` and `mcp.client.sse`), `temporalio`, `pytest`, `unittest.mock`

---

## File Map

| File | Change |
|---|---|
| `durable-worker/manifest.py` | Add `StdioMCPToolSpec`, `HttpMCPToolSpec`, `MCPToolSpec` alias; update `AgentletSpec`; update `parse_agentlet()` |
| `durable-worker/agent_config.py` | Add `StdioServerRef`, `HttpServerRef`; rename `MCPServerRef` to union alias |
| `durable-worker/worker.py` | Add `_resolve_headers()`; promote MCP imports to module level; update `_fetch_mcp_schemas()` |
| `durable-worker/activities.py` | Add module-level HTTP MCP imports; add `call_http_mcp_tool` activity |
| `durable-worker/workflows/agent.py` | Import `call_http_mcp_tool`; add isinstance dispatch |
| `durable-worker/tests/test_manifest.py` | Update import; replace excluded test; add http/sse/mixed tests |
| `durable-worker/tests/test_worker.py` | Add `_resolve_headers` tests |
| `durable-worker/tests/test_activities.py` | Create — tests for `call_http_mcp_tool` |

---

## Task 1: Data Model — `manifest.py` and `agent_config.py`

**Files:**
- Modify: `durable-worker/manifest.py`
- Modify: `durable-worker/agent_config.py`

### manifest.py

- [ ] **Step 1.1: Replace `MCPToolSpec` with two discriminated dataclasses and a union alias**

Replace the entire `MCPToolSpec` class and `AgentletSpec.mcp_tools` field. The `from typing import Literal` import is needed; the file already has `from __future__ import annotations`.

```python
# durable-worker/manifest.py — replace from line 1 of the $defs block

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx
import yaml


@dataclass
class StdioMCPToolSpec:
    """MCP server launched as a subprocess (stdio transport)."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class HttpMCPToolSpec:
    """MCP server reached over HTTP (Streamable HTTP or SSE transport)."""

    name: str
    url: str
    transport: Literal["http", "sse"]
    headers: dict[str, str] = field(default_factory=dict)   # raw ${VAR} placeholders
    api_key_env: str | None = None


MCPToolSpec = StdioMCPToolSpec | HttpMCPToolSpec


@dataclass
class AgentletSpec:
    system_prompt: str
    prompt: str | None
    provider: str
    model_id: str
    mcp_tools: list[MCPToolSpec] = field(default_factory=list)
```

### agent_config.py

- [ ] **Step 1.2: Replace `MCPServerRef` with two discriminated dataclasses and a union alias**

```python
# durable-worker/agent_config.py — full replacement of the dataclass block

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class StdioServerRef:
    """Reference to a stdio MCP server — used by call_mcp_tool activity."""

    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class HttpServerRef:
    """Reference to an HTTP/SSE MCP server — used by call_http_mcp_tool activity."""

    url: str
    transport: Literal["http", "sse"]
    headers: dict[str, str] = field(default_factory=dict)   # already resolved


# Union alias — kept for type annotations; isinstance works with this in Python 3.10+
MCPServerRef = StdioServerRef | HttpServerRef


system_prompt: str = ""
effective_prompt: str = ""

# LiteLLM model string, e.g. "azure_ai/gpt-5.3-chat", "openai/gpt-4o"
model: str = "azure_ai/gpt-5.3-chat"

# OpenAI-format tool schemas to pass to litellm — MCP tools discovered at startup
tools_schema: list[dict] = []  # type: ignore[type-arg]

# Maps each MCP tool name to the server that provides it
mcp_tool_map: dict[str, MCPServerRef] = {}  # type: ignore[valid-type]

# Presigned S3 PUT URL for output.zip
output_url: str = ""
```

- [ ] **Step 1.3: Verify no syntax errors**

```bash
cd durable-worker && uv run python -c "from manifest import StdioMCPToolSpec, HttpMCPToolSpec, MCPToolSpec; from agent_config import StdioServerRef, HttpServerRef, MCPServerRef; print('ok')"
```

Expected output: `ok`

- [ ] **Step 1.4: Commit**

```bash
git add durable-worker/manifest.py durable-worker/agent_config.py
git commit -m "feat(durable-worker): add discriminated MCP tool spec and server ref types"
```

---

## Task 2: `parse_agentlet()` — HTTP/SSE Parsing + Tests

**Files:**
- Modify: `durable-worker/manifest.py`
- Modify: `durable-worker/tests/test_manifest.py`

- [ ] **Step 2.1: Write failing tests first**

Open `durable-worker/tests/test_manifest.py`. Make the following changes:

**Update the import line** (line 23) — add the new types:

```python
from manifest import (
    AgentletSpec,
    HttpMCPToolSpec,
    MCPToolSpec,
    StdioMCPToolSpec,
    fetch_manifest,
    parse_agentlet,
    resolve_prompt,
)
```

**Replace `test_parse_agentlet_non_stdio_tools_excluded`** (lines 159–171) — it tested that `server: http` is excluded. Delete it and add the following tests at the end of the `parse_agentlet — mcp_tools` section:

```python
def test_parse_agentlet_http_tool_included() -> None:
    yaml = """\
mcp_tools:
  - name: search
    server: http
    url: http://search:8000/mcp
"""
    spec = parse_agentlet({"agentlet_yaml": yaml})
    assert len(spec.mcp_tools) == 1
    assert isinstance(spec.mcp_tools[0], HttpMCPToolSpec)
    assert spec.mcp_tools[0].name == "search"
    assert spec.mcp_tools[0].url == "http://search:8000/mcp"
    assert spec.mcp_tools[0].transport == "http"


def test_parse_agentlet_sse_tool_included() -> None:
    yaml = """\
mcp_tools:
  - name: crm
    server: sse
    url: http://crm:9000/sse
"""
    spec = parse_agentlet({"agentlet_yaml": yaml})
    assert len(spec.mcp_tools) == 1
    assert isinstance(spec.mcp_tools[0], HttpMCPToolSpec)
    assert spec.mcp_tools[0].transport == "sse"


def test_parse_agentlet_http_tool_headers_and_api_key_env() -> None:
    yaml = """\
mcp_tools:
  - name: search
    server: http
    url: http://search:8000/mcp
    headers:
      X-Custom: "value"
    api_key_env: SEARCH_KEY
"""
    spec = parse_agentlet({"agentlet_yaml": yaml})
    tool = spec.mcp_tools[0]
    assert isinstance(tool, HttpMCPToolSpec)
    assert tool.headers == {"X-Custom": "value"}
    assert tool.api_key_env == "SEARCH_KEY"


def test_parse_agentlet_http_tool_without_url_excluded() -> None:
    yaml = """\
mcp_tools:
  - name: no_url
    server: http
"""
    spec = parse_agentlet({"agentlet_yaml": yaml})
    assert spec.mcp_tools == []


def test_parse_agentlet_mixed_transports() -> None:
    yaml = """\
mcp_tools:
  - name: files
    server: stdio
    command: file-server
  - name: search
    server: http
    url: http://search:8000/mcp
  - name: crm
    server: sse
    url: http://crm:9000/sse
"""
    spec = parse_agentlet({"agentlet_yaml": yaml})
    assert len(spec.mcp_tools) == 3
    assert isinstance(spec.mcp_tools[0], StdioMCPToolSpec)
    assert isinstance(spec.mcp_tools[1], HttpMCPToolSpec)
    assert isinstance(spec.mcp_tools[2], HttpMCPToolSpec)


def test_parse_agentlet_unknown_server_type_excluded() -> None:
    yaml = """\
mcp_tools:
  - name: ws_tool
    server: websocket
    url: ws://localhost:9999
"""
    spec = parse_agentlet({"agentlet_yaml": yaml})
    assert spec.mcp_tools == []
```

- [ ] **Step 2.2: Run tests — expect failures**

```bash
cd durable-worker && uv run pytest tests/test_manifest.py -v -k "http or sse or mixed or unknown_server"
```

Expected: multiple FAILED (parse_agentlet returns StdioMCPToolSpec for http/sse, http tool is excluded)

- [ ] **Step 2.3: Update `parse_agentlet()` in manifest.py**

Replace the `mcp_tools` parsing block inside `parse_agentlet()`. Current code:

```python
    mcp_tools: list[MCPToolSpec] = []
    for tool in config.get("mcp_tools") or []:
        if tool.get("server") == "stdio" and tool.get("command"):
            mcp_tools.append(
                MCPToolSpec(
                    name=tool["name"],
                    command=tool["command"],
                    args=tool.get("args") or [],
                    env=tool.get("env") or {},
                )
            )
```

Replace with:

```python
    mcp_tools: list[MCPToolSpec] = []
    for tool in config.get("mcp_tools") or []:
        server = tool.get("server")
        if server == "stdio":
            if not tool.get("command"):
                continue
            mcp_tools.append(
                StdioMCPToolSpec(
                    name=tool["name"],
                    command=tool["command"],
                    args=tool.get("args") or [],
                    env=tool.get("env") or {},
                )
            )
        elif server in ("http", "sse"):
            if not tool.get("url"):
                continue
            mcp_tools.append(
                HttpMCPToolSpec(
                    name=tool["name"],
                    url=tool["url"],
                    transport=server,
                    headers=tool.get("headers") or {},
                    api_key_env=tool.get("api_key_env") or None,
                )
            )
```

- [ ] **Step 2.4: Run the new tests — expect all pass**

```bash
cd durable-worker && uv run pytest tests/test_manifest.py -v
```

Expected: all PASSED (including the updated non-stdio test replaced by the new ones)

- [ ] **Step 2.5: Commit**

```bash
git add durable-worker/manifest.py durable-worker/tests/test_manifest.py
git commit -m "feat(durable-worker): parse http/sse MCP tool entries in parse_agentlet"
```

---

## Task 3: `_resolve_headers()` in `worker.py` + Tests

**Files:**
- Modify: `durable-worker/worker.py`
- Modify: `durable-worker/tests/test_worker.py`

- [ ] **Step 3.1: Write failing tests**

Append to `durable-worker/tests/test_worker.py`:

```python
import os
from unittest.mock import patch

from worker import _resolve_headers


def test_resolve_headers_substitutes_env_var() -> None:
    with patch.dict(os.environ, {"MY_KEY": "secret123"}):
        result = _resolve_headers({"Authorization": "Bearer ${MY_KEY}"}, None)
    assert result == {"Authorization": "Bearer secret123"}


def test_resolve_headers_missing_var_resolves_to_empty_string() -> None:
    result = _resolve_headers({"X-Token": "${NONEXISTENT_VAR}"}, None)
    assert result == {"X-Token": ""}


def test_resolve_headers_api_key_env_adds_authorization() -> None:
    with patch.dict(os.environ, {"SEARCH_KEY": "mytoken"}):
        result = _resolve_headers({}, "SEARCH_KEY")
    assert result == {"Authorization": "Bearer mytoken"}


def test_resolve_headers_api_key_env_skipped_when_auth_header_present() -> None:
    with patch.dict(os.environ, {"SEARCH_KEY": "mytoken"}):
        result = _resolve_headers({"Authorization": "Bearer existing"}, "SEARCH_KEY")
    assert result == {"Authorization": "Bearer existing"}


def test_resolve_headers_api_key_env_missing_env_var_adds_nothing() -> None:
    result = _resolve_headers({}, "NONEXISTENT_KEY")
    assert "Authorization" not in result


def test_resolve_headers_empty_inputs_returns_empty() -> None:
    result = _resolve_headers({}, None)
    assert result == {}
```

- [ ] **Step 3.2: Run tests — expect ImportError or AttributeError**

```bash
cd durable-worker && uv run pytest tests/test_worker.py -v -k "resolve_headers"
```

Expected: FAILED — `cannot import name '_resolve_headers' from 'worker'`

- [ ] **Step 3.3: Add `_resolve_headers` to `worker.py`**

Add `import re` to the imports block in `worker.py` (after the existing `import os` line):

```python
import re
```

Add the function after the `logger = logging.getLogger(__name__)` line (before `_fetch_mcp_schemas`):

```python
def _resolve_headers(
    headers: dict[str, str],
    api_key_env: str | None,
) -> dict[str, str]:
    """Resolve ${VAR} placeholders in header values from os.environ.

    If api_key_env names an env var and no Authorization header is present,
    adds Authorization: Bearer <value>.
    """
    resolved: dict[str, str] = {
        key: re.sub(r"\$\{([^}]+)\}", lambda m: os.environ.get(m.group(1), ""), value)
        for key, value in headers.items()
    }
    if api_key_env and "Authorization" not in resolved:
        key_value = os.environ.get(api_key_env, "")
        if key_value:
            resolved["Authorization"] = f"Bearer {key_value}"
        else:
            logger.warning("api_key_env=%r is set but the env var is empty or missing", api_key_env)
    return resolved
```

- [ ] **Step 3.4: Run tests — expect all pass**

```bash
cd durable-worker && uv run pytest tests/test_worker.py -v
```

Expected: all PASSED

- [ ] **Step 3.5: Commit**

```bash
git add durable-worker/worker.py durable-worker/tests/test_worker.py
git commit -m "feat(durable-worker): add _resolve_headers for HTTP MCP header interpolation"
```

---

## Task 4: `_fetch_mcp_schemas()` — HTTP/SSE Branch + Tests

**Files:**
- Modify: `durable-worker/worker.py`
- Modify: `durable-worker/tests/test_worker.py`

- [ ] **Step 4.1: Write failing tests**

Append to `durable-worker/tests/test_worker.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_config import HttpServerRef, StdioServerRef
from manifest import HttpMCPToolSpec, StdioMCPToolSpec
from worker import _fetch_mcp_schemas


def _make_mock_session(tool_name: str = "my_tool") -> AsyncMock:
    mock_tool = MagicMock()
    mock_tool.name = tool_name
    mock_tool.description = "A tool"
    mock_tool.inputSchema = {"type": "object", "properties": {}}

    mock_tools_result = MagicMock()
    mock_tools_result.tools = [mock_tool]

    session = AsyncMock()
    session.initialize = AsyncMock(return_value=None)
    session.list_tools = AsyncMock(return_value=mock_tools_result)
    return session


async def test_fetch_mcp_schemas_http_returns_schema_and_http_server_ref() -> None:
    mock_session = _make_mock_session("search")

    mock_http_cm = MagicMock()
    mock_http_cm.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock(), None))
    mock_http_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    spec = HttpMCPToolSpec(name="search_srv", url="http://search:8000/mcp", transport="http")

    with patch("worker.streamablehttp_client", return_value=mock_http_cm):
        with patch("worker.ClientSession", return_value=mock_session_cm):
            schemas, tool_map = await _fetch_mcp_schemas([spec])

    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "search"
    assert "search" in tool_map
    ref = tool_map["search"]
    assert isinstance(ref, HttpServerRef)
    assert ref.url == "http://search:8000/mcp"
    assert ref.transport == "http"


async def test_fetch_mcp_schemas_sse_uses_sse_client() -> None:
    mock_session = _make_mock_session("crm_list")

    mock_sse_cm = MagicMock()
    mock_sse_cm.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
    mock_sse_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    spec = HttpMCPToolSpec(name="crm_srv", url="http://crm:9000/sse", transport="sse")

    with patch("worker.sse_client", return_value=mock_sse_cm):
        with patch("worker.ClientSession", return_value=mock_session_cm):
            schemas, tool_map = await _fetch_mcp_schemas([spec])

    assert "crm_list" in tool_map
    assert isinstance(tool_map["crm_list"], HttpServerRef)
    assert tool_map["crm_list"].transport == "sse"


async def test_fetch_mcp_schemas_http_resolves_headers() -> None:
    mock_session = _make_mock_session()

    mock_http_cm = MagicMock()
    mock_http_cm.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock(), None))
    mock_http_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    spec = HttpMCPToolSpec(
        name="srv",
        url="http://srv:8000/mcp",
        transport="http",
        headers={"Authorization": "Bearer ${MY_TOKEN}"},
    )

    captured: dict = {}

    def capture_client(url: str, headers: dict) -> MagicMock:
        captured["headers"] = headers
        return mock_http_cm

    with patch.dict(os.environ, {"MY_TOKEN": "tok123"}):
        with patch("worker.streamablehttp_client", side_effect=capture_client):
            with patch("worker.ClientSession", return_value=mock_session_cm):
                await _fetch_mcp_schemas([spec])

    assert captured["headers"] == {"Authorization": "Bearer tok123"}


async def test_fetch_mcp_schemas_http_connection_failure_skips_server() -> None:
    spec = HttpMCPToolSpec(name="bad_srv", url="http://missing:9999/mcp", transport="http")

    mock_http_cm = MagicMock()
    mock_http_cm.__aenter__ = AsyncMock(side_effect=ConnectionError("refused"))
    mock_http_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("worker.streamablehttp_client", return_value=mock_http_cm):
        schemas, tool_map = await _fetch_mcp_schemas([spec])

    assert schemas == []
    assert tool_map == {}
```

- [ ] **Step 4.2: Run tests — expect failures**

```bash
cd durable-worker && uv run pytest tests/test_worker.py -v -k "fetch_mcp_schemas"
```

Expected: FAILED — `worker` has no attribute `streamablehttp_client` / `sse_client`

- [ ] **Step 4.3: Update imports in `worker.py`**

Replace the import lines (currently lines 42–46):

```python
import agent_config
from activities import call_llm_step, call_mcp_tool, upload_output
from agent_config import MCPServerRef
from config import EXECUTION_ID, SYNTELES_MANIFEST_URL, SYNTELES_OUTPUT_URL, TEMPORAL_ADDRESS, TEMPORAL_TASK_QUEUE
from manifest import MCPToolSpec, fetch_manifest, parse_agentlet, resolve_prompt
from workflows.agent import AgentWorkflow
```

With:

```python
import agent_config
from activities import call_llm_step, call_mcp_tool, upload_output
from agent_config import HttpServerRef, MCPServerRef, StdioServerRef
from config import EXECUTION_ID, SYNTELES_MANIFEST_URL, SYNTELES_OUTPUT_URL, TEMPORAL_ADDRESS, TEMPORAL_TASK_QUEUE
from manifest import HttpMCPToolSpec, MCPToolSpec, StdioMCPToolSpec, fetch_manifest, parse_agentlet, resolve_prompt
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from workflows.agent import AgentWorkflow
```

- [ ] **Step 4.4: Update `_fetch_mcp_schemas()` to handle HTTP/SSE**

Replace the entire `_fetch_mcp_schemas` function body:

```python
async def _fetch_mcp_schemas(
    mcp_tools: list[MCPToolSpec],
) -> tuple[list[dict], dict[str, MCPServerRef]]:  # type: ignore[type-arg]
    """Query each MCP server for its tool list (stdio, HTTP, or SSE).

    Returns (openai-format tool schemas, tool_name → MCPServerRef mapping).
    Servers that fail to connect are skipped with a warning.
    """
    schemas: list[dict] = []  # type: ignore[type-arg]
    tool_map: dict[str, MCPServerRef] = {}

    for spec in mcp_tools:
        if isinstance(spec, StdioMCPToolSpec):
            server_params = StdioServerParameters(
                command=spec.command,
                args=spec.args,
                env={**os.environ, **spec.env},
            )
            try:
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_list = await session.list_tools()
                        ref: MCPServerRef = StdioServerRef(command=spec.command, args=spec.args, env=spec.env)
                        for tool in tools_list.tools:
                            schemas.append(
                                {
                                    "type": "function",
                                    "function": {
                                        "name": tool.name,
                                        "description": tool.description or "",
                                        "parameters": tool.inputSchema,
                                    },
                                }
                            )
                            tool_map[tool.name] = ref
                logger.info("Fetched %d tools from MCP server '%s'", len(tools_list.tools), spec.name)
            except Exception as exc:
                logger.warning("Failed to reach MCP server '%s': %s", spec.name, exc)

        else:  # HttpMCPToolSpec
            resolved = _resolve_headers(spec.headers, spec.api_key_env)
            http_ref = HttpServerRef(url=spec.url, transport=spec.transport, headers=resolved)
            try:
                if spec.transport == "http":
                    async with streamablehttp_client(spec.url, headers=resolved) as (read, write, _):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            tools_list = await session.list_tools()
                else:  # sse — headers not forwarded (per schema)
                    async with sse_client(spec.url) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            tools_list = await session.list_tools()
                for tool in tools_list.tools:
                    schemas.append(
                        {
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description or "",
                                "parameters": tool.inputSchema,
                            },
                        }
                    )
                    tool_map[tool.name] = http_ref
                logger.info(
                    "Fetched %d tools from HTTP MCP server '%s'", len(tools_list.tools), spec.name
                )
            except Exception as exc:
                logger.warning("Failed to reach HTTP MCP server '%s': %s", spec.name, exc)

    return schemas, tool_map
```

- [ ] **Step 4.5: Run all worker tests — expect all pass**

```bash
cd durable-worker && uv run pytest tests/test_worker.py -v
```

Expected: all PASSED

- [ ] **Step 4.6: Commit**

```bash
git add durable-worker/worker.py durable-worker/tests/test_worker.py
git commit -m "feat(durable-worker): add HTTP/SSE branch to _fetch_mcp_schemas"
```

---

## Task 5: `call_http_mcp_tool` Activity + Tests

**Files:**
- Modify: `durable-worker/activities.py`
- Create: `durable-worker/tests/test_activities.py`

- [ ] **Step 5.1: Write failing tests**

Create `durable-worker/tests/test_activities.py`:

```python
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

"""Unit tests for activities.py — call_http_mcp_tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.testing import ActivityEnvironment

from activities import call_http_mcp_tool


def _make_tool_result(text: str = "result text") -> MagicMock:
    content_item = MagicMock()
    content_item.text = text
    result = MagicMock()
    result.content = [content_item]
    return result


def _make_session_cm(tool_result: MagicMock) -> MagicMock:
    session = AsyncMock()
    session.initialize = AsyncMock(return_value=None)
    session.call_tool = AsyncMock(return_value=tool_result)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


async def test_call_http_mcp_tool_streamable_returns_text() -> None:
    env = ActivityEnvironment()
    result = _make_tool_result("found 3 results")
    session_cm = _make_session_cm(result)

    http_cm = MagicMock()
    http_cm.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock(), None))
    http_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("activities.streamablehttp_client", return_value=http_cm):
        with patch("activities.ClientSession", return_value=session_cm):
            output = await env.run(
                call_http_mcp_tool,
                "http://search:8000/mcp",
                "http",
                {"Authorization": "Bearer tok"},
                "web_search",
                {"query": "test"},
            )

    assert output == "found 3 results"


async def test_call_http_mcp_tool_sse_uses_sse_client() -> None:
    env = ActivityEnvironment()
    result = _make_tool_result("sse result")
    session_cm = _make_session_cm(result)

    sse_cm = MagicMock()
    sse_cm.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
    sse_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("activities.sse_client", return_value=sse_cm):
        with patch("activities.ClientSession", return_value=session_cm):
            output = await env.run(
                call_http_mcp_tool,
                "http://crm:9000/sse",
                "sse",
                {},
                "list_contacts",
                {},
            )

    assert output == "sse result"


async def test_call_http_mcp_tool_multiple_content_parts_joined() -> None:
    env = ActivityEnvironment()

    part1 = MagicMock()
    part1.text = "line one"
    part2 = MagicMock()
    part2.text = "line two"
    result = MagicMock()
    result.content = [part1, part2]

    session_cm = _make_session_cm(result)
    http_cm = MagicMock()
    http_cm.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock(), None))
    http_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("activities.streamablehttp_client", return_value=http_cm):
        with patch("activities.ClientSession", return_value=session_cm):
            output = await env.run(
                call_http_mcp_tool,
                "http://srv:8000/mcp",
                "http",
                {},
                "my_tool",
                {},
            )

    assert output == "line one\nline two"


async def test_call_http_mcp_tool_non_text_content_stringified() -> None:
    env = ActivityEnvironment()

    part = MagicMock(spec=[])   # no 'text' attribute
    part.__str__ = lambda self: "binary blob"
    result = MagicMock()
    result.content = [part]

    session_cm = _make_session_cm(result)
    http_cm = MagicMock()
    http_cm.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock(), None))
    http_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("activities.streamablehttp_client", return_value=http_cm):
        with patch("activities.ClientSession", return_value=session_cm):
            output = await env.run(
                call_http_mcp_tool,
                "http://srv:8000/mcp",
                "http",
                {},
                "my_tool",
                {},
            )

    assert output == "binary blob"
```

- [ ] **Step 5.2: Run tests — expect ImportError**

```bash
cd durable-worker && uv run pytest tests/test_activities.py -v
```

Expected: FAILED — `cannot import name 'call_http_mcp_tool' from 'activities'`

- [ ] **Step 5.3: Add HTTP imports and `call_http_mcp_tool` to `activities.py`**

Add after the existing imports block (after `from temporalio import activity`):

```python
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
```

Add the new activity after the existing `call_mcp_tool` function:

```python
@activity.defn
async def call_http_mcp_tool(
    url: str,
    transport: str,
    headers: dict[str, Any],
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Call a tool on an HTTP or SSE MCP server and return the text result."""
    logger.info("HTTP MCP tool call: transport=%s url=%s tool=%s", transport, url, tool_name)
    if transport == "http":
        async with streamablehttp_client(url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
    else:  # sse — headers not forwarded per schema contract
        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)

    parts: list[str] = []
    for content in result.content:
        if hasattr(content, "text"):
            parts.append(content.text)
        else:
            parts.append(str(content))
    return "\n".join(parts)
```

- [ ] **Step 5.4: Run tests — expect all pass**

```bash
cd durable-worker && uv run pytest tests/test_activities.py -v
```

Expected: all PASSED

- [ ] **Step 5.5: Commit**

```bash
git add durable-worker/activities.py durable-worker/tests/test_activities.py
git commit -m "feat(durable-worker): add call_http_mcp_tool Temporal activity"
```

---

## Task 6: Workflow Dispatch + Worker Registration + Final Verification

**Files:**
- Modify: `durable-worker/workflows/agent.py`
- Modify: `durable-worker/worker.py`

- [ ] **Step 6.1: Update `workflows/agent.py` — import and dispatch**

Update the `workflow.unsafe.imports_passed_through()` block (currently lines 38–40):

```python
with workflow.unsafe.imports_passed_through():
    from activities import call_llm_step, call_mcp_tool, upload_output
    import agent_config
```

Change to:

```python
with workflow.unsafe.imports_passed_through():
    from activities import call_http_mcp_tool, call_llm_step, call_mcp_tool, upload_output
    import agent_config
```

Update the MCP tool dispatch block inside `AgentWorkflow.run()`. Currently (around line 140):

```python
                        mcp_ref = agent_config.mcp_tool_map.get(tool_name)
                        if mcp_ref:
                            tool_result = await workflow.execute_activity(
                                call_mcp_tool,
                                args=[mcp_ref.command, mcp_ref.args, mcp_ref.env, tool_name, tool_args],
                                start_to_close_timeout=timedelta(seconds=60),
                                retry_policy=_TOOL_RETRY,
                            )
```

Replace with:

```python
                        mcp_ref = agent_config.mcp_tool_map.get(tool_name)
                        if mcp_ref:
                            if isinstance(mcp_ref, agent_config.StdioServerRef):
                                tool_result = await workflow.execute_activity(
                                    call_mcp_tool,
                                    args=[mcp_ref.command, mcp_ref.args, mcp_ref.env, tool_name, tool_args],
                                    start_to_close_timeout=timedelta(seconds=60),
                                    retry_policy=_TOOL_RETRY,
                                )
                            else:  # HttpServerRef
                                tool_result = await workflow.execute_activity(
                                    call_http_mcp_tool,
                                    args=[mcp_ref.url, mcp_ref.transport, mcp_ref.headers, tool_name, tool_args],
                                    start_to_close_timeout=timedelta(seconds=60),
                                    retry_policy=_TOOL_RETRY,
                                )
```

- [ ] **Step 6.2: Register `call_http_mcp_tool` in `worker.py`**

Update the imports line (currently `from activities import call_llm_step, call_mcp_tool, upload_output`):

```python
from activities import call_http_mcp_tool, call_llm_step, call_mcp_tool, upload_output
```

Update the `Worker(...)` call in `main()`:

```python
    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[AgentWorkflow],
        activities=[call_llm_step, call_mcp_tool, call_http_mcp_tool, upload_output],
    )
```

- [ ] **Step 6.3: Run the full test suite**

```bash
cd durable-worker && uv run pytest -v
```

Expected: all PASSED (should include all existing + new tests)

- [ ] **Step 6.4: Run `make check` (lint + type + security)**

```bash
cd durable-worker && make check
```

Expected: no errors. If mypy flags `MCPServerRef` as `valid-type` (union alias), add `# type: ignore[valid-type]` on the `mcp_tool_map` annotation in `agent_config.py` — the comment is already there from the original.

- [ ] **Step 6.5: Commit**

```bash
git add durable-worker/workflows/agent.py durable-worker/worker.py
git commit -m "feat(durable-worker): wire call_http_mcp_tool into workflow dispatch and worker registration"
```

---

## Self-Review Checklist

- [x] **Spec: YAML schema** — no changes needed; handled by parse_agentlet (Task 2)
- [x] **Spec: StdioMCPToolSpec / HttpMCPToolSpec** — Task 1
- [x] **Spec: StdioServerRef / HttpServerRef** — Task 1
- [x] **Spec: parse_agentlet http/sse** — Task 2
- [x] **Spec: header resolution (`${VAR}` + `api_key_env`)** — Task 3
- [x] **Spec: _fetch_mcp_schemas HTTP/SSE branch** — Task 4
- [x] **Spec: call_http_mcp_tool activity** — Task 5
- [x] **Spec: workflow dispatch isinstance** — Task 6
- [x] **Spec: register activity in Worker** — Task 6
- [x] **Spec: error handling — http entry with no url skipped** — Task 2 test + impl
- [x] **Spec: error handling — connection failure skips server** — Task 4 test
- [x] **Spec: SSE headers ignored** — activities.py does not forward headers for sse; test confirms sse_client is called without headers arg
- [x] **Type consistency** — `StdioServerRef` used in workflow isinstance check matches definition in agent_config.py Task 1
