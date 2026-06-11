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

"""Execution management router."""

from __future__ import annotations

import base64
import logging
import re
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.models import DurableExecStatus, ExecStatus, ExecutionBackend
from synteles_db.repos.executions import ExecutionRepo
from temporalio.service import RPCError

from auth import TokenClaims, trusted_claims, trusted_claims_with_org
from backends import get_backend
from config import OUTPUT_URL_MAX_EXPIRY_SECONDS, S3_LOGS_BUCKET
from db import get_db, get_s3
from monitor import _finalize
from temporal_client import get_temporal_client

router = APIRouter()
logger = logging.getLogger(__name__)


def _encode_offset_token(offset: int) -> str:
    try:
        return base64.urlsafe_b64encode(str(offset).encode()).decode()
    except Exception:
        return ""


def _decode_offset_token(token: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(token.encode()).decode())
    except Exception:
        return 0


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _calc_elapsed(created_at: datetime, completed_at: datetime | None) -> int | None:
    if not completed_at:
        return None
    try:
        return int((completed_at - created_at).total_seconds())
    except Exception:
        return None


def _format_execution(e: Any) -> dict[str, Any]:
    created_at = e.created_at.isoformat() if e.created_at else ""
    completed_at = e.completed_at.isoformat() if e.completed_at else None
    # "stopped" is the DB value for user-initiated termination; expose as "terminated"
    status_value = "terminated" if e.status == ExecStatus.stopped else e.status
    summary: dict[str, Any] = {
        "execution_id": str(e.id),
        "agentlet_id": e.agentlet_name,
        "status": status_value,
        "execution_type": str(e.execution_type),
        "created_at": created_at,
        "completed_at": completed_at,
        "logs_s3_uri": e.logs_s3_uri,
        "prompt": e.prompt or "",
    }
    elapsed = _calc_elapsed(e.created_at, e.completed_at)
    if elapsed is not None:
        summary["elapsed_seconds"] = elapsed
    return summary


class SignalRequest(BaseModel):
    input: str


async def _fetch_last_message(workflow_id: str, *, completed: bool) -> str | None:
    """Fetch last LLM message from a durable workflow.

    Active workflows: query get_last_message.
    Completed workflows: fetch the run() return value, which IS the final answer.
    """
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id)
        if completed:
            result: str = await handle.result(follow_runs=False)
        else:
            result = await handle.query("get_last_message")
        return result or None
    except Exception as exc:
        logger.warning("Failed to fetch last message for workflow %s: %s", workflow_id, exc)
        return None


async def _query_pending_question(workflow_id: str) -> str | None:
    """Query the AgentWorkflow for the question it is waiting on. Returns None on any error."""
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id)
        result: str = await handle.query("get_pending_question")
        return result or None
    except Exception as exc:
        logger.warning("Failed to query pending question for workflow %s: %s", workflow_id, exc)
        return None


async def _deliver_signal(
    execution_id: str, org_id: str, input_text: str, db: AsyncSession
) -> None:
    """Validate the execution, send provide_user_input signal, and optimistically flip status.

    The DB status is updated to running immediately after the Temporal signal is accepted.
    The monitor will confirm on the next poll; no race risk because the guard above requires
    waiting_for_signal and the monitor only flips back if is_input_needed returns True.
    """
    execution = await ExecutionRepo(db).get_by_id(UUID(execution_id))
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    if str(execution.org_id) != org_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this execution")
    if execution.execution_type != ExecutionBackend.durable:
        raise HTTPException(
            status_code=409, detail="Signal is only supported for durable executions"
        )
    if execution.status != DurableExecStatus.waiting_for_signal:
        raise HTTPException(status_code=409, detail="Execution is not waiting for input")
    if not execution.workflow_id:
        raise HTTPException(status_code=409, detail="Execution has no associated workflow")
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(execution.workflow_id)
        # Refresh the output presigned URL before resuming — prevents expiry during long pauses
        try:
            fresh_output_url: str = get_s3().generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": S3_LOGS_BUCKET,
                    "Key": f"executions/{execution_id}/output/output.zip",
                },
                ExpiresIn=OUTPUT_URL_MAX_EXPIRY_SECONDS,
            )
            await handle.signal("update_output_url", args=[fresh_output_url])
        except Exception as url_exc:
            logger.warning(
                "Failed to refresh output URL for execution %s: %s", execution_id, url_exc
            )
        await handle.signal("provide_user_input", args=[input_text])
    except RPCError as exc:
        logger.error("Failed to deliver signal to workflow %s: %s", execution.workflow_id, exc)
        raise HTTPException(status_code=500, detail="Failed to deliver signal to workflow") from exc
    await ExecutionRepo(db).update_status(execution, DurableExecStatus.running)
    await db.commit()

    # Ensure a worker container is alive to pick up the resumed workflow.
    # The container may have exited during the waiting_for_signal pause.
    from worker_restart import ensure_worker_running

    await ensure_worker_running(execution, db)


@router.get("/api/executions")
async def list_executions(
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    agentlet_id: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    created_at_start: Annotated[str | None, Query()] = None,
    created_at_end: Annotated[str | None, Query()] = None,
    completed_at_start: Annotated[str | None, Query()] = None,
    completed_at_end: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    next_token: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    valid_statuses = {s.value for s in ExecStatus} | {s.value for s in DurableExecStatus}
    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(valid_statuses))}",
        )

    org_id = claims.org_id
    offset = _decode_offset_token(next_token) if next_token else 0

    executions = await ExecutionRepo(db).list_by_org(
        UUID(org_id),
        agentlet_name=agentlet_id,
        status=status,
        created_at_start=_parse_dt(created_at_start),
        created_at_end=_parse_dt(created_at_end),
        completed_at_start=_parse_dt(completed_at_start),
        completed_at_end=_parse_dt(completed_at_end),
        limit=limit + 1,
        offset=offset,
    )

    has_more = len(executions) > limit
    page = executions[:limit]
    execution_list = [_format_execution(e) for e in page]

    response_body: dict[str, Any] = {
        "executions": execution_list,
        "count": len(execution_list),
    }
    if has_more:
        response_body["next_token"] = _encode_offset_token(offset + limit)
    return response_body


@router.get("/api/executions/{execution_id}/logs")
async def get_execution_logs(
    execution_id: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: Annotated[str, Query()] = "text",
    download: Annotated[bool, Query()] = False,
) -> Any:
    org_id = claims.org_id
    execution = await ExecutionRepo(db).get_by_id(UUID(execution_id))
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    if str(execution.org_id) != org_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this execution")

    logs_s3_uri = execution.logs_s3_uri
    exec_status = "terminated" if execution.status == ExecStatus.stopped else execution.status

    if not logs_s3_uri:
        if execution.status in (ExecStatus.running, ExecStatus.deploying):
            return {
                "execution_id": execution_id,
                "status": exec_status,
                "logs_available": False,
                "message": f"Execution is {exec_status}. Logs will be available after completion.",
                "created_at": execution.created_at.isoformat(),
            }
        raise HTTPException(status_code=410, detail="Logs are not available for this execution")

    match = re.match(r"s3://([^/]+)/(.+)", logs_s3_uri)
    if not match:
        raise HTTPException(status_code=500, detail="Invalid logs configuration")

    bucket, key = match.groups()
    s3_client = get_s3()
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        logs_content: str = response["Body"].read().decode("utf-8")
    except Exception as exc:
        logger.error("Failed to retrieve logs from S3 %s: %s", logs_s3_uri, exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve logs") from exc

    if format.lower() == "json":
        log_entries = []
        for line in logs_content.strip().split("\n"):
            if not line:
                continue
            m = re.match(r"\[([^\]]+)\]\s+\[([^\]]+)\]\s+(.*)", line)
            if m:
                ts, severity, message = m.groups()
                log_entries.append({"timestamp": ts, "severity": severity, "message": message})
            else:
                log_entries.append({"timestamp": None, "severity": "UNKNOWN", "message": line})

        return {
            "execution_id": execution_id,
            "status": exec_status,
            "logs_available": True,
            "s3_uri": logs_s3_uri,
            "log_size_bytes": len(logs_content.encode("utf-8")),
            "created_at": execution.created_at.isoformat(),
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "logs": log_entries,
        }

    headers: dict[str, str] = {
        "X-Execution-Status": exec_status,
        "X-S3-Uri": logs_s3_uri,
    }
    if download:
        headers["Content-Disposition"] = f'attachment; filename="execution-{execution_id}-logs.txt"'
    return PlainTextResponse(content=logs_content, headers=headers)


@router.get("/api/executions/{execution_id}")
async def get_execution_status(
    execution_id: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    org_id = claims.org_id
    execution = await ExecutionRepo(db).get_by_id(UUID(execution_id))
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    if str(execution.org_id) != org_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this execution")

    exec_status = "terminated" if execution.status == ExecStatus.stopped else execution.status
    completed_at = execution.completed_at.isoformat() if execution.completed_at else None
    response_body: dict[str, Any] = {
        "execution_id": execution_id,
        "agentlet_id": execution.agentlet_name,
        "status": exec_status,
        "logs_s3_uri": execution.logs_s3_uri,
        "created_at": execution.created_at.isoformat(),
        "completed_at": completed_at,
        "prompt": execution.prompt or "",
    }
    elapsed = _calc_elapsed(execution.created_at, execution.completed_at)
    if elapsed is not None:
        response_body["elapsed_seconds"] = elapsed
    if execution.execution_type == ExecutionBackend.durable and execution.workflow_id:
        response_body["workflow_id"] = execution.workflow_id
    if execution.status == DurableExecStatus.waiting_for_signal and execution.workflow_id:
        pending_question = await _query_pending_question(execution.workflow_id)
        if pending_question is not None:
            response_body["pending_question"] = pending_question
    _active_durable = (
        ExecStatus.running,
        ExecStatus.deploying,
        DurableExecStatus.waiting_for_signal,
    )
    if execution.execution_type == ExecutionBackend.durable and execution.workflow_id:
        if execution.status in _active_durable or execution.status == ExecStatus.completed:
            last_message = await _fetch_last_message(
                execution.workflow_id, completed=(execution.status == ExecStatus.completed)
            )
            if last_message is not None:
                response_body["last_message"] = last_message
    return response_body


@router.post("/api/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    org_id = claims.org_id
    execution = await ExecutionRepo(db).get_by_id(UUID(execution_id))
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    if str(execution.org_id) != org_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this execution")

    active_statuses = (
        ExecStatus.deploying,
        ExecStatus.running,
        DurableExecStatus.waiting_for_signal,
    )
    if execution.status in active_statuses:
        await _finalize(
            execution, ExecStatus.stopped, get_backend(ExecutionBackend(execution.execution_type)), db
        )

    completed_at = execution.completed_at.isoformat() if execution.completed_at else None
    status_value = "terminated" if execution.status == ExecStatus.stopped else execution.status
    return {
        "execution_id": execution_id,
        "status": status_value,
        "stopped_at": completed_at,
    }


@router.post("/api/executions/{execution_id}/signal", status_code=202)
async def signal_execution(
    execution_id: str,
    body: SignalRequest,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    assert claims.org_id  # guaranteed by trusted_claims_with_org
    await _deliver_signal(execution_id, claims.org_id, body.input, db)
    return {"execution_id": execution_id, "status": "running"}


@router.post("/api/public/executions/{execution_id}/signal", status_code=202)
async def signal_execution_public(
    execution_id: str,
    body: SignalRequest,
    claims: Annotated[TokenClaims, Depends(trusted_claims)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    org_id = claims.org_id
    if not org_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    await _deliver_signal(execution_id, org_id, body.input, db)
    return {"execution_id": execution_id, "status": "running"}


@router.get("/api/public/executions/{execution_id}")
async def get_public_execution_status(
    execution_id: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    org_id = claims.org_id
    if not org_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    execution = await ExecutionRepo(db).get_by_id(UUID(execution_id))
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    if str(execution.org_id) != org_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this execution")

    exec_status = "terminated" if execution.status == ExecStatus.stopped else execution.status
    completed_at = execution.completed_at.isoformat() if execution.completed_at else None
    response_body: dict[str, Any] = {
        "execution_id": execution_id,
        "agentlet_id": execution.agentlet_name,
        "status": exec_status,
        "logs_s3_uri": execution.logs_s3_uri,
        "created_at": execution.created_at.isoformat(),
        "completed_at": completed_at,
        "prompt": execution.prompt or "",
    }
    elapsed = _calc_elapsed(execution.created_at, execution.completed_at)
    if elapsed is not None:
        response_body["elapsed_seconds"] = elapsed
    if execution.execution_type == ExecutionBackend.durable and execution.workflow_id:
        response_body["workflow_id"] = execution.workflow_id
    if execution.status == DurableExecStatus.waiting_for_signal and execution.workflow_id:
        pending_question = await _query_pending_question(execution.workflow_id)
        if pending_question is not None:
            response_body["pending_question"] = pending_question
    _active_durable = (
        ExecStatus.running,
        ExecStatus.deploying,
        DurableExecStatus.waiting_for_signal,
    )
    if execution.execution_type == ExecutionBackend.durable and execution.workflow_id:
        if execution.status in _active_durable or execution.status == ExecStatus.completed:
            last_message = await _fetch_last_message(
                execution.workflow_id, completed=(execution.status == ExecStatus.completed)
            )
            if last_message is not None:
                response_body["last_message"] = last_message
    return response_body


@router.delete("/api/executions/{execution_id}", status_code=204)
async def delete_execution(
    execution_id: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    org_id = claims.org_id
    execution = await ExecutionRepo(db).get_by_id(UUID(execution_id))
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    if str(execution.org_id) != org_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this execution")

    active_statuses = (
        ExecStatus.deploying,
        ExecStatus.running,
        DurableExecStatus.waiting_for_signal,
    )
    if execution.status in active_statuses:
        await _finalize(
            execution, ExecStatus.stopped, get_backend(ExecutionBackend(execution.execution_type)), db
        )
