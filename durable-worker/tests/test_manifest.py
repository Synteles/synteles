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

"""Unit tests for manifest.py — parse_agentlet, resolve_prompt, fetch_manifest."""

from __future__ import annotations

import httpx
import pytest
import respx

from manifest import AgentletSpec, HttpMCPToolSpec, MCPToolSpec, StdioMCPToolSpec, fetch_manifest, parse_agentlet, resolve_prompt

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FULL_YAML = """\
system_prompt: You are a contract reviewer.
prompt: Review the attached contract.
model:
  provider: openai
  model_id: gpt-4o-mini
mcp_tools:
  - name: doc_reader
    server: stdio
    command: python
    args: ["-m", "doc_reader"]
    env:
      SOME_VAR: value
  - name: web_search
    server: stdio
    command: search-server
"""

_MANIFEST_WITH_YAML = {"agentlet_yaml": _FULL_YAML, "prompt": ""}


# ---------------------------------------------------------------------------
# parse_agentlet — field extraction
# ---------------------------------------------------------------------------


def test_parse_agentlet_system_prompt() -> None:
    spec = parse_agentlet(_MANIFEST_WITH_YAML)
    assert spec.system_prompt == "You are a contract reviewer."


def test_parse_agentlet_yaml_default_prompt() -> None:
    spec = parse_agentlet(_MANIFEST_WITH_YAML)
    assert spec.prompt == "Review the attached contract."


def test_parse_agentlet_provider() -> None:
    spec = parse_agentlet(_MANIFEST_WITH_YAML)
    assert spec.provider == "openai"


def test_parse_agentlet_model_id() -> None:
    spec = parse_agentlet(_MANIFEST_WITH_YAML)
    assert spec.model_id == "gpt-4o-mini"


def test_parse_agentlet_mcp_tools_count() -> None:
    spec = parse_agentlet(_MANIFEST_WITH_YAML)
    assert len(spec.mcp_tools) == 2


def test_parse_agentlet_mcp_tool_name() -> None:
    spec = parse_agentlet(_MANIFEST_WITH_YAML)
    assert spec.mcp_tools[0].name == "doc_reader"


def test_parse_agentlet_mcp_tool_command() -> None:
    spec = parse_agentlet(_MANIFEST_WITH_YAML)
    assert spec.mcp_tools[0].command == "python"


def test_parse_agentlet_mcp_tool_args() -> None:
    spec = parse_agentlet(_MANIFEST_WITH_YAML)
    assert spec.mcp_tools[0].args == ["-m", "doc_reader"]


def test_parse_agentlet_mcp_tool_env() -> None:
    spec = parse_agentlet(_MANIFEST_WITH_YAML)
    assert spec.mcp_tools[0].env == {"SOME_VAR": "value"}


def test_parse_agentlet_mcp_tool_no_args_defaults_to_empty_list() -> None:
    spec = parse_agentlet(_MANIFEST_WITH_YAML)
    assert spec.mcp_tools[1].args == []


def test_parse_agentlet_mcp_tool_no_env_defaults_to_empty_dict() -> None:
    spec = parse_agentlet(_MANIFEST_WITH_YAML)
    assert spec.mcp_tools[1].env == {}


def test_parse_agentlet_returns_agentlet_spec() -> None:
    spec = parse_agentlet(_MANIFEST_WITH_YAML)
    assert isinstance(spec, AgentletSpec)


def test_parse_agentlet_mcp_tools_are_mcp_tool_spec() -> None:
    spec = parse_agentlet(_MANIFEST_WITH_YAML)
    assert all(isinstance(t, MCPToolSpec) for t in spec.mcp_tools)


# ---------------------------------------------------------------------------
# parse_agentlet — defaults when fields are absent
# ---------------------------------------------------------------------------


def test_parse_agentlet_empty_yaml_returns_defaults() -> None:
    spec = parse_agentlet({"agentlet_yaml": ""})
    assert spec.system_prompt == ""
    assert spec.prompt is None
    assert spec.provider == "openai"
    assert spec.model_id == "gpt-4o"
    assert spec.mcp_tools == []


def test_parse_agentlet_missing_agentlet_yaml_key() -> None:
    spec = parse_agentlet({})
    assert spec.system_prompt == ""
    assert spec.mcp_tools == []


def test_parse_agentlet_no_model_section_defaults_to_gpt4o() -> None:
    yaml = "system_prompt: Hello"
    spec = parse_agentlet({"agentlet_yaml": yaml})
    assert spec.provider == "openai"
    assert spec.model_id == "gpt-4o"


def test_parse_agentlet_no_prompt_field_is_none() -> None:
    yaml = "system_prompt: Hello"
    spec = parse_agentlet({"agentlet_yaml": yaml})
    assert spec.prompt is None


def test_parse_agentlet_empty_prompt_field_is_none() -> None:
    yaml = "system_prompt: Hello\nprompt: "
    spec = parse_agentlet({"agentlet_yaml": yaml})
    assert spec.prompt is None


def test_parse_agentlet_http_tool_included() -> None:
    yaml = """\
mcp_tools:
  - name: web_search
    server: http
    url: "http://search-mcp:8000/mcp"
"""
    spec = parse_agentlet({"agentlet_yaml": yaml})
    assert len(spec.mcp_tools) == 1
    tool = spec.mcp_tools[0]
    assert isinstance(tool, HttpMCPToolSpec)
    assert tool.name == "web_search"
    assert tool.url == "http://search-mcp:8000/mcp"
    assert tool.transport == "http"


def test_parse_agentlet_sse_tool_included() -> None:
    yaml = """\
mcp_tools:
  - name: crm_tools
    server: sse
    url: "http://crm-mcp:9000/sse"
"""
    spec = parse_agentlet({"agentlet_yaml": yaml})
    assert len(spec.mcp_tools) == 1
    tool = spec.mcp_tools[0]
    assert isinstance(tool, HttpMCPToolSpec)
    assert tool.transport == "sse"


def test_parse_agentlet_http_tool_headers_and_api_key_env() -> None:
    yaml = """\
mcp_tools:
  - name: secured
    server: http
    url: "http://mcp:8000/mcp"
    headers:
      X-Custom: "value"
    api_key_env: MY_API_KEY
"""
    spec = parse_agentlet({"agentlet_yaml": yaml})
    tool = spec.mcp_tools[0]
    assert isinstance(tool, HttpMCPToolSpec)
    assert tool.headers == {"X-Custom": "value"}
    assert tool.api_key_env == "MY_API_KEY"


def test_parse_agentlet_http_tool_without_url_excluded() -> None:
    yaml = """\
mcp_tools:
  - name: no_url
    server: http
  - name: stdio_tool
    server: stdio
    command: my-server
"""
    spec = parse_agentlet({"agentlet_yaml": yaml})
    assert len(spec.mcp_tools) == 1
    assert spec.mcp_tools[0].name == "stdio_tool"


def test_parse_agentlet_mixed_transports() -> None:
    yaml = """\
mcp_tools:
  - name: file_reader
    server: stdio
    command: uvx
    args: ["mcp-file-reader"]
  - name: web_search
    server: http
    url: "http://search-mcp:8000/mcp"
  - name: crm_tools
    server: sse
    url: "http://crm-mcp:9000/sse"
"""
    spec = parse_agentlet({"agentlet_yaml": yaml})
    assert len(spec.mcp_tools) == 3
    assert isinstance(spec.mcp_tools[0], StdioMCPToolSpec)
    assert isinstance(spec.mcp_tools[1], HttpMCPToolSpec)
    assert isinstance(spec.mcp_tools[2], HttpMCPToolSpec)
    assert spec.mcp_tools[1].transport == "http"
    assert spec.mcp_tools[2].transport == "sse"


def test_parse_agentlet_unknown_server_type_excluded() -> None:
    yaml = """\
mcp_tools:
  - name: ws_tool
    server: websocket
    url: "ws://mcp:8000"
  - name: stdio_tool
    server: stdio
    command: my-server
"""
    spec = parse_agentlet({"agentlet_yaml": yaml})
    assert len(spec.mcp_tools) == 1
    assert spec.mcp_tools[0].name == "stdio_tool"


def test_parse_agentlet_stdio_tool_without_command_excluded() -> None:
    yaml = """\
mcp_tools:
  - name: no_cmd
    server: stdio
"""
    spec = parse_agentlet({"agentlet_yaml": yaml})
    assert spec.mcp_tools == []


# ---------------------------------------------------------------------------
# resolve_prompt
# ---------------------------------------------------------------------------


def _make_spec(prompt: str | None = "YAML default") -> AgentletSpec:
    return AgentletSpec(system_prompt="sys", prompt=prompt, provider="openai", model_id="gpt-4o")


def test_resolve_prompt_runtime_overrides_yaml_default() -> None:
    spec = _make_spec("YAML default")
    manifest = {"prompt": "Runtime override"}
    assert resolve_prompt(manifest, spec) == "Runtime override"


def test_resolve_prompt_falls_back_to_yaml_default() -> None:
    spec = _make_spec("YAML default")
    manifest: dict[str, str] = {"prompt": ""}
    assert resolve_prompt(manifest, spec) == "YAML default"


def test_resolve_prompt_no_runtime_no_yaml_returns_empty() -> None:
    spec = _make_spec(None)
    manifest: dict[str, str] = {}
    assert resolve_prompt(manifest, spec) == ""


def test_resolve_prompt_runtime_empty_string_falls_back_to_yaml() -> None:
    spec = _make_spec("YAML default")
    manifest = {"prompt": ""}
    assert resolve_prompt(manifest, spec) == "YAML default"


def test_resolve_prompt_runtime_none_key_absent_falls_back() -> None:
    spec = _make_spec("YAML default")
    manifest: dict[str, object] = {}
    assert resolve_prompt(manifest, spec) == "YAML default"


# ---------------------------------------------------------------------------
# fetch_manifest
# ---------------------------------------------------------------------------


@respx.mock
async def test_fetch_manifest_returns_parsed_json() -> None:
    respx.get("http://example.com/manifest.json").mock(
        return_value=httpx.Response(200, json={"agentlet_yaml": "prompt: hi", "prompt": ""})
    )
    result = await fetch_manifest("http://example.com/manifest.json")
    assert result["agentlet_yaml"] == "prompt: hi"


@respx.mock
async def test_fetch_manifest_raises_on_http_error() -> None:
    respx.get("http://example.com/manifest.json").mock(return_value=httpx.Response(404))
    with pytest.raises(httpx.HTTPStatusError):
        await fetch_manifest("http://example.com/manifest.json")


@respx.mock
async def test_fetch_manifest_raises_on_network_error() -> None:
    respx.get("http://example.com/manifest.json").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    with pytest.raises(httpx.ConnectError):
        await fetch_manifest("http://example.com/manifest.json")
