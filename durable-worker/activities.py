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

"""Temporal activities: LiteLLM completion, MCP stdio tool calls, and output upload."""

from __future__ import annotations

import logging
import os
import zipfile as _zipfile
from typing import Any

import httpx
import litellm
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
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
        env={**os.environ, **env},  # static YAML env overrides; container secrets always present
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


@activity.defn
async def call_http_mcp_tool(
    url: str,
    transport: str,
    headers: dict[str, str],
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Call a named tool on an HTTP or SSE MCP server and return the text result."""
    logger.info("MCP HTTP tool call: url=%s transport=%s tool=%s", url, transport, tool_name)
    if transport == "http":
        ctx = streamablehttp_client(url, headers=headers)
        async with ctx as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
    else:  # sse
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


@activity.defn
async def upload_output(output_url: str) -> None:
    """Zip /tmp/output and PUT to the presigned S3 URL.

    No-op when output_url is empty or /tmp/output has no files.
    Raises on upload failure so Temporal can retry.
    """
    output_dir = "/tmp/output"
    zip_path = "/tmp/output.zip"

    if not output_url:
        logger.info("No output URL — skipping output upload")
        return

    if not os.path.isdir(output_dir):
        logger.info("/tmp/output does not exist — skipping output upload")
        return

    files: list[tuple[str, str]] = []
    for dirpath, _dirs, filenames in os.walk(output_dir):
        for filename in filenames:
            abs_path = os.path.join(dirpath, filename)
            arc_name = os.path.relpath(abs_path, output_dir)
            files.append((abs_path, arc_name))

    if not files:
        logger.info("Output directory is empty — skipping output upload")
        return

    logger.info("Zipping %d output file(s) to %s", len(files), zip_path)
    with _zipfile.ZipFile(zip_path, "w", _zipfile.ZIP_DEFLATED) as zf:
        for abs_path, arc_name in files:
            zf.write(abs_path, arc_name)

    zip_size = os.path.getsize(zip_path)
    logger.info("Uploading output.zip (%d bytes) to presigned URL", zip_size)

    async with httpx.AsyncClient(follow_redirects=False, timeout=120) as client:
        with open(zip_path, "rb") as f:
            resp = await client.put(
                output_url,
                content=f.read(),
                headers={"Content-Type": "application/zip"},
            )

    if resp.status_code not in (200, 204):
        raise RuntimeError(f"Output upload failed with HTTP {resp.status_code}: {resp.text[:200]}")
    logger.info("Output uploaded successfully (HTTP %d)", resp.status_code)
