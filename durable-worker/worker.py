"""Durable worker entrypoint.

Startup sequence:
  1. Fetch the execution manifest from SYNTELES_MANIFEST_URL.
  2. Parse mandatory agentlet fields: system_prompt, mcp_tools, default prompt.
  3. Resolve the effective prompt (runtime override > YAML default).
  4. Populate agent_config so AgentWorkflow can read it deterministically.
  5. Build StatelessMCPServerProvider instances for each stdio MCP tool.
  6. Connect to Temporal with OpenAIAgentsPlugin and start polling.

The Temporal workflow is started by DockerDurableBackend.submit() before this
container launches. Temporal queues the task until the worker registers, so
the ordering is safe: agent_config is fully populated before the first workflow
task is dispatched.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta

from agents.mcp import MCPServerStdio
from temporalio.client import Client
from temporalio.contrib.openai_agents import (
    ModelActivityParameters,
    OpenAIAgentsPlugin,
    StatelessMCPServerProvider,
)
from temporalio.worker import Worker

import agent_config
from activities.notify import notify_resumed, notify_waiting_for_signal
from config import (
    EXECUTION_ID,
    OPENAI_MODEL,
    SYNTELES_MANIFEST_URL,
    TEMPORAL_ADDRESS,
    TEMPORAL_TASK_QUEUE,
)
from manifest import MCPToolSpec, fetch_manifest, parse_agentlet, resolve_prompt
from workflows.agent import AgentWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _make_stdio_factory(tool: MCPToolSpec) -> Callable[[], MCPServerStdio]:
    """Return a factory closure for a single stdio MCP server.

    The closure captures `tool` by value so each provider gets its own config.
    """

    def factory() -> MCPServerStdio:
        return MCPServerStdio(
            name=tool.name,
            params={"command": tool.command, "args": tool.args},
            cache_tools_list=True,
        )

    return factory


async def main() -> None:
    if not SYNTELES_MANIFEST_URL:
        raise RuntimeError("SYNTELES_MANIFEST_URL is not set")
    if not TEMPORAL_TASK_QUEUE:
        raise RuntimeError("TEMPORAL_TASK_QUEUE is not set")
    if not EXECUTION_ID:
        raise RuntimeError("EXECUTION_ID is not set")

    logger.info("Fetching manifest for execution %s", EXECUTION_ID)
    manifest = await fetch_manifest(SYNTELES_MANIFEST_URL)
    spec = parse_agentlet(manifest)

    effective_prompt = resolve_prompt(manifest, spec)
    if not effective_prompt:
        raise RuntimeError(
            "No prompt available: provide one at API call time or set a default "
            "prompt in the agentlet YAML."
        )

    # Populate module-level config read by AgentWorkflow.
    agent_config.system_prompt = spec.system_prompt
    agent_config.effective_prompt = effective_prompt
    agent_config.mcp_server_names = [t.name for t in spec.mcp_tools]
    agent_config.model = OPENAI_MODEL or spec.model_id

    logger.info(
        "Config loaded — model=%s mcp_tools=%d prompt=%s",
        agent_config.model,
        len(spec.mcp_tools),
        effective_prompt[:80] + "..." if len(effective_prompt) > 80 else effective_prompt,
    )

    mcp_providers = [
        StatelessMCPServerProvider(
            name=tool.name,
            server_factory=_make_stdio_factory(tool),
        )
        for tool in spec.mcp_tools
    ]

    plugin = OpenAIAgentsPlugin(
        model_params=ModelActivityParameters(
            start_to_close_timeout=timedelta(seconds=120),
        ),
        mcp_server_providers=mcp_providers,
    )

    client = await Client.connect(TEMPORAL_ADDRESS, plugins=[plugin])

    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[AgentWorkflow],
        activities=[notify_waiting_for_signal, notify_resumed],
    )

    logger.info("Durable worker started on task queue '%s'", TEMPORAL_TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
