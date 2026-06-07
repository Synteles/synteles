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

# scheduler-service/config.py
"""Centralised environment-variable configuration for scheduler-service."""

import os

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://synteles:synteles@localhost:5432/synteles",
)
PORTAL_DOMAIN_NAME: str = os.environ.get("PORTAL_DOMAIN_NAME", "")
OIDC_ISSUER_URL: str = os.environ.get("OIDC_ISSUER_URL", "")
OIDC_JWKS_URL: str = os.environ.get("OIDC_JWKS_URL", "")
OIDC_AUDIENCE: str = os.environ.get("OIDC_AUDIENCE", "")
S3_LOGS_BUCKET: str = os.environ.get("S3_LOGS_BUCKET", "")
S3_UPLOAD_BUCKET: str = os.environ.get("S3_UPLOAD_BUCKET", "")
REGION: str = os.environ.get("AWS_REGION", os.environ.get("REGION", "eu-central-1"))
AGENTLET_IMAGE: str = os.environ.get("AGENTLET_IMAGE", "synteles/agentlet:edge")
DOCKER_NETWORK: str = os.environ.get("DOCKER_NETWORK", "")
MONITOR_INTERVAL_SECONDS: int = int(os.environ.get("MONITOR_INTERVAL_SECONDS", "30"))
EXECUTION_BACKEND: str = os.environ.get("EXECUTION_BACKEND", "standard")
EXECUTION_RUNTIME: str = os.environ.get("EXECUTION_RUNTIME", "docker")
TEMPORAL_ADDRESS: str = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
AGENT_WORKER_IMAGE: str = os.environ.get("AGENT_WORKER_IMAGE", "synteles/durable-agentlet:edge")
TAVILY_API_KEY: str = os.environ.get("TAVILY_API_KEY", "")
SIGNAL_WAIT_TIMEOUT_SECONDS: int = int(
    os.environ.get("SIGNAL_WAIT_TIMEOUT_SECONDS", str(24 * 3600))
)

_cors_env: str = os.environ.get("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOWED_ORIGINS: list[str] = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else (
        [f"https://{PORTAL_DOMAIN_NAME}"]
        if PORTAL_DOMAIN_NAME
        else ["http://localhost:8501", "http://localhost:3000"]
    )
)
