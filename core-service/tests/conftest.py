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

"""Set env vars before any module-level imports are triggered by test collection."""

import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost/test"
os.environ["PROJECT_NAME"] = "test"
os.environ["ENVIRONMENT"] = "test"
os.environ["PORTAL_DOMAIN_NAME"] = "test.synteles.dev"
os.environ["OIDC_ISSUER_URL"] = ""
os.environ["OIDC_AUDIENCE"] = ""
os.environ["S3_LOGS_BUCKET"] = "test-logs"
os.environ["S3_UPLOADS_BUCKET"] = "test-uploads"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["CORS_ALLOWED_ORIGINS"] = "http://localhost"
os.environ["SECRET_ENCRYPTION_KEY"] = "deadbeef" * 8
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["KEYCLOAK_ADMIN_URL"] = ""
os.environ["KEYCLOAK_PROVISIONER_CLIENT_ID"] = ""
os.environ["KEYCLOAK_PROVISIONER_CLIENT_SECRET"] = ""
