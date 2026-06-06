"""Notification activities — update execution status in the platform DB.

Phase 4: stubs that log only. Phase 6 will replace the bodies with an HTTP
call to core-service POST /api/internal/executions/{id}/status when the
signal-bridge endpoint is added.
"""

import logging

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn(name="notify_waiting_for_signal")
async def notify_waiting_for_signal(execution_id: str, question: str) -> None:
    logger.info("[%s] waiting_for_signal — question: %s", execution_id, question)


@activity.defn(name="notify_resumed")
async def notify_resumed(execution_id: str) -> None:
    logger.info("[%s] resumed", execution_id)
