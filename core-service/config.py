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

"""Centralised environment-variable configuration for core-service."""

import os

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://synteles:synteles@localhost:5432/synteles",
)
PROJECT_NAME: str = os.environ.get("PROJECT_NAME", "")
ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "")
PORTAL_DOMAIN_NAME: str = os.environ.get("PORTAL_DOMAIN_NAME", "")
OIDC_ISSUER_URL: str = os.environ.get("OIDC_ISSUER_URL", "")
OIDC_JWKS_URL: str = os.environ.get("OIDC_JWKS_URL", "")
OIDC_AUDIENCE: str = os.environ.get("OIDC_AUDIENCE", "")
S3_LOGS_BUCKET: str = os.environ.get("S3_LOGS_BUCKET", "")
S3_UPLOADS_BUCKET: str = os.environ.get("S3_UPLOADS_BUCKET", "")
REGION: str = os.environ.get("AWS_REGION", os.environ.get("REGION", "eu-central-1"))

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

KEYCLOAK_ADMIN_URL: str = os.environ.get("KEYCLOAK_ADMIN_URL", "")
KEYCLOAK_REALM: str = os.environ.get("KEYCLOAK_REALM", "synteles")
KEYCLOAK_PROVISIONER_CLIENT_ID: str = os.environ.get("KEYCLOAK_PROVISIONER_CLIENT_ID", "")
KEYCLOAK_PROVISIONER_CLIENT_SECRET: str = os.environ.get("KEYCLOAK_PROVISIONER_CLIENT_SECRET", "")
