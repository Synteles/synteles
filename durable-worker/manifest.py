"""Fetch the execution manifest and parse the mandatory agentlet fields."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx
import yaml


@dataclass
class MCPToolSpec:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentletSpec:
    system_prompt: str
    prompt: str | None  # optional default from YAML; None if not set
    model_id: str  # e.g. "gpt-4o"
    mcp_tools: list[MCPToolSpec] = field(default_factory=list)


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
    model_id: str = model_cfg.get("model_id", "gpt-4o")

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

    return AgentletSpec(
        system_prompt=system_prompt,
        prompt=prompt,
        model_id=model_id,
        mcp_tools=mcp_tools,
    )


def resolve_prompt(manifest: Mapping[str, Any], spec: AgentletSpec) -> str:
    """Runtime prompt overrides agentlet default; falls back to the YAML default.

    Mirrors the logic in the standard agentlet entrypoint.sh + override_config():
    if the caller supplied a non-empty prompt it takes precedence, otherwise the
    agentlet's own default prompt is used.
    """
    runtime_prompt: str = manifest.get("prompt") or ""
    return runtime_prompt or spec.prompt or ""
