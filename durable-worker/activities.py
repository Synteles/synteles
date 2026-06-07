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

"""Temporal activities: LiteLLM completion and MCP stdio tool calls."""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm
from temporalio import activity

litellm.drop_params = True  # silently drop params unsupported by the active provider

logger = logging.getLogger(__name__)


@activity.defn
async def call_llm_step(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    model: str,
) -> dict[str, Any]:
    """Call the LLM via LiteLLM and return the assistant message dict.

    Retries are disabled here — the Temporal retry policy on the caller handles them.
    """
    logger.info("Calling LLM: model=%s messages=%d tools=%d", model, len(messages), len(tools))
    response = await litellm.acompletion(
        model=model,
        messages=messages,
        tools=tools or None,
        tool_choice="auto" if tools else None,
        num_retries=0,
    )
    msg = response.choices[0].message
    tool_calls = None
    if msg.tool_calls:
        tool_calls = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
    return {"role": "assistant", "content": msg.content, "tool_calls": tool_calls}


@activity.defn
async def call_mcp_tool(
    command: str,
    args: list[str],
    env: dict[str, str],
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Start an MCP stdio server, call the named tool, and return the text result."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(
        command=command,
        args=args,
        env=env or None,
    )
    logger.info("MCP tool call: server=%s tool=%s", command, tool_name)
    async with stdio_client(server_params) as (read, write):
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
