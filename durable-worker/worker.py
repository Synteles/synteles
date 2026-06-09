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
  1. Validate that TEMPORAL_TASK_QUEUE is set.
  2. Connect to Temporal.
  3. Start the Worker — all config loading happens inside the load_agent_config
     activity so the result is captured in Temporal event history.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from temporalio.client import Client
from temporalio.worker import Worker

from activities import (
    call_http_mcp_tool,
    call_llm_step,
    call_mcp_tool,
    load_agent_config,
    upload_output,
)
from config import TEMPORAL_ADDRESS, TEMPORAL_TASK_QUEUE
from workflows.agent import AgentWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not TEMPORAL_TASK_QUEUE:
        raise RuntimeError("TEMPORAL_TASK_QUEUE is not set")

    client = await Client.connect(TEMPORAL_ADDRESS)

    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[AgentWorkflow],
        activities=[
            load_agent_config,
            call_llm_step,
            call_mcp_tool,
            call_http_mcp_tool,
            upload_output,
        ],
        graceful_shutdown_timeout=timedelta(seconds=300),
        max_concurrent_activities=5,
    )

    logger.info("Durable worker started on task queue '%s'", TEMPORAL_TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
