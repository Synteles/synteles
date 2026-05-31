# Environment Variable Reference

Complete reference for every environment variable used across the Synteles platform.

Variables marked **Required** have no meaningful default and the service will fail or behave incorrectly without them. Variables marked **Conditional** are required only when a specific feature is enabled. Variables marked **Optional** have safe defaults for local development.

All required variables are set automatically by `install.sh` and `docker-compose.yml` for local development. For production deployments, supply them via your secrets manager or container orchestration environment.

---

## Table of Contents

- [Shared / Root](#shared--root)
- [core-service](#core-service)
- [scheduler-service](#scheduler-service)
- [synte-service](#synte-service)
- [ux-console](#ux-console)
- [PostgreSQL](#postgresql)
- [MinIO](#minio)
- [Keycloak](#keycloak)

---

## Shared / Root

These variables are defined in the root `.env` file and consumed by multiple services.

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_ENCRYPTION_KEY` | **Required** | — | 64-character hex string (32 bytes). Used for AES-256-GCM encryption of user secrets stored in the database. Generate with: `od -vN 32 -An -tx1 /dev/urandom \| tr -d ' \n'` |
| `TAVILY_API_KEY` | Optional | _(empty)_ | Tavily web search API key. When set, injected into agentlet containers at execution time to enable web search tools. |
| `OIDC_CLIENT_SECRET` | **Required** | `synteles-dev-secret` | OIDC client secret for the `synteles-app` Keycloak client. Shared between `ux-console` and the Keycloak provisioner. Change from the default for any non-local deployment. |
| `KEYCLOAK_PROVISIONER_CLIENT_SECRET` | **Required** | `provisioner-dev-secret` | Client secret for the `synteles-provisioner` Keycloak client used by `core-service` to manage users and organizations. Change from the default for any non-local deployment. |

---

## core-service

Python FastAPI service providing the platform REST API.

### Database

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | **Required** | `postgresql+asyncpg://synteles:synteles@localhost:5432/synteles` | AsyncPG PostgreSQL connection string. |
| `SECRET_ENCRYPTION_KEY` | **Required** | — | See [Shared / Root](#shared--root). |

### Authentication (OIDC)

| Variable | Required | Default | Description |
|---|---|---|---|
| `OIDC_ISSUER_URL` | **Required** | — | OIDC issuer URL for JWT validation, e.g. `https://auth.example.com/realms/synteles`. In local dev: `http://localhost:8080/auth/realms/synteles`. |
| `OIDC_JWKS_URL` | **Required** | — | JWKS endpoint used to fetch public keys for JWT signature verification. In local dev: `http://keycloak:9090/auth/realms/synteles/protocol/openid-connect/certs` (container-internal). |
| `OIDC_AUDIENCE` | Optional | _(empty)_ | Expected `aud` claim value. When empty, audience validation is skipped. |
| `KEYCLOAK_ADMIN_URL` | **Required** | — | Keycloak admin API base URL, e.g. `http://keycloak:9090/auth`. Used to provision users and organizations. |
| `KEYCLOAK_REALM` | Optional | `synteles` | Keycloak realm name. |
| `KEYCLOAK_PROVISIONER_CLIENT_ID` | **Required** | — | Client ID for the Keycloak provisioner client, e.g. `synteles-provisioner`. |
| `KEYCLOAK_PROVISIONER_CLIENT_SECRET` | **Required** | — | See [Shared / Root](#shared--root). |

### Storage (S3 / MinIO)

| Variable | Required | Default | Description |
|---|---|---|---|
| `S3_LOGS_BUCKET` | **Required** | — | S3 bucket for execution logs and conversation blobs, e.g. `synteles-logs`. |
| `S3_UPLOADS_BUCKET` | **Required** | — | S3 bucket for user-uploaded input files, e.g. `synteles-uploads`. |
| `S3_ENDPOINT_URL` | Optional | _(AWS)_ | Custom S3 endpoint URL. Set to `http://minio:9000` for local MinIO. When unset, uses AWS S3. |
| `S3_PUBLIC_ENDPOINT_URL` | Optional | _(same as S3_ENDPOINT_URL)_ | Publicly reachable S3 endpoint used when generating presigned download URLs. Set to `http://localhost:9000` in local dev so URLs are accessible from a browser on the host machine. |
| `S3_ACCESS_KEY` | Conditional | — | S3 / MinIO access key. Required when `S3_ENDPOINT_URL` is set. |
| `S3_SECRET_KEY` | Conditional | — | S3 / MinIO secret key. Required when `S3_ENDPOINT_URL` is set. |
| `AWS_REGION` | Optional | `eu-central-1` | AWS region. Also read from `REGION` as a fallback. |

### Networking

| Variable | Required | Default | Description |
|---|---|---|---|
| `PORTAL_DOMAIN_NAME` | Optional | _(empty)_ | Public domain of the portal, e.g. `https://app.synteles.dev`. Used to derive CORS allowed origins when `CORS_ALLOWED_ORIGINS` is not set explicitly. |
| `CORS_ALLOWED_ORIGINS` | Optional | _(derived from PORTAL_DOMAIN_NAME or localhost)_ | Comma-separated list of allowed CORS origins. When empty, defaults to localhost origins in development or the portal domain in production. |

---

## scheduler-service

Python service that schedules and monitors agentlet executions.

### Database

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | **Required** | `postgresql+asyncpg://synteles:synteles@localhost:5432/synteles` | AsyncPG PostgreSQL connection string. |

### Authentication (OIDC)

| Variable | Required | Default | Description |
|---|---|---|---|
| `OIDC_ISSUER_URL` | **Required** | — | See [core-service](#authentication-oidc). |
| `OIDC_JWKS_URL` | **Required** | — | See [core-service](#authentication-oidc). |
| `OIDC_AUDIENCE` | Optional | _(empty)_ | See [core-service](#authentication-oidc). |

### Storage (S3 / MinIO)

| Variable | Required | Default | Description |
|---|---|---|---|
| `S3_LOGS_BUCKET` | **Required** | — | S3 bucket for execution logs, e.g. `synteles-logs`. |
| `S3_UPLOAD_BUCKET` | **Required** | — | S3 bucket for user-uploaded input files, e.g. `synteles-uploads`. Note: singular `UPLOAD` (vs `core-service`'s `UPLOADS`). |
| `S3_ENDPOINT_URL` | Optional | _(AWS)_ | See [core-service](#storage-s3--minio). |
| `S3_ACCESS_KEY` | Conditional | — | See [core-service](#storage-s3--minio). |
| `S3_SECRET_KEY` | Conditional | — | See [core-service](#storage-s3--minio). |
| `AWS_REGION` | Optional | `eu-central-1` | See [core-service](#storage-s3--minio). |

### Execution

| Variable | Required | Default | Description |
|---|---|---|---|
| `EXECUTION_BACKEND` | Optional | `docker` | Execution backend for agentlet containers. Currently only `docker` is supported. |
| `AGENTLET_IMAGE` | Optional | `synteles/agentlet:edge` | Docker image used to spawn agentlet containers. Override to pin a specific tag or use a private registry, e.g. `synteles/agentlet:1.2.3`. |
| `DOCKER_NETWORK` | Optional | _(empty)_ | Docker network name to attach agentlet containers to, e.g. `synteles_default`. When empty, no explicit network is set. Required for containers to reach internal services (MinIO, PostgreSQL). |
| `MONITOR_INTERVAL_SECONDS` | Optional | `30` | How often (in seconds) the scheduler polls running executions for status updates. |
| `TAVILY_API_KEY` | Optional | _(empty)_ | See [Shared / Root](#shared--root). |

### Networking

| Variable | Required | Default | Description |
|---|---|---|---|
| `PORTAL_DOMAIN_NAME` | Optional | _(empty)_ | See [core-service](#networking). |
| `CORS_ALLOWED_ORIGINS` | Optional | _(derived)_ | See [core-service](#networking). |

---

## synte-service

Python service providing the streaming chat agent endpoint.

### Authentication (OIDC)

| Variable | Required | Default | Description |
|---|---|---|---|
| `OIDC_ISSUER_URL` | **Required** | — | See [core-service](#authentication-oidc). |
| `OIDC_JWKS_URL` | **Required** | — | See [core-service](#authentication-oidc). |

### Agent

| Variable | Required | Default | Description |
|---|---|---|---|
| `API_BASE_URL` | Optional | `https://api.synteles.dev/v1` | Base URL for platform API calls made by the agent's tools, e.g. `http://traefik:8080`. |
| `CHAT_MODEL_ID` | Optional | `azure_ai/gpt-5.3-chat` | LiteLLM model string for the chat agent, e.g. `anthropic/claude-sonnet-4-6` or `openai/gpt-4.1`. |
| `OPENAI_API_KEY` | Conditional | _(empty)_ | Required when `CHAT_MODEL_ID` references an OpenAI model. |
| `ANTHROPIC_API_KEY` | Conditional | _(empty)_ | Required when `CHAT_MODEL_ID` references an Anthropic model. |
| `PLATFORM_SECRET_<NAME>` | Conditional | — | Dynamic provider credentials loaded from `config/platform.toml`. One variable per configured secret, where `<NAME>` matches the secret name in uppercase. Value must be a JSON object of key-value credential pairs, e.g. `PLATFORM_SECRET_OPENAI={"OPENAI_API_KEY":"sk-..."}`. |

---

## ux-console

Next.js frontend application.

> All `NEXT_PUBLIC_*` variables are embedded in the client-side bundle at build time and visible in the browser. Do not put secrets in `NEXT_PUBLIC_*` variables.

| Variable | Required | Default | Description |
|---|---|---|---|
| `OIDC_ISSUER_URL` | **Required** | — | Keycloak realm URL used server-side for OIDC discovery, e.g. `https://auth.example.com/realms/synteles`. |
| `OIDC_INTERNAL_BASE` | Optional | _(same as OIDC_ISSUER_URL base)_ | Internal base URL for server-to-server Keycloak requests, e.g. `http://keycloak:9090`. Used inside Docker where `localhost` does not reach Keycloak. |
| `OIDC_PUBLIC_BASE` | Optional | _(same as OIDC_ISSUER_URL base)_ | Public base URL for browser-side Keycloak endpoints, e.g. `http://localhost:8080`. Used to rewrite server-generated URLs so the browser can reach them. |
| `OIDC_CLIENT_ID` | **Required** | — | OIDC client ID registered in Keycloak, e.g. `synteles-app`. |
| `OIDC_CLIENT_SECRET` | **Required** | — | See [Shared / Root](#shared--root). Used server-side only for the token exchange. |
| `API_BASE_URL` | **Required** | — | Base URL of the platform API gateway used by server-side Next.js code, e.g. `http://traefik:8080` inside Docker. |
| `API_PUBLIC_BASE_URL` | Optional | `https://api.synteles.dev` | Publicly reachable API base URL shown in the **API Integration** curl snippets. Read server-side at request time (not baked into the bundle), so it reflects the running environment. Set to `http://localhost:8080` for local dev, `https://api.synteles.dev` for production. |
| `CHAT_STREAM_URL` | **Required** | — | Full URL of the synte-service streaming endpoint, e.g. `http://synte-service:8080/chat/stream`. |
| `REDIRECT_URI` | **Required** | — | OIDC redirect URI registered in Keycloak, e.g. `http://localhost:3000/callback`. Must exactly match the URI configured in the Keycloak client. |

---

## PostgreSQL

Variables for the PostgreSQL Docker service.

| Variable | Required | Default | Description |
|---|---|---|---|
| `POSTGRES_USER` | **Required** | `synteles` | PostgreSQL superuser username. |
| `POSTGRES_PASSWORD` | **Required** | `synteles` | PostgreSQL superuser password. Change for any non-local deployment. |
| `POSTGRES_DB` | **Required** | `synteles` | Default database name. |

---

## MinIO

Variables for the MinIO Docker service (local S3-compatible object storage).

| Variable | Required | Default | Description |
|---|---|---|---|
| `MINIO_ROOT_USER` | **Required** | `minioadmin` | MinIO root username. Matches `S3_ACCESS_KEY` in service configs. Change for any non-local deployment. |
| `MINIO_ROOT_PASSWORD` | **Required** | `minioadmin` | MinIO root password. Matches `S3_SECRET_KEY` in service configs. Change for any non-local deployment. |
| `MINIO_SERVER_URL` | Optional | `http://localhost:9000` | Public MinIO URL advertised to clients. Determines the host embedded in presigned URLs when `S3_PUBLIC_ENDPOINT_URL` is not set separately. |

---

## Keycloak

Variables for Keycloak and its provisioner.

| Variable | Required | Default | Description |
|---|---|---|---|
| `KEYCLOAK_ADMIN_USER` | **Required** | `admin` | Keycloak master realm admin username. |
| `KEYCLOAK_ADMIN_PASSWORD` | **Required** | `admin` | Keycloak master realm admin password. Change for any non-local deployment. |
| `KEYCLOAK_DEFAULT_USER` | Optional | `synteles` | Username of the default **human login** account created in the `synteles` realm on first provisioning. Used for manual browser access after `docker compose up`. Not used by the automated test suite. |
| `KEYCLOAK_DEFAULT_PASSWORD` | Optional | `synteles` | Password for `KEYCLOAK_DEFAULT_USER`. Change for any non-local deployment. |
| `KEYCLOAK_TEST_USER` | Optional | `synteles-test` | Username of the dedicated **integration test** account. The automated test suite authenticates as this user — keeping it separate from `KEYCLOAK_DEFAULT_USER` prevents test runs from polluting the developer's working environment. |
| `KEYCLOAK_TEST_PASSWORD` | Optional | `synteles-test` | Password for `KEYCLOAK_TEST_USER`. Change for any non-local deployment. |
| `KEYCLOAK_FRESH_USER` | Optional | `synteles-fresh` | Base username for **provisioning integration tests**. The test fixture creates a unique `synteles-fresh-{uuid}` Keycloak user per session from this credential so the first-login provisioning path is exercised every run. |
| `KEYCLOAK_FRESH_PASSWORD` | Optional | `synteles-fresh` | Password for `KEYCLOAK_FRESH_USER` (and all derived ephemeral users). |

---

## Production Checklist

Before deploying to a non-local environment, rotate or set all of the following — the defaults are intentionally weak for development convenience:

- `SECRET_ENCRYPTION_KEY` — generate a fresh 32-byte random key
- `OIDC_CLIENT_SECRET` — use a strong random secret, register it in Keycloak
- `KEYCLOAK_PROVISIONER_CLIENT_SECRET` — use a strong random secret
- `KEYCLOAK_ADMIN_PASSWORD` — set a strong admin password
- `KEYCLOAK_DEFAULT_PASSWORD` — set or disable the human login account
- `KEYCLOAK_TEST_PASSWORD` — set a strong password for the test user, or disable the account in production
- `KEYCLOAK_FRESH_PASSWORD` — set or disable the provisioning test base account
- `POSTGRES_PASSWORD` — use a strong database password
- `MINIO_ROOT_PASSWORD` — use a strong MinIO password (or replace with managed S3)
