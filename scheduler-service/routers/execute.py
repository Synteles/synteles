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

"""Execution submit router."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

import yaml
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.crypto import decrypt
from synteles_db.models import DurableExecStatus, ExecutionType, StandardExecStatus
from synteles_db.repos.agentlets import AgentletRepo
from synteles_db.repos.executions import ExecutionRepo
from synteles_db.repos.secrets import SecretRepo

from auth import TokenClaims, trusted_claims, trusted_claims_with_org
from db import get_db, get_s3

router = APIRouter()
logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_MAX_INPUT_FILES = 20
_INPUT_URL_EXPIRY_SECONDS = 3600
_OUTPUT_URL_MAX_EXPIRY_SECONDS = 43200
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

_PLATFORM_SECRET_SENTINEL = "default"  # nosec B105 — sentinel string, not a password
_PLATFORM_MODELS: dict[tuple[str, str], str] = {}


def _load_platform_models() -> None:
    global _PLATFORM_MODELS
    import tomllib
    from pathlib import Path

    needle = Path("config") / "platform.toml"
    config_path: Path | None = None
    for parent in Path(__file__).resolve().parents:
        candidate = parent / needle
        if candidate.exists():
            config_path = candidate
            break
    if config_path is None:
        logger.warning("platform.toml not found — platform models disabled")
        return
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        for entry in config.get("model", []):
            _PLATFORM_MODELS[(entry["provider"], entry["model_id"])] = entry["secret_name"]
    except Exception as exc:
        logger.warning("Failed to load platform.toml: %s", exc)


_load_platform_models()


def _file_type(name: str) -> str:
    return "image" if os.path.splitext(name)[1].lower() in _IMAGE_EXTENSIONS else "document"


def _fetch_platform_model_secret(provider: str, model_id: str) -> dict[str, str]:
    secret_name = _PLATFORM_MODELS.get((provider, model_id))
    if not secret_name:
        logger.warning(
            "No platform default configured for provider='%s' model_id='%s'", provider, model_id
        )
        return {}
    env_key = f"PLATFORM_SECRET_{secret_name.upper().replace('-', '_').replace(' ', '_')}"
    raw = os.environ.get(env_key, "")
    if not raw:
        logger.warning("A required platform model secret env var is not set")
        return {}
    try:
        secret_value = json.loads(raw)
        return {k: v for k, v in secret_value.items() if isinstance(k, str) and isinstance(v, str)}
    except Exception:
        logger.warning("Failed to parse a platform model secret (malformed JSON)")
        return {}


async def _fetch_user_secrets(
    org_id: str, user_id: str, secret_names: list[str], db: AsyncSession
) -> dict[str, str]:
    """Fetch named user secrets from PostgreSQL and return merged env var dict."""
    if not secret_names:
        return {}
    env_vars: dict[str, str] = {}
    try:
        secrets = await SecretRepo(db).list_by_user_names(UUID(user_id), secret_names)
        for secret in secrets:
            try:
                value = decrypt(secret.nonce, secret.encrypted_value)
                if isinstance(value, dict):
                    env_vars.update(
                        {
                            k: v
                            for k, v in value.items()
                            if isinstance(k, str) and isinstance(v, str)
                        }
                    )
            except Exception as exc:
                logger.warning("Could not decrypt user secret '%s': %s", secret.name, exc)
    except Exception as exc:
        logger.warning("Could not list user secrets for %s: %s", user_id, exc)
    return env_vars


def _copy_input_files(
    s3_client: Any, input_objects: list[str], execution_id: str
) -> list[dict[str, str]]:
    if not input_objects:
        return []

    from config import S3_LOGS_BUCKET, S3_UPLOAD_BUCKET

    result: list[dict[str, str]] = []
    for s3_uri in input_objects:
        expected_prefix = f"s3://{S3_UPLOAD_BUCKET}/"
        if not s3_uri.startswith(expected_prefix):
            raise RuntimeError(f"Invalid input file URI (wrong bucket): {s3_uri!r}")

        key = s3_uri[len(expected_prefix) :]
        parts = key.split("/", 1)
        if len(parts) != 2:
            raise RuntimeError(f"Invalid input file URI (expected upload_id/filename): {s3_uri!r}")

        upload_id, file_name = parts
        if not _UUID_RE.match(upload_id):
            raise RuntimeError(f"Invalid upload_id in URI: {s3_uri!r}")
        if not file_name or "/" in file_name or "\\" in file_name or file_name.startswith("."):
            raise RuntimeError(f"Invalid file name in URI: {s3_uri!r}")

        dest_key = f"executions/{execution_id}/input/{file_name}"
        try:
            s3_client.copy_object(
                CopySource={"Bucket": S3_UPLOAD_BUCKET, "Key": key},
                Bucket=S3_LOGS_BUCKET,
                Key=dest_key,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to copy {s3_uri!r} to execution bucket: {exc}") from exc

        try:
            presigned_url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": S3_LOGS_BUCKET, "Key": dest_key},
                ExpiresIn=_INPUT_URL_EXPIRY_SECONDS,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to generate presigned GET URL for {dest_key!r}: {exc}"
            ) from exc

        result.append({"name": file_name, "url": presigned_url, "type": _file_type(file_name)})
        logger.info("Copied input file: %r → s3://%s/%s", s3_uri, S3_LOGS_BUCKET, dest_key)

    return result


def _generate_output_presigned_url(s3_client: Any, execution_id: str, timeout: int) -> str:
    from config import S3_LOGS_BUCKET

    expiry = min(timeout, _OUTPUT_URL_MAX_EXPIRY_SECONDS)
    output_key = f"executions/{execution_id}/output/output.zip"
    try:
        return str(
            s3_client.generate_presigned_url(
                "put_object",
                Params={"Bucket": S3_LOGS_BUCKET, "Key": output_key},
                ExpiresIn=expiry,
            )
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to generate presigned PUT URL for output.zip: {exc}") from exc


def _upload_execution_manifest(
    s3_client: Any,
    execution_id: str,
    agentlet_yaml: str,
    input_files: list[dict[str, Any]],
    output_url: str,
    prompt: str,
    timeout: int,
) -> str:
    from config import S3_LOGS_BUCKET

    manifest = {
        "agentlet_yaml": agentlet_yaml,
        "input_files": input_files,
        "output_url": output_url,
        "prompt": prompt,
        "timeout": max(1, timeout - 60),
    }
    key = f"executions/{execution_id}/manifest.json"
    try:
        s3_client.put_object(
            Bucket=S3_LOGS_BUCKET,
            Key=key,
            Body=json.dumps(manifest).encode("utf-8"),
            ContentType="application/json",
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to upload execution manifest to S3: {exc}") from exc

    expiry = min(timeout, _OUTPUT_URL_MAX_EXPIRY_SECONDS)
    try:
        return str(
            s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": S3_LOGS_BUCKET, "Key": key},
                ExpiresIn=expiry,
            )
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to generate presigned GET URL for execution manifest: {exc}"
        ) from exc


def _resolve_execution_type(agentlet: Any) -> ExecutionType:
    """Return ExecutionType from the agentlet's execution_backend DB column."""
    return agentlet.execution_backend


async def _run_execution(
    *,
    agentlet_name: str,
    org_id: str,
    user_id: str,
    prompt: str,
    timeout_seconds: int,
    input_objects: list[str],
    db: AsyncSession,
) -> dict[str, Any]:
    if not isinstance(input_objects, list):
        raise HTTPException(status_code=400, detail="'input_objects' must be a list")
    if len(input_objects) > _MAX_INPUT_FILES:
        raise HTTPException(
            status_code=400, detail=f"Too many input files. Maximum {_MAX_INPUT_FILES} allowed."
        )
    if not all(isinstance(u, str) for u in input_objects):
        raise HTTPException(status_code=400, detail="'input_objects' must be a list of strings")
    if not isinstance(timeout_seconds, int) or timeout_seconds < 1 or timeout_seconds > 86400:
        raise HTTPException(status_code=400, detail="timeout must be between 1 and 86400 seconds")

    agentlet = await AgentletRepo(db).get_by_org_and_name(UUID(org_id), agentlet_name)
    if not agentlet:
        raise HTTPException(status_code=404, detail="Agentlet not found")

    execution_type = _resolve_execution_type(agentlet)
    init_status: StandardExecStatus | DurableExecStatus = (
        DurableExecStatus.deploying
        if execution_type == ExecutionType.durable
        else StandardExecStatus.deploying
    )
    fail_status: StandardExecStatus | DurableExecStatus = (
        DurableExecStatus.failed
        if execution_type == ExecutionType.durable
        else StandardExecStatus.failed
    )

    now = datetime.now(UTC)
    timeout_at = now + timedelta(seconds=timeout_seconds)

    execution = await ExecutionRepo(db).create(
        org_id=UUID(org_id),
        user_id=UUID(user_id),
        agentlet_id=agentlet.id,
        agentlet_name=agentlet.name,
        status=init_status,
        timeout_at=timeout_at,
        prompt=prompt or "",
        execution_type=execution_type,
    )
    await db.commit()

    execution_id = str(execution.id)
    s3_client = get_s3()

    if input_objects:
        try:
            copied_files = _copy_input_files(s3_client, input_objects, execution_id)
        except Exception as exc:
            logger.error("Input file copy failed for execution %s: %s", execution_id, exc)
            await ExecutionRepo(db).update_status(
                execution, fail_status, error=f"Input file copy failed: {exc}"
            )
            await db.commit()
            raise HTTPException(
                status_code=500, detail=f"Failed to copy input files: {exc}"
            ) from exc
    else:
        copied_files = []

    try:
        output_presigned_url = _generate_output_presigned_url(
            s3_client, execution_id, timeout_seconds
        )
    except Exception as exc:
        logger.error("Failed to generate output presigned URL for %s: %s", execution_id, exc)
        raise HTTPException(status_code=500, detail="Failed to generate output URL") from exc

    agentlet_yaml = agentlet.yaml_definition or ""
    env_vars: dict[str, str] = {}
    yaml_secrets: list[Any] = []

    try:
        agentlet_config = yaml.safe_load(agentlet_yaml) or {}
        yaml_secrets = agentlet_config.get("secrets") or []
        if _PLATFORM_SECRET_SENTINEL in yaml_secrets:
            models_to_fetch: set[tuple[str, str]] = set()
            model_config = agentlet_config.get("model") or {}
            orch_provider = model_config.get("provider", "")
            orch_model_id = model_config.get("model_id", "")
            if orch_provider and orch_model_id:
                models_to_fetch.add((orch_provider, orch_model_id))
            for sub in agentlet_config.get("sub_agentlets") or []:
                if isinstance(sub, dict):
                    sub_model = sub.get("model") or {}
                    sub_provider = sub_model.get("provider", "")
                    sub_model_id = sub_model.get("model_id", "")
                    if sub_provider and sub_model_id:
                        models_to_fetch.add((sub_provider, sub_model_id))
            for provider, model_id in models_to_fetch:
                platform_creds = _fetch_platform_model_secret(provider, model_id)
                env_vars.update(platform_creds)
                if platform_creds:
                    logger.info("Loaded platform credentials for %s/%s", provider, model_id)
    except yaml.YAMLError as exc:
        logger.warning("Could not parse agentlet YAML to check for default secret: %s", exc)

    named_secrets = [s for s in yaml_secrets if s != _PLATFORM_SECRET_SENTINEL]
    env_vars.update(await _fetch_user_secrets(org_id, user_id, named_secrets, db))
    env_vars.pop("TAVILY_API_KEY", None)  # prevent user secrets from overriding platform key
    from config import TAVILY_API_KEY

    if TAVILY_API_KEY:
        env_vars["TAVILY_API_KEY"] = TAVILY_API_KEY

    try:
        manifest_url = _upload_execution_manifest(
            s3_client,
            execution_id,
            agentlet_yaml,
            copied_files,
            output_presigned_url,
            prompt,
            timeout_seconds,
        )
    except Exception as exc:
        logger.error("Failed to upload execution manifest for %s: %s", execution_id, exc)
        raise HTTPException(status_code=500, detail="Failed to upload execution manifest") from exc

    env_vars["SYNTELES_EXEC_ID"] = execution_id
    env_vars["SYNTELES_MANIFEST_URL"] = manifest_url

    from backends import get_backend
    from backends.base import ExecutionConfig
    from config import AGENTLET_IMAGE

    backend = get_backend(execution_type)
    config = ExecutionConfig(
        execution_id=execution_id,
        image=AGENTLET_IMAGE,
        env=env_vars,
        timeout_seconds=timeout_seconds,
    )
    run_status: StandardExecStatus | DurableExecStatus = (
        DurableExecStatus.running
        if execution_type == ExecutionType.durable
        else StandardExecStatus.running
    )
    try:
        job_ref = await backend.submit(config)
    except Exception as exc:
        await ExecutionRepo(db).update_status(execution, fail_status, error=str(exc))
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Execution deployment failed: {exc}") from exc

    durable_workflow_id: str | None = None
    if execution_type == ExecutionType.durable:
        from backends.docker_durable import _workflow_id

        durable_workflow_id = _workflow_id(job_ref)
    await ExecutionRepo(db).update_job_ref(
        execution, job_ref, run_status, workflow_id=durable_workflow_id
    )
    await db.commit()

    return {
        "execution_id": execution_id,
        "status": "running",
        "agentlet_id": agentlet_name,
        "created_at": execution.created_at.isoformat(),
    }


class ExecuteRequest(BaseModel):
    agentlet_id: str | None = None
    prompt: str = ""
    timeout: int = 3600
    input_objects: list[str] = []
    org_id: str | None = None


class PublicExecuteRequest(BaseModel):
    prompt: str = ""
    timeout: int = 3600
    input_objects: list[str] = []


@router.post("/api/executions", status_code=202)
async def execute_agentlet(
    body: ExecuteRequest,
    claims: Annotated[TokenClaims, Depends(trusted_claims_with_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    if not body.agentlet_id:
        raise HTTPException(status_code=400, detail="agentlet_id is required")

    org_id = claims.org_id
    assert org_id  # guaranteed by trusted_claims_with_org

    if body.org_id and body.org_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this organization")

    return await _run_execution(
        agentlet_name=body.agentlet_id,
        org_id=org_id,
        user_id=claims.user_id,
        prompt=body.prompt,
        timeout_seconds=body.timeout,
        input_objects=body.input_objects,
        db=db,
    )


@router.post("/api/public/agentlets/{agentlet_id}/executions", status_code=202)
async def execute_agentlet_public(
    agentlet_id: str,
    claims: Annotated[TokenClaims, Depends(trusted_claims)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[PublicExecuteRequest | None, Body()] = None,
) -> dict[str, Any]:
    body = body or PublicExecuteRequest()
    if not agentlet_id:
        raise HTTPException(status_code=400, detail="agentlet_id is required")

    org_id = claims.org_id
    if not org_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    agentlet = await AgentletRepo(db).get_by_org_and_name(UUID(org_id), agentlet_id)
    if not agentlet:
        raise HTTPException(status_code=404, detail="Agentlet not found")
    if agentlet.user_id and str(agentlet.user_id) != claims.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this agentlet")

    return await _run_execution(
        agentlet_name=agentlet_id,
        org_id=org_id,
        user_id=claims.user_id,
        prompt=body.prompt,
        timeout_seconds=body.timeout,
        input_objects=body.input_objects,
        db=db,
    )
