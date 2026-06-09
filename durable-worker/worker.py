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

"""Durable worker entrypoint.

Startup sequence:
  1. Fetch the execution manifest from SYNTELES_MANIFEST_URL.
  2. Parse mandatory agentlet fields: system_prompt, provider/model_id, mcp_tools, prompt.
  3. Resolve the effective prompt (runtime override > YAML default).
  4. Query each MCP server for its tool schemas; populate agent_config.
  5. Connect to Temporal and start polling — LiteLLM handles all model calls.

The Temporal workflow is started by DockerDurableBackend.submit() before this
container launches. Temporal queues the task until the worker registers, so
the ordering is safe: agent_config is fully populated before the first workflow
task is dispatched.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from temporalio.client import Client
from temporalio.worker import Worker

import agent_config
from activities import call_http_mcp_tool, call_llm_step, call_mcp_tool, upload_output
from agent_config import HttpServerRef, StdioServerRef
from config import (
    EXECUTION_ID,
    SYNTELES_MANIFEST_URL,
    SYNTELES_OUTPUT_URL,
    TEMPORAL_ADDRESS,
    TEMPORAL_TASK_QUEUE,
)
from manifest import (
    HttpMCPToolSpec,
    StdioMCPToolSpec,
    fetch_manifest,
    parse_agentlet,
    resolve_prompt,
)
from workflows.agent import AgentWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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
) -> tuple[list[dict], dict[str, StdioServerRef | HttpServerRef]]:  # type: ignore[type-arg]
    """Query each MCP server for its tool list.

    Returns (openai-format tool schemas, tool_name → server ref mapping).
    Servers that fail to connect are skipped with a warning.
    """
    schemas: list[dict] = []  # type: ignore[type-arg]
    tool_map: dict[str, StdioServerRef | HttpServerRef] = {}

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
                        ref: StdioServerRef | HttpServerRef = StdioServerRef(
                            command=spec.command, args=spec.args, env=spec.env
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
                            tool_map[tool.name] = ref
            else:  # HttpMCPToolSpec
                resolved_headers = _resolve_headers(spec.headers, spec.api_key_env)
                if spec.transport == "http":
                    ctx = streamablehttp_client(spec.url, headers=resolved_headers)
                    async with ctx as (read, write, _):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            tools_list = await session.list_tools()
                            ref = HttpServerRef(
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
                                tool_map[tool.name] = ref
                else:  # sse
                    async with sse_client(spec.url) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            tools_list = await session.list_tools()
                            ref = HttpServerRef(
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
                                tool_map[tool.name] = ref
            logger.info("Fetched %d tools from MCP server '%s'", len(tools_list.tools), spec.name)
        except Exception as exc:
            logger.warning("Failed to reach MCP server '%s': %s", spec.name, exc)

    return schemas, tool_map


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
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            logger.info("Downloaded input file %r → %s", name, dest_path)


async def main() -> None:
    if not SYNTELES_MANIFEST_URL:
        raise RuntimeError("SYNTELES_MANIFEST_URL is not set")
    if not TEMPORAL_TASK_QUEUE:
        raise RuntimeError("TEMPORAL_TASK_QUEUE is not set")
    if not EXECUTION_ID:
        raise RuntimeError("EXECUTION_ID is not set")

    logger.info("Fetching manifest for execution %s", EXECUTION_ID)
    manifest = await fetch_manifest(SYNTELES_MANIFEST_URL)

    input_files: list[dict[str, Any]] = manifest.get("input_files") or []
    if input_files:
        trusted_netloc = urlparse(SYNTELES_MANIFEST_URL).netloc
        logger.info("Downloading %d input file(s) to /tmp/input/", len(input_files))
        await _download_input_files(input_files, trusted_netloc)

    spec = parse_agentlet(manifest)

    effective_prompt = resolve_prompt(manifest, spec)
    if not effective_prompt:
        raise RuntimeError(
            "No prompt available: provide one at API call time or set a default "
            "prompt in the agentlet YAML."
        )

    agent_config.system_prompt = spec.system_prompt
    agent_config.effective_prompt = effective_prompt
    agent_config.model = f"{spec.provider}/{spec.model_id}"

    agent_config.tools_schema, agent_config.mcp_tool_map = await _fetch_mcp_schemas(spec.mcp_tools)

    # Env var takes priority — worker_restart.py regenerates it on each container restart
    agent_config.output_url = SYNTELES_OUTPUT_URL or manifest.get("output_url", "")

    logger.info(
        "Config loaded — model=%s mcp_tools=%d prompt=%s",
        agent_config.model,
        len(agent_config.tools_schema),
        effective_prompt[:80] + "..." if len(effective_prompt) > 80 else effective_prompt,
    )

    client = await Client.connect(TEMPORAL_ADDRESS)

    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[AgentWorkflow],
        activities=[call_llm_step, call_mcp_tool, call_http_mcp_tool, upload_output],
    )

    logger.info("Durable worker started on task queue '%s'", TEMPORAL_TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
