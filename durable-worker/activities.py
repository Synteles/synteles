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

import asyncio
import logging
import os
import re
import zipfile as _zipfile
from typing import Any
from urllib.parse import urlparse

import httpx
import litellm
from mcp import ClientSession, StdioServerParameters
from temporalio.exceptions import ApplicationError
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from temporalio import activity

from manifest import HttpMCPToolSpec, StdioMCPToolSpec
from workflow_config import AgentWorkflowConfig, HttpServerConfig, StdioServerConfig

litellm.drop_params = True  # silently drop params unsupported by the active provider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private helpers (not Temporal activities)
# ---------------------------------------------------------------------------


def _resolve_headers(raw: dict[str, str], api_key_env: str | None) -> dict[str, str]:
    """Resolve ${VAR} placeholders in header values and apply api_key_env if present."""
    resolved: dict[str, str] = {}
    for key, value in raw.items():

        def _replace(m: re.Match) -> str:  # type: ignore[type-arg]
            env_val = os.environ.get(m.group(1), "")
            if not env_val:
                logger.warning("Header placeholder ${%s} has no matching env var", m.group(1))
            return env_val

        resolved[key] = re.sub(r"\$\{([^}]+)\}", _replace, value)

    if api_key_env and "Authorization" not in resolved:
        key_value = os.environ.get(api_key_env, "")
        if key_value:
            resolved["Authorization"] = f"Bearer {key_value}"
        else:
            logger.warning("api_key_env '%s' is set but env var is missing", api_key_env)

    return resolved


async def _fetch_mcp_schemas(
    mcp_tools: list[StdioMCPToolSpec | HttpMCPToolSpec],
) -> tuple[list[dict], dict[str, StdioServerConfig], dict[str, HttpServerConfig]]:  # type: ignore[type-arg]
    """Query each MCP server for its tool list.

    Returns (openai-format tool schemas, tool_name → StdioServerConfig,
    tool_name → HttpServerConfig).
    Servers that fail to connect are skipped with a warning.
    """
    schemas: list[dict] = []  # type: ignore[type-arg]
    stdio_tool_map: dict[str, StdioServerConfig] = {}
    http_tool_map: dict[str, HttpServerConfig] = {}

    for spec in mcp_tools:
        try:
            if isinstance(spec, StdioMCPToolSpec):
                server_params = StdioServerParameters(
                    command=spec.command,
                    args=spec.args,
                    env={**os.environ, **spec.env},
                )
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_list = await session.list_tools()
                        ref = StdioServerConfig(command=spec.command, args=spec.args, env=spec.env)
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
                            stdio_tool_map[tool.name] = ref
            else:  # HttpMCPToolSpec
                resolved_headers = _resolve_headers(spec.headers, spec.api_key_env)
                if spec.transport == "http":
                    ctx = streamablehttp_client(spec.url, headers=resolved_headers)
                    async with ctx as (read, write, _):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            tools_list = await session.list_tools()
                            ref_http = HttpServerConfig(
                                url=spec.url, transport=spec.transport, headers=resolved_headers
                            )
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
                                http_tool_map[tool.name] = ref_http
                else:  # sse
                    async with sse_client(spec.url, headers=resolved_headers) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            tools_list = await session.list_tools()
                            ref_http = HttpServerConfig(
                                url=spec.url, transport=spec.transport, headers=resolved_headers
                            )
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
                                http_tool_map[tool.name] = ref_http
            logger.info("Fetched %d tools from MCP server '%s'", len(tools_list.tools), spec.name)
        except Exception as exc:
            logger.warning("Failed to reach MCP server '%s': %s", spec.name, exc)

    return schemas, stdio_tool_map, http_tool_map


async def _download_input_files(
    input_files: list[dict[str, Any]],
    trusted_netloc: str,
    dest_dir: str = "/tmp/input",
) -> None:
    """Download each input file from its presigned GET URL into dest_dir.

    Only fetches URLs whose host:port matches trusted_netloc (derived from
    SYNTELES_MANIFEST_URL) to prevent SSRF if the manifest were tampered with.
    Redirects are disabled — presigned S3/MinIO URLs never redirect.
    """
    os.makedirs(dest_dir, exist_ok=True)
    async with httpx.AsyncClient(follow_redirects=False, timeout=120) as client:
        for file_info in input_files:
            name: str = file_info.get("name", "")
            url: str = file_info.get("url", "")
            if not name or not url:
                continue
            parsed = urlparse(url)
            if parsed.netloc != trusted_netloc:
                raise ValueError(
                    f"Input file URL host {parsed.netloc!r} does not match "
                    f"expected manifest origin {trusted_netloc!r}"
                )
            safe_name = os.path.basename(name)
            dest_path = os.path.join(dest_dir, safe_name)
            resp = await client.get(url)
            resp.raise_for_status()
            with open(dest_path, "wb") as f:  # noqa: ASYNC230
                f.write(resp.content)
            logger.info("Downloaded input file %r → %s", name, dest_path)


# ---------------------------------------------------------------------------
# Temporal activities
# ---------------------------------------------------------------------------


@activity.defn
async def load_agent_config() -> AgentWorkflowConfig:
    """Read env vars, fetch manifest, download inputs, build AgentWorkflowConfig.

    All config loading is done inside this activity so the result is captured
    in Temporal event history — making replay deterministic (fixes C1).
    """
    from config import EXECUTION_ID, SYNTELES_MANIFEST_URL, SYNTELES_OUTPUT_URL
    from manifest import fetch_manifest, parse_agentlet, resolve_prompt

    if not SYNTELES_MANIFEST_URL:
        raise RuntimeError("SYNTELES_MANIFEST_URL is not set")
    if not EXECUTION_ID:
        raise RuntimeError("EXECUTION_ID is not set")

    activity.heartbeat("fetching manifest")
    manifest = await fetch_manifest(SYNTELES_MANIFEST_URL)

    input_files = manifest.get("input_files") or []
    if input_files:
        trusted_netloc = urlparse(SYNTELES_MANIFEST_URL).netloc
        activity.heartbeat("downloading input files")
        await _download_input_files(input_files, trusted_netloc)

    spec = parse_agentlet(manifest)
    effective_prompt = resolve_prompt(manifest, spec)
    if not effective_prompt:
        raise RuntimeError(
            "No prompt available: provide one at API call time or set a default "
            "prompt in the agentlet YAML."
        )

    activity.heartbeat("fetching MCP schemas")
    tools_schema, stdio_tool_map, http_tool_map = await _fetch_mcp_schemas(spec.mcp_tools)

    output_url = SYNTELES_OUTPUT_URL or manifest.get("output_url", "")

    return AgentWorkflowConfig(
        system_prompt=spec.system_prompt,
        effective_prompt=effective_prompt,
        model=f"{spec.provider}/{spec.model_id}",
        tools_schema=tools_schema,
        output_url=output_url,
        stdio_tool_map=stdio_tool_map,
        http_tool_map=http_tool_map,
    )


@activity.defn
async def call_llm_step(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    model: str,
) -> dict[str, Any]:
    """Call the LLM via LiteLLM and return the assistant message dict.

    Retries are disabled here — the Temporal retry policy on the caller handles them.
    A background task heartbeats every 15s so Temporal can detect dead workers
    and deliver cancellations during long LLM calls (fixes C3).
    """
    logger.info("Calling LLM: model=%s messages=%d tools=%d", model, len(messages), len(tools))

    async def _heartbeat_loop() -> None:
        while True:
            await asyncio.sleep(15)
            activity.heartbeat()

    heartbeat_task = asyncio.ensure_future(_heartbeat_loop())
    try:
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            tools=tools or None,
            tool_choice="auto" if tools else None,
            num_retries=0,
        )
    except (
        litellm.BadRequestError,
        litellm.AuthenticationError,
        litellm.PermissionDeniedError,
    ) as exc:
        raise ApplicationError(str(exc), non_retryable=True) from exc
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            # Re-raise if the outer activity task itself is being cancelled so
            # Temporal receives the cancellation (Python 3.11+ Task.cancelling()).
            if asyncio.current_task().cancelling():
                raise

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
    from mcp import StdioServerParameters
    from mcp.client.stdio import stdio_client as _stdio_client

    server_params = StdioServerParameters(
        command=command,
        args=args,
        env={**os.environ, **env},  # static YAML env overrides; container secrets always present
    )
    logger.info("MCP tool call: server=%s tool=%s", command, tool_name)

    async def _hb() -> None:
        while True:
            await asyncio.sleep(15)
            activity.heartbeat()

    hb_task = asyncio.ensure_future(_hb())
    try:
        async with _stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
    finally:
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise

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

    async def _hb() -> None:
        while True:
            await asyncio.sleep(15)
            activity.heartbeat()

    hb_task = asyncio.ensure_future(_hb())
    try:
        if transport == "http":
            ctx = streamablehttp_client(url, headers=headers)
            async with ctx as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
        else:  # sse
            async with sse_client(url, headers=headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
    finally:
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise

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

    if not os.path.isdir(output_dir):  # noqa: ASYNC240
        logger.info("/tmp/output does not exist — skipping output upload")
        return

    files: list[tuple[str, str]] = []
    for dirpath, _dirs, filenames in os.walk(output_dir):
        for filename in filenames:
            abs_path = os.path.join(dirpath, filename)
            arc_name = os.path.relpath(abs_path, output_dir)  # noqa: ASYNC240
            files.append((abs_path, arc_name))

    if not files:
        logger.info("Output directory is empty — skipping output upload")
        return

    logger.info("Zipping %d output file(s) to %s", len(files), zip_path)
    activity.heartbeat("zipping")
    with _zipfile.ZipFile(zip_path, "w", _zipfile.ZIP_DEFLATED) as zf:
        for abs_path, arc_name in files:
            zf.write(abs_path, arc_name)

    zip_size = os.path.getsize(zip_path)  # noqa: ASYNC240
    logger.info("Uploading output.zip (%d bytes) to presigned URL", zip_size)
    activity.heartbeat("uploading")

    async with httpx.AsyncClient(follow_redirects=False, timeout=120) as client:
        with open(zip_path, "rb") as f:  # noqa: ASYNC230
            resp = await client.put(
                output_url,
                content=f.read(),
                headers={"Content-Type": "application/zip"},
            )

    if resp.status_code not in (200, 204):
        raise RuntimeError(f"Output upload failed with HTTP {resp.status_code}: {resp.text[:200]}")
    logger.info("Output uploaded successfully (HTTP %d)", resp.status_code)
