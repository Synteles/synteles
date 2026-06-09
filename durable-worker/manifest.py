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

"""Fetch the execution manifest and parse the mandatory agentlet fields."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx
import yaml


@dataclass
class StdioMCPToolSpec:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class HttpMCPToolSpec:
    name: str
    url: str
    transport: Literal["http", "sse"]
    headers: dict[str, str] = field(default_factory=dict)
    api_key_env: str | None = None


MCPToolSpec = StdioMCPToolSpec | HttpMCPToolSpec


@dataclass
class AgentletSpec:
    system_prompt: str
    prompt: str | None  # optional default from YAML; None if not set
    provider: str  # e.g. "azure_ai", "openai", "anthropic"
    model_id: str  # e.g. "gpt-5.3-chat", "gpt-4o"
    mcp_tools: list[StdioMCPToolSpec | HttpMCPToolSpec] = field(default_factory=list)


async def fetch_manifest(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]


def parse_agentlet(manifest: Mapping[str, Any]) -> AgentletSpec:
    """Extract mandatory durable-worker fields from the agentlet YAML in the manifest."""
    yaml_text: str = manifest.get("agentlet_yaml", "")
    config: dict[str, Any] = yaml.safe_load(yaml_text) or {}

    system_prompt: str = config.get("system_prompt", "")
    prompt: str | None = config.get("prompt") or None

    model_cfg: dict[str, Any] = config.get("model") or {}
    provider: str = model_cfg.get("provider", "openai")
    model_id: str = model_cfg.get("model_id", "gpt-4o")

    mcp_tools: list[StdioMCPToolSpec | HttpMCPToolSpec] = []
    for tool in config.get("mcp_tools") or []:
        if tool.get("server") == "stdio" and tool.get("command"):
            mcp_tools.append(
                StdioMCPToolSpec(
                    name=tool["name"],
                    command=tool["command"],
                    args=tool.get("args") or [],
                    env=tool.get("env") or {},
                )
            )

    return AgentletSpec(
        system_prompt=system_prompt,
        prompt=prompt,
        provider=provider,
        model_id=model_id,
        mcp_tools=mcp_tools,
    )


def resolve_prompt(manifest: Mapping[str, Any], spec: AgentletSpec) -> str:
    """Runtime prompt overrides agentlet default; falls back to the YAML default."""
    runtime_prompt: str = manifest.get("prompt") or ""
    return runtime_prompt or spec.prompt or ""
