import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from activities import call_llm_step, execute_tool, record_outcome
from config import TEMPORAL_ADDRESS, TEMPORAL_TASK_QUEUE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Connecting to Temporal at %s", TEMPORAL_ADDRESS)
    client = await Client.connect(TEMPORAL_ADDRESS)

    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        activities=[call_llm_step, execute_tool, record_outcome],
    )

    logger.info("Activity worker started, polling queue '%s'", TEMPORAL_TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
