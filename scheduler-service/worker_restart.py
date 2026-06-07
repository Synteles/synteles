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

"""Worker container restart for durable executions.

Used by two callers:
  - The monitor: auto-restart when Temporal workflow is RUNNING but the
    agent-worker container has exited (e.g. OOM, crash).
  - Signal delivery: ensure a live worker exists before resuming a workflow
    that was paused at waiting_for_signal (container may have exited during
    the wait).
"""

from __future__ import annotations

import logging

import yaml
from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.models import Execution
from synteles_db.repos.agentlets import AgentletRepo

from backends.docker_durable import DockerDurableBackend, _container_name
from config import AGENT_WORKER_IMAGE, S3_LOGS_BUCKET, TAVILY_API_KEY, TEMPORAL_ADDRESS
from db import get_s3
from routers.execute import _fetch_platform_model_secret, _fetch_user_secrets

logger = logging.getLogger(__name__)

_MANIFEST_PRESIGN_TTL = 3600  # 1 hour — enough for the restarted worker to boot and fetch


async def _assemble_env(execution: Execution, db: AsyncSession) -> dict[str, str]:
    """Reconstruct the container env vars for a durable worker restart.

    Regenerates a fresh presigned GET URL for the existing manifest already in
    S3 (no re-upload needed) and re-fetches secrets from the DB.
    """
    env_vars: dict[str, str] = {}

    agentlet = await AgentletRepo(db).get_by_org_and_name(execution.org_id, execution.agentlet_name)
    if agentlet and agentlet.yaml_definition:
        try:
            agentlet_config = yaml.safe_load(agentlet.yaml_definition) or {}
            yaml_secrets: list[str] = [str(s) for s in (agentlet_config.get("secrets") or [])]

            if "default" in yaml_secrets:
                model_cfg = agentlet_config.get("model") or {}
                provider: str = model_cfg.get("provider", "")
                model_id: str = model_cfg.get("model_id", "")
                if provider and model_id:
                    env_vars.update(_fetch_platform_model_secret(provider, model_id))

            named_secrets = [s for s in yaml_secrets if s != "default"]
            env_vars.update(
                await _fetch_user_secrets(
                    str(execution.org_id), str(execution.user_id), named_secrets, db
                )
            )
        except yaml.YAMLError as exc:
            logger.warning("Could not parse agentlet YAML for worker restart: %s", exc)

    if TAVILY_API_KEY:
        env_vars["TAVILY_API_KEY"] = TAVILY_API_KEY

    execution_id = str(execution.id)
    manifest_key = f"executions/{execution_id}/manifest.json"
    try:
        manifest_url: str = get_s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_LOGS_BUCKET, "Key": manifest_key},
            ExpiresIn=_MANIFEST_PRESIGN_TTL,
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to generate presigned manifest URL: {exc}") from exc

    env_vars["SYNTELES_EXEC_ID"] = execution_id
    env_vars["SYNTELES_MANIFEST_URL"] = manifest_url

    return env_vars


async def ensure_worker_running(execution: Execution, db: AsyncSession) -> bool:
    """Start or restart the agent-worker container if it is not currently running.

    Returns True if a (re)start was triggered, False if the container was
    already alive and no action was taken.
    """
    execution_id = str(execution.id)
    backend = DockerDurableBackend()

    if backend.container_alive(execution_id):
        return False

    logger.info("Agent-worker for execution %s is not running — restarting", execution_id)

    try:
        env = await _assemble_env(execution, db)
    except Exception as exc:
        logger.error(
            "Cannot restart agent-worker for %s: failed to assemble env: %s", execution_id, exc
        )
        return False

    task_queue = f"synteles-agent-{execution_id}"
    container_env = {
        "TEMPORAL_ADDRESS": TEMPORAL_ADDRESS,
        "TEMPORAL_TASK_QUEUE": task_queue,
        "EXECUTION_ID": execution_id,
        **env,
    }

    cname = _container_name(execution_id)
    backend._runtime.stop_container(cname)  # no-op if already gone
    try:
        backend._runtime.run_container(AGENT_WORKER_IMAGE, cname, container_env)
        logger.info("Restarted agent-worker container %s", cname)
        return True
    except Exception as exc:
        logger.error("Failed to start agent-worker container %s: %s", cname, exc)
        return False
