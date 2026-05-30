# Synteles Platform API Contracts

## Table of Contents
- [Overview](#overview)
- [Base URL](#base-url)
- [Authentication](#authentication)
  - [OIDC Bearer Token](#oidc-bearer-token)
  - [API Key Authentication](#api-key-authentication)
- [Common Patterns](#common-patterns)
- [Error Responses](#error-responses)
- [API Endpoints](#api-endpoints)
  - [Auth Endpoints](#auth-endpoints)
  - [User Endpoints](#user-endpoints)
  - [Organization Endpoints](#organization-endpoints)
  - [Agentlet Endpoints](#agentlet-endpoints)
  - [API Key Management Endpoints](#api-key-management-endpoints)
  - [Secrets Endpoints](#secrets-endpoints)
  - [Public Agentlet Endpoints](#public-agentlet-endpoints)
  - [Execution/Scheduler Endpoints](#executionscheduler-endpoints)
  - [Files Endpoints](#files-endpoints)
  - [Conversations Endpoints](#conversations-endpoints)
  - [Model Presets Endpoints](#model-presets-endpoints)
  - [MCP Presets Endpoints](#mcp-presets-endpoints)
  - [Chat Stream Endpoint](#chat-stream-endpoint)

---

## Overview

The Synteles Platform API is a RESTful API built on FastAPI with two separate backend services.

**API Version:** v1

**Architecture:**
- **core-service:** FastAPI — user profiles, agentlets, secrets, conversations, model presets, MCP presets, API keys, files
- **scheduler-service:** FastAPI — execution submission and management
- **synte-service:** FastAPI — streaming AI chat (`POST /chat/stream`)
- **Database:** PostgreSQL (SQLAlchemy async ORM, single schema)
- **Authentication:** Keycloak OIDC — JWT Bearer tokens for user endpoints; API keys (hashed in PostgreSQL) for public endpoints
- **Forward-auth:** Traefik calls `GET /auth/verify` on core-service to validate tokens and inject identity headers

---

## Base URL

```
https://{api-domain-name}/v1
```

**Example:** `https://api.synteles.dev/v1`

All endpoints are prefixed with the version: `/v1/...`

---

## Authentication

### OIDC Bearer Token

Used for user-facing endpoints (`/api/users/*`, `/api/organizations/*`, `/api/agentlets/*`, `/api/executions/*`, `/api/secrets/*`, `/api/conversations/*`, `/api/models/*`, `/api/connectors/*`).

**Authorization Header:**
```
Authorization: Bearer {access_token}
```

The `access_token` is a JWT issued by Keycloak. Tokens are verified against the OIDC JWKS endpoint (`OIDC_JWKS_URL` or `{OIDC_ISSUER_URL}/protocol/openid-connect/certs`).

**JWT Claims used:**
- `sub` — user identifier
- `org_id` — organization UUID (set by provisioner as a Keycloak user attribute)
- `custom:metadata` — fallback for legacy org_id encoding (`{"org_id": "..."}`)

**OAuth2 flow** is handled directly by Keycloak (not by this API). The frontend initiates PKCE or authorization-code flows against the Keycloak authorization endpoint and receives tokens from there.

### API Key Authentication

Used for public agentlet access (`/api/public/agentlets/*`, `/api/public/executions/*`).

**Authorization Header:**
```
Authorization: Bearer {api_key}
```

**Key Format:**
- Generated via `POST /api/users/apikeys`
- URL-safe base64 token (43 characters), generated with `secrets.token_urlsafe(32)`
- SHA256 hash stored in PostgreSQL
- `key_name` must start with a letter or digit; may contain letters, digits, underscores, and hyphens (max 128 characters)

---

## Common Patterns

### CORS Support

All endpoints support CORS with:
- **Allowed Origins:** `CORS_ALLOWED_ORIGINS` environment variable (configurable)
- **Allowed Headers:** `*`
- **Allowed Methods:** `*`
- **Credentials:** `true` (cookies supported)

### Request Format

**Content-Type:** `application/json`

**Path Parameters:** Specified in curly braces (e.g., `{org_id}`, `{agentlet_id}`)

**Query Parameters:** Optional, documented per endpoint

### Response Format

**Content-Type:** `application/json` (default) or `application/x-yaml` (for agentlet YAML)

**Error Structure:**
```json
{
  "detail": "Error message description"
}
```

---

## Error Responses

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 202 | Accepted | Request accepted, processing asynchronously |
| 204 | No Content | Request succeeded, no response body |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource already exists |
| 410 | Gone | Resource existed but is no longer available |
| 500 | Internal Server Error | Server-side error |

### Common Error Responses

**401 Unauthorized:**
```json
{
  "detail": "Missing Bearer token"
}
```

**404 Not Found:**
```json
{
  "detail": "Resource not found"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Internal server error"
}
```

---

## API Endpoints

### Auth Endpoints

#### `GET /auth/verify`

Traefik forward-auth endpoint. Validates Bearer token (JWT or API key) and propagates identity headers to upstream services.

**Authorization:** Bearer token (JWT or API key)

**Response:**
- **Status:** `200 OK`
- **Headers added to upstream request:**
  - `X-User-Id`: authenticated user UUID
  - `X-Org-Id`: organization UUID (empty string if not resolved)
- **Body:**
```json
{
  "ok": true
}
```

**Behavior:**
- If the token contains two dots (`.`), it is treated as a JWT and validated against OIDC JWKS
- Otherwise it is treated as an API key and looked up via SHA256 hash in PostgreSQL

**Error Responses:**
- **401:** Missing or invalid token

---

### User Endpoints

All user endpoints require OIDC authentication.

---

#### `GET /api/users/me`

Returns the authenticated user's basic profile and organization info. On the very first call for a new user, lazily provisions a personal organization and sets `org_id` in Keycloak.

**Authorization:** Bearer token (OIDC)

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "sub": "keycloak-user-uuid",
  "org_id": "org-uuid",
  "org_name": "Personal Workspace"
}
```

**Notes:**
- `org_id` and `org_name` are always present after first call (provisioning creates a personal org)
- On first login the user record is created atomically in PostgreSQL and `org_id` is written back to Keycloak as a user attribute

**Error Responses:**
- **401:** Missing or invalid token
- **500:** Provisioning conflict

**Example:**
```bash
curl https://api.synteles.dev/v1/api/users/me \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

#### `GET /api/users/me/profile`

Returns the full user profile including identity-provider fields (email, name, picture) fetched from the OIDC userinfo endpoint.

**Authorization:** Bearer token (OIDC)

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "sub": "keycloak-user-uuid",
  "email": "user@example.com",
  "name": "John Doe",
  "given_name": "John",
  "family_name": "Doe",
  "picture": "https://...",
  "org_id": "org-uuid",
  "org_name": "Personal Workspace"
}
```

**Notes:**
- Identity fields (`email`, `name`, `given_name`, `family_name`, `picture`) come from the OIDC userinfo endpoint; they may be null if the provider does not include them
- Organization fields are fetched from PostgreSQL

**Error Responses:**
- **401:** Invalid access token

**Example:**
```bash
curl https://api.synteles.dev/v1/api/users/me/profile \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

### Organization Endpoints

---

#### `GET /api/organizations/{org_id}`

Retrieves organization metadata and list of member user IDs.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `org_id` (required): Organization UUID

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "org_name": "Example Organization",
  "users": [
    "user-uuid-1",
    "user-uuid-2"
  ]
}
```

**Error Responses:**
- **403:** Caller does not belong to this organization
- **404:** Organization not found
- **500:** Database error

**Example:**
```bash
curl https://api.synteles.dev/v1/api/organizations/org-123 \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

### Agentlet Endpoints

Agentlets are AI agent configurations stored as YAML definitions. All endpoints require OIDC authentication.

`org_id` is always derived from the caller's JWT token. An optional `?org_id=` query parameter is accepted but must match the token's org — cross-org access returns 403.

---

#### `POST /api/agentlets`

Creates a new agentlet in the caller's organization.

**Authorization:** Bearer token (OIDC)

**Request Body:**
```json
{
  "id": "my_agentlet",
  "description": "Agent description",
  "YAML": "agentlet:\n  name: MyAgent\n  ..."
}
```

**Field Validation:**
- `id` (required): Must start with letter or digit, contain only alphanumeric chars, underscores, or hyphens (max 128 chars); regex `^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$`
- `description` (optional): Text description
- `YAML` (optional): YAML configuration string

**Response:**
- **Status:** `201 Created`
- **Body:**
```json
{
  "id": "my_agentlet",
  "yaml": "agentlet:\n  name: MyAgent\n  ...",
  "description": "Agent description",
  "created_at": "2025-12-01T10:30:00.000000+00:00",
  "updated_at": "2025-12-01T10:30:00.000000+00:00"
}
```

**Error Responses:**
- **400:** Invalid agentlet ID format
```json
{
  "detail": "id is required and must start with a letter or digit; may contain letters, digits, underscores, and hyphens (max 128 characters)"
}
```
- **409:** Agentlet with ID already exists
```json
{
  "detail": "Agentlet with given ID already exists in this organization"
}
```

**Example:**
```bash
curl -X POST https://api.synteles.dev/v1/api/agentlets \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "my_agentlet",
    "description": "My first agent",
    "YAML": "agentlet:\n  name: MyAgent"
  }'
```

---

#### `GET /api/agentlets`

Lists all agentlets in the caller's organization.

**Authorization:** Bearer token (OIDC)

**Query Parameters:**
- `org_id` (optional): Organization UUID — must match the caller's JWT org; reserved for future multi-org support

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
[
  {
    "id": "agentlet1",
    "description": "First agent",
    "created_at": "2025-12-01T10:00:00.000000+00:00",
    "updated_at": "2025-12-01T10:30:00.000000+00:00"
  },
  {
    "id": "agentlet2",
    "description": "Second agent",
    "created_at": "2025-12-01T11:00:00.000000+00:00",
    "updated_at": "2025-12-01T11:00:00.000000+00:00"
  }
]
```

**Notes:**
- Returns summary information only (no YAML content)
- Use `GET /api/agentlets/{agentlet_id}` to retrieve full definition

**Example:**
```bash
curl https://api.synteles.dev/v1/api/agentlets \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

#### `GET /api/agentlets/{agentlet_id}`

Retrieves full agentlet definition including YAML configuration.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `agentlet_id` (required): Agentlet identifier

**Query Parameters:**
- `org_id` (optional): Organization UUID — must match the caller's JWT org

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "description": "Agent description",
  "YAML": "agentlet:\n  name: MyAgent\n  ...",
  "created_at": "2025-12-01T10:00:00.000000+00:00",
  "updated_at": "2025-12-01T10:30:00.000000+00:00"
}
```

**Error Responses:**
- **404:** Agentlet not found
```json
{
  "detail": "Agentlet not found"
}
```

**Example:**
```bash
curl https://api.synteles.dev/v1/api/agentlets/my_agentlet \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

#### `PATCH /api/agentlets/{agentlet_id}`

Updates an existing agentlet.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `agentlet_id` (required): Agentlet identifier

**Request Body:**
```json
{
  "description": "Updated description",
  "YAML": "agentlet:\n  name: UpdatedAgent\n  ..."
}
```

**Notes:**
- Both fields are optional; only provided fields will be updated
- `updated_at` timestamp is automatically set

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "message": "Agentlet updated"
}
```

**Example:**
```bash
curl -X PATCH https://api.synteles.dev/v1/api/agentlets/my_agentlet \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated agent description",
    "YAML": "agentlet:\n  name: UpdatedAgent"
  }'
```

---

#### `DELETE /api/agentlets/{agentlet_id}`

Deletes an agentlet.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `agentlet_id` (required): Agentlet identifier

**Response:**
- **Status:** `204 No Content`

**Error Responses:**
- **404:** Agentlet not found
```json
{
  "detail": "Agentlet not found"
}
```

**Example:**
```bash
curl -X DELETE https://api.synteles.dev/v1/api/agentlets/my_agentlet \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

### API Key Management Endpoints

Manage API keys for programmatic access to public agentlet endpoints.

---

#### `POST /api/users/apikeys`

Creates a new API key for the authenticated user.

**Authorization:** Bearer token (OIDC)

**Request Body:**
```json
{
  "key_name": "My API Key"
}
```

**Field Validation:**
- `key_name` (required): Must start with a letter or digit; may contain letters, digits, underscores, and hyphens (max 128 characters)

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "key_id": "uuid-v4",
  "key": "base64url-encoded-key-43-chars",
  "key_name": "My API Key",
  "created_at": "2025-12-01T10:00:00.000000+00:00"
}
```

**Important:**
- The `key` field contains the actual API key and is only returned once
- Store this key securely; it cannot be retrieved later
- Keys are stored as SHA256 hashes in PostgreSQL

**Error Responses:**
- **400:** Missing or invalid key_name
```json
{
  "detail": "key_name is required"
}
```

**Example:**
```bash
curl -X POST https://api.synteles.dev/v1/api/users/apikeys \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"key_name": "Production API Key"}'
```

---

#### `GET /api/users/apikeys`

Lists all API keys for the authenticated user.

**Authorization:** Bearer token (OIDC)

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
[
  {
    "key_id": "uuid-1",
    "key_name": "Production Key",
    "created_at": "2025-12-01T10:00:00.000000+00:00",
    "last_used": "2025-12-01T15:30:00.000000+00:00"
  },
  {
    "key_id": "uuid-2",
    "key_name": "Development Key",
    "created_at": "2025-11-25T08:00:00.000000+00:00",
    "last_used": null
  }
]
```

**Notes:**
- `last_used` is updated each time the API key is used for authentication
- The actual key value is never returned (only stored as hash)

**Example:**
```bash
curl https://api.synteles.dev/v1/api/users/apikeys \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

#### `DELETE /api/users/apikeys/{apikey_id}`

Deletes (revokes) an API key.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `apikey_id` (required): API key UUID

**Response:**
- **Status:** `204 No Content`

**Error Responses:**
- **404:** API key not found (or key belongs to a different user/org)
```json
{
  "detail": "API key not found"
}
```

**Example:**
```bash
curl -X DELETE https://api.synteles.dev/v1/api/users/apikeys/key-uuid \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

### Secrets Endpoints

User-scoped secrets store LLM API keys (e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) and other sensitive key-value pairs. Secret values are **encrypted at rest in PostgreSQL** (AES-GCM with per-record nonce). At execution time, the scheduler service decrypts the relevant secrets and injects them as container environment variables.

**Reserved name:** `default` cannot be used as a secret name (it is a sentinel for platform-managed credentials).

**Authorization:** Bearer token (OIDC) — all endpoints are scoped to the authenticated user. Users can only access their own secrets.

---

#### `POST /api/secrets`

Creates a new secret for the authenticated user.

**Authorization:** Bearer token (OIDC)

**Request Body:**
```json
{
  "name": "my-llm-keys",
  "description": "OpenAI and Anthropic API keys",
  "value": {
    "ANTHROPIC_API_KEY": "sk-ant-...",
    "OPENAI_API_KEY": "sk-..."
  }
}
```

**Field Details:**
- `name` (required): Secret identifier
  - Must start with alphanumeric character
  - May contain letters, digits, dashes (`-`), underscores (`_`); regex `^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$`
  - Maximum 128 characters
  - Cannot be `default` (reserved)
- `description` (optional): Human-readable description, maximum 1,000 characters
- `value` (required): Non-empty JSON object of string key-value pairs — each key becomes an environment variable name injected into agentlet containers at execution time

**Response:**
- **Status:** `201 Created`
- **Body:**
```json
{
  "name": "my-llm-keys",
  "description": "OpenAI and Anthropic API keys",
  "key_count": 2,
  "created_at": "2025-12-01T10:00:00.000000+00:00"
}
```

**Notes:**
- Secret values are encrypted and stored in PostgreSQL; only metadata (name, description, key count) is returned
- Actual values are never returned by any listing endpoint; use `GET /api/secrets/{secret_name}?reveal_value=true` to retrieve them

**Error Responses:**
- **400:** Missing or invalid `name`
```json
{
  "detail": "name must start with alphanumeric and contain only letters, digits, dashes, or underscores (max 128 chars)"
}
```
- **400:** `name` is reserved
```json
{
  "detail": "'default' is a reserved secret name and cannot be used"
}
```
- **400:** `description` exceeds 1,000 characters
- **400:** Missing or empty `value`
```json
{
  "detail": "value must be a non-empty JSON object"
}
```
- **409:** Secret with this name already exists
```json
{
  "detail": "Secret 'my-llm-keys' already exists"
}
```

**Example:**
```bash
curl -X POST https://api.synteles.dev/v1/api/secrets \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-llm-keys",
    "description": "LLM provider keys",
    "value": {
      "ANTHROPIC_API_KEY": "sk-ant-...",
      "OPENAI_API_KEY": "sk-..."
    }
  }'
```

---

#### `GET /api/secrets`

Lists all secrets for the authenticated user (metadata only, no values).

**Authorization:** Bearer token (OIDC)

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
[
  {
    "name": "my-llm-keys",
    "description": "OpenAI and Anthropic API keys",
    "key_count": 2,
    "created_at": "2025-12-01T10:00:00.000000+00:00",
    "updated_at": "2025-12-01T10:00:00.000000+00:00"
  }
]
```

**Example:**
```bash
curl https://api.synteles.dev/v1/api/secrets \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

#### `GET /api/secrets/{secret_name}`

Retrieves metadata and key names for a specific secret. Optionally returns the actual secret values.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `secret_name` (required): Secret name

**Query Parameters:**
- `reveal_value` (optional): Set to `true` to include the decrypted key-value pairs in the response. Defaults to `false` (key names only).

**Response (default — key names only):**
- **Status:** `200 OK`
- **Body:**
```json
{
  "name": "my-llm-keys",
  "description": "OpenAI and Anthropic API keys",
  "key_names": ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"],
  "created_at": "2025-12-01T10:00:00.000000+00:00",
  "updated_at": "2025-12-01T10:00:00.000000+00:00"
}
```

**Response (`?reveal_value=true` — includes values):**
- **Status:** `200 OK`
- **Body:**
```json
{
  "name": "my-llm-keys",
  "description": "OpenAI and Anthropic API keys",
  "key_names": ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"],
  "value": {
    "ANTHROPIC_API_KEY": "sk-ant-...",
    "OPENAI_API_KEY": "sk-..."
  },
  "created_at": "2025-12-01T10:00:00.000000+00:00",
  "updated_at": "2025-12-01T10:00:00.000000+00:00"
}
```

**Notes:**
- `value` is decrypted on-demand from PostgreSQL; only present when `reveal_value=true`

**Error Responses:**
- **404:** Secret not found
```json
{
  "detail": "Secret not found"
}
```

**Examples:**
```bash
# Key names only (default)
curl https://api.synteles.dev/v1/api/secrets/my-llm-keys \
  -H "Authorization: Bearer ACCESS_TOKEN"

# Include actual values
curl "https://api.synteles.dev/v1/api/secrets/my-llm-keys?reveal_value=true" \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

#### `PATCH /api/secrets/{secret_name}`

Updates the description and/or value of an existing secret.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `secret_name` (required): Secret name

**Request Body:**
```json
{
  "description": "Updated description",
  "value": {
    "ANTHROPIC_API_KEY": "sk-ant-new-...",
    "OPENAI_API_KEY": "sk-new-..."
  }
}
```

**Field Details:**
- `description` (optional): New description string (max 1,000 characters)
- `value` (optional): Replacement secret value — non-empty JSON object of string key-value pairs
- At least one of `description` or `value` must be provided

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "name": "my-llm-keys",
  "description": "Updated description",
  "key_count": 2,
  "updated_at": "2025-12-01T11:00:00.000000+00:00"
}
```

**Notes:**
- When `value` is updated, the entire encrypted value is replaced (not merged)

**Error Responses:**
- **400:** Neither `description` nor `value` provided
- **400:** Invalid `value` format
- **404:** Secret not found

**Example:**
```bash
curl -X PATCH https://api.synteles.dev/v1/api/secrets/my-llm-keys \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "value": {
      "ANTHROPIC_API_KEY": "sk-ant-updated-...",
      "OPENAI_API_KEY": "sk-updated-..."
    }
  }'
```

---

#### `DELETE /api/secrets/{secret_name}`

Deletes a secret (removes encrypted value and metadata from PostgreSQL).

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `secret_name` (required): Secret name

**Response:**
- **Status:** `204 No Content`

**Error Responses:**
- **404:** Secret not found

**Example:**
```bash
curl -X DELETE https://api.synteles.dev/v1/api/secrets/my-llm-keys \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

### Public Agentlet Endpoints

Public endpoints for programmatic agentlet access using API keys.

**Authentication:** All public endpoints use API Key authentication.

**Authorization Header:**
```
Authorization: Bearer {api_key}
```

---

#### `GET /api/public/agentlets/{agentlet_id}`

Retrieves agentlet YAML definition with injected organization attributes.

**Authorization:** API Key (via `Authorization: Bearer {api_key}`)

**Path Parameters:**
- `agentlet_id` (required): Agentlet identifier

**Query Parameters:**
- `format` (optional): Set to `yaml` to return YAML instead of JSON

**Headers:**
- `Accept` (optional): Set to `application/x-yaml` for YAML response

**Response (JSON):**
- **Status:** `200 OK`
- **Content-Type:** `application/json`
- **Body:**
```json
{
  "description": "Agent description",
  "YAML": "agentlet:\n  name: MyAgent\n  attributes:\n    synteles.org.id: org-uuid\n  ..."
}
```

**Response (YAML):**
- **Status:** `200 OK`
- **Content-Type:** `application/x-yaml`
- **Body:**
```yaml
agentlet:
  name: MyAgent
  attributes:
    synteles.org.id: org-uuid
  ...
```

**Attribute Injection:**
The endpoint automatically injects the following attributes into the YAML:
- `synteles.org.id`: Organization UUID from API key context

**Access Control:**
- The agentlet must belong to the same user who created the API key (user-level check)

**Error Responses:**
- **401:** Unauthorized (invalid or missing API key)
- **404:** Agentlet not found, empty agentlet_id, or no YAML definition
```json
{
  "detail": "Agentlet not found"
}
```

**Example (JSON):**
```bash
curl https://api.synteles.dev/v1/api/public/agentlets/my_agentlet \
  -H "Authorization: Bearer base64url-encoded-key-43-chars"
```

**Example (YAML via query param):**
```bash
curl "https://api.synteles.dev/v1/api/public/agentlets/my_agentlet?format=yaml" \
  -H "Authorization: Bearer base64url-encoded-key-43-chars"
```

**Example (YAML via Accept header):**
```bash
curl https://api.synteles.dev/v1/api/public/agentlets/my_agentlet \
  -H "Authorization: Bearer base64url-encoded-key-43-chars" \
  -H "Accept: application/x-yaml"
```

---

#### `POST /api/public/agentlets/{agentlet_id}/executions`

Creates a new agentlet execution using API key authentication.

**Authorization:** API Key (via `Authorization: Bearer {api_key}`)

**Path Parameters:**
- `agentlet_id` (required): Agentlet identifier

**Request Body:**
```json
{
  "prompt": "task description",
  "timeout": 3600,
  "input_objects": [
    "s3://{upload-bucket}/{upload_id}/data.csv"
  ]
}
```

**Request Field Details:**
- `prompt` (optional): Task description included in the execution manifest
- `timeout` (optional): Maximum execution time in seconds
  - Default: `3600` (1 hour)
  - Range: `1-86400` (1 second to 24 hours)
- `input_objects` (optional): List of S3 URIs for input files (from `POST /api/files`)

**Response:**
- **Status:** `202 Accepted`
- **Body:**
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "agentlet_id": "my_agentlet",
  "created_at": "2025-12-13T10:30:45.000000+00:00"
}
```

**Access Control:**
- API key must belong to the same user who created the agentlet

**Error Responses:**
- **400:** Invalid timeout value
- **401:** Missing or invalid API key
- **403:** Not authorized to access this agentlet
- **404:** Agentlet not found

**Example:**
```bash
curl -X POST https://api.synteles.dev/v1/api/public/agentlets/my_agentlet/executions \
  -H "Authorization: Bearer base64url-encoded-key-43-chars" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Generate monthly sales report",
    "timeout": 1800
  }'
```

---

#### `GET /api/public/executions/{execution_id}`

Retrieves execution status and metadata using API key authentication.

**Authorization:** API Key (via `Authorization: Bearer {api_key}`)

**Path Parameters:**
- `execution_id` (required): Execution UUID

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "agentlet_id": "my_agentlet",
  "status": "completed",
  "logs_s3_uri": "s3://synteles-logs/executions/550e8400-e29b-41d4-a716-446655440000/logs.txt",
  "created_at": "2025-12-13T10:30:45.000000+00:00",
  "completed_at": "2025-12-13T10:35:50.000000+00:00",
  "elapsed_seconds": 305,
  "prompt": "Generate monthly sales report"
}
```

**Status Values:**
- `deploying` - Container deployment in progress
- `running` - Container is executing
- `completed` - Execution finished successfully
- `failed` - Execution encountered an error
- `terminated` - Execution was stopped (via cancel or delete)

**Error Responses:**
- **401:** Missing or invalid API key
- **403:** Not authorized (org mismatch)
- **404:** Execution not found

**Example:**
```bash
curl https://api.synteles.dev/v1/api/public/executions/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer base64url-encoded-key-43-chars"
```

---

### Execution/Scheduler Endpoints

Endpoints for managing agentlet executions.

**Architecture:**
- Fire-and-forget async execution pattern
- Background monitor loop polls active executions every 60 seconds
- Automatic log collection and S3 storage on completion
- Agentlet container backend is pluggable via `EXECUTION_BACKEND` env var (Docker by default)
- Execution records are cleaned up automatically by PostgreSQL TTL logic after 30 days

---

#### `POST /api/executions`

Creates a new agentlet execution.

**Authorization:** Bearer token (OIDC)

> **Organization resolution:** `org_id` is derived from the caller's JWT. An optional `org_id` body field may be provided; if present it must match the JWT org or the request is rejected with 403.

**Request Body:**
```json
{
  "agentlet_id": "my_agentlet",
  "prompt": "task description",
  "timeout": 3600,
  "org_id": "org-123",
  "input_objects": [
    "s3://{upload-bucket}/{upload_id}/report.csv",
    "s3://{upload-bucket}/{upload_id}/config.yaml"
  ]
}
```

**Request Field Details:**
- `agentlet_id` (required): Agentlet identifier
- `prompt` (optional): Task description included in the execution manifest
- `timeout` (optional): Maximum execution time in seconds
  - Default: `3600` (1 hour)
  - Range: `1-86400` (1 second to 24 hours)
- `org_id` (optional): Organization UUID. Must match the JWT org if provided.
- `input_objects` (optional): List of S3 URIs for input files (from `POST /api/files`)
  - Maximum 20 files
  - Each URI must point to the file-uploads staging bucket

**Response:**
- **Status:** `202 Accepted`
- **Body:**
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "agentlet_id": "my_agentlet",
  "created_at": "2025-12-13T10:30:45.000000+00:00"
}
```

**Execution Lifecycle:**
1. Execution record created with status `deploying`
2. Platform default credentials fetched if agentlet YAML declares `secrets: [default]` — model-specific API keys loaded from platform environment
3. Named user secrets (listed in agentlet YAML `secrets` array) decrypted from PostgreSQL and merged on top (user secrets take priority over platform defaults)
4. `TAVILY_API_KEY` from user secrets is discarded; platform-configured `TAVILY_API_KEY` is injected instead
5. If `input_objects` provided: files copied from staging bucket → execution-logs bucket
6. A single JSON manifest is uploaded to S3 (`executions/{id}/manifest.json`) containing: `agentlet_yaml`, `input_files`, `output_url`, `prompt`, and effective `timeout`
7. Container launched with `SYNTELES_MANIFEST_URL` (presigned GET URL for the manifest) and `SYNTELES_EXEC_ID` injected as environment variables
8. Status updated to `running` once container is started
9. Background monitor polls active executions and collects logs on completion
10. On completion: logs fetched from container log backend, uploaded to S3, status updated to `completed`/`failed`

**Error Responses:**
- **400:** Invalid timeout value
- **400:** `agentlet_id` is required
- **403:** Caller does not belong to this organization
- **404:** Agentlet not found

**Example:**
```bash
curl -X POST https://api.synteles.dev/v1/api/executions \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agentlet_id": "my_agentlet",
    "prompt": "Generate monthly sales report",
    "timeout": 1800
  }'
```

---

#### `GET /api/executions/{execution_id}`

Retrieves execution status and metadata.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `execution_id` (required): Execution UUID

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "agentlet_id": "my_agentlet",
  "status": "completed",
  "logs_s3_uri": "s3://synteles-logs/executions/550e8400-e29b-41d4-a716-446655440000/logs.txt",
  "created_at": "2025-12-13T10:30:45.000000+00:00",
  "completed_at": "2025-12-13T10:35:50.000000+00:00",
  "elapsed_seconds": 305,
  "prompt": "Generate monthly sales report"
}
```

**Status Values:**
- `deploying` - Container deployment in progress
- `running` - Container is executing
- `completed` - Execution finished successfully
- `failed` - Execution encountered an error
- `terminated` - Execution was stopped

**Field Details:**
- `logs_s3_uri`: S3 URI for log file (null if execution still in progress)
- `completed_at`: ISO 8601 timestamp (null if still running)
- `elapsed_seconds`: Total execution time in seconds (only present if completed)
- `prompt`: Task prompt provided at execution start

**Error Responses:**
- **403:** Caller does not belong to this execution's organization
- **404:** Execution not found

**Example:**
```bash
curl https://api.synteles.dev/v1/api/executions/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

#### `GET /api/executions/{execution_id}/logs`

Retrieves execution logs from S3 storage.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `execution_id` (required): Execution UUID

**Query Parameters:**
- `format` (optional): Response format — `text` (default) or `json`
- `download` (optional): Add Content-Disposition header for file download — `false` (default) or `true`

**Response (200 OK - Text Format):**
- **Content-Type:** `text/plain; charset=utf-8`
- **Headers:**
  - `X-Execution-Status`: Current execution status
  - `X-S3-Uri`: S3 URI of log file
  - `Content-Disposition`: `attachment; filename="execution-{id}-logs.txt"` (if download=true)
- **Body:** (raw log content)
```
[2025-12-13T10:30:45.123Z] [INFO] Container started
[2025-12-13T10:30:46.456Z] [INFO] Loading agentlet configuration...
[2025-12-13T10:35:50.123Z] [INFO] Task completed successfully
```

**Response (200 OK - JSON Format):**
- **Content-Type:** `application/json`
- **Body:**
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "logs_available": true,
  "s3_uri": "s3://synteles-logs/executions/550e8400-e29b-41d4-a716-446655440000/logs.txt",
  "log_size_bytes": 2048,
  "created_at": "2025-12-13T10:30:45.000000+00:00",
  "completed_at": "2025-12-13T10:35:50.000000+00:00",
  "logs": [
    {
      "timestamp": "2025-12-13T10:30:45.123Z",
      "severity": "INFO",
      "message": "Container started"
    }
  ]
}
```

**Response (202 Accepted - Logs Not Available):**
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "logs_available": false,
  "message": "Execution is running. Logs will be available after completion.",
  "created_at": "2025-12-13T10:30:45.000000+00:00"
}
```

**Error Responses:**
- **404:** Execution not found
- **410 Gone:** Execution completed but logs not available
```json
{
  "detail": "Logs are not available for this execution"
}
```
- **500:** Failed to retrieve logs from S3

**Examples:**
```bash
# Text format (default)
curl https://api.synteles.dev/v1/api/executions/550e8400-e29b-41d4-a716-446655440000/logs \
  -H "Authorization: Bearer ACCESS_TOKEN"

# JSON format
curl "https://api.synteles.dev/v1/api/executions/550e8400-e29b-41d4-a716-446655440000/logs?format=json" \
  -H "Authorization: Bearer ACCESS_TOKEN"

# Download as file
curl "https://api.synteles.dev/v1/api/executions/550e8400-e29b-41d4-a716-446655440000/logs?download=true" \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -o execution-logs.txt
```

---

#### `POST /api/executions/{execution_id}/cancel`

Cancels a running execution. If the execution is `deploying` or `running`, sends a stop request to the container backend and marks the execution as `terminated`.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `execution_id` (required): Execution UUID

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "terminated",
  "stopped_at": "2025-12-13T10:40:00.000000+00:00"
}
```

**Notes:**
- If the execution is already in a terminal state (`completed`, `failed`, `terminated`) the request is still accepted; the response reflects the current state
- `stopped_at` is null if the execution completed before the cancel was processed

**Error Responses:**
- **403:** Caller does not belong to this execution's organization
- **404:** Execution not found

**Example:**
```bash
curl -X POST https://api.synteles.dev/v1/api/executions/550e8400-e29b-41d4-a716-446655440000/cancel \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

#### `DELETE /api/executions/{execution_id}`

Stops a running execution and removes it from the active state. Calls the container backend's stop API if the execution is still running.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `execution_id` (required): Execution UUID

**Response:**
- **Status:** `204 No Content`

**Error Responses:**
- **403:** Caller does not belong to this execution's organization
- **404:** Execution not found

**Example:**
```bash
curl -X DELETE https://api.synteles.dev/v1/api/executions/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

#### `GET /api/executions`

Lists executions with filtering and pagination support.

**Authorization:** Bearer token (OIDC)

**Query Parameters:**
- `agentlet_id` (optional): Filter by agentlet identifier
- `status` (optional): Filter by execution status
  - Valid values: `deploying`, `running`, `completed`, `failed`, `stopped`, `terminated`
- `created_at_start` (optional): Filter by creation date (ISO 8601 timestamp, inclusive)
- `created_at_end` (optional): Filter by creation date (ISO 8601 timestamp, inclusive)
- `completed_at_start` (optional): Filter by completion date (ISO 8601 timestamp, inclusive)
- `completed_at_end` (optional): Filter by completion date (ISO 8601 timestamp, inclusive)
- `limit` (optional): Maximum number of results per page
  - Default: `50`
  - Range: `1-100`
- `next_token` (optional): Pagination token from previous response

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "executions": [
    {
      "execution_id": "550e8400-e29b-41d4-a716-446655440000",
      "agentlet_id": "my_agentlet",
      "status": "completed",
      "created_at": "2025-12-13T10:30:45.000000+00:00",
      "completed_at": "2025-12-13T10:35:50.000000+00:00",
      "logs_s3_uri": "s3://synteles-logs/executions/550e8400-e29b-41d4-a716-446655440000/logs.txt",
      "elapsed_seconds": 305,
      "prompt": "Generate monthly sales report"
    }
  ],
  "count": 1,
  "next_token": "NTA="
}
```

**Field Details:**
- `executions`: Array of execution summaries (each includes `prompt`)
- `count`: Number of executions in current response
- `next_token`: Base64-encoded offset token (present only if more results available)
- `elapsed_seconds`: Only present for completed executions
- `completed_at`: Null for in-progress executions
- `logs_s3_uri`: Null for in-progress executions

**Pagination:**
- Results sorted by `created_at` descending (newest first)
- Use `next_token` from response to fetch next page
- Invalid tokens are treated as first page (offset 0)

**Error Responses:**
- **400:** Invalid limit or status value
- **401:** User not associated with any organization

**Examples:**
```bash
# List all executions
curl "https://api.synteles.dev/v1/api/executions" \
  -H "Authorization: Bearer ACCESS_TOKEN"

# Filter by agentlet_id and status
curl "https://api.synteles.dev/v1/api/executions?agentlet_id=my_agentlet&status=completed&limit=10" \
  -H "Authorization: Bearer ACCESS_TOKEN"

# Paginate
curl "https://api.synteles.dev/v1/api/executions?limit=50&next_token=NTA=" \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

### Files Endpoints

Endpoints for agentlet file exchange — uploading input files before execution and retrieving input/output files after execution. Files are transferred via S3 presigned URLs.

**Architecture:**
- **Staging bucket** (`synteles-uploads`): Temporary upload target; 7-day lifecycle expiry
- **Logs bucket** (`synteles-logs`): Permanent storage for execution logs, input files (`executions/{id}/input/`) and output artifacts (`executions/{id}/output/output.zip`); 30-day lifecycle expiry
- **Container env vars**: `SYNTELES_MANIFEST_URL` (presigned GET URL for the execution manifest JSON) and `SYNTELES_EXEC_ID` are injected directly; the manifest itself contains `input_files`, `output_url`, `agentlet_yaml`, `prompt`, and `timeout`

**Typical workflow:**
1. Call `POST /api/files` to create an upload session and get presigned POST URLs
2. Upload files directly to S3 using the returned URLs
3. Pass the `s3_uri` values as `input_objects` in the execution create request
4. After execution completes, call `GET /api/executions/{id}/files` to get presigned download URLs

---

#### `POST /api/files`

Creates an upload session and returns presigned S3 POST URLs for a batch of input files.

**Authorization:** Bearer token (OIDC)

**Request Body:**
```json
{
  "files": [
    {"name": "report.csv"},
    {"name": "config.yaml"}
  ]
}
```

**Field Details:**
- `files` (required): Non-empty list of file descriptors (max 20)
  - Each entry must have a `name` field (non-empty string, no path separators `/` or `\`, no leading dot)

**Response:**
- **Status:** `201 Created`
- **Body:**
```json
{
  "upload_id": "550e8400-e29b-41d4-a716-446655440000",
  "files": [
    {
      "name": "report.csv",
      "s3_uri": "s3://{upload-bucket}/{upload_id}/report.csv",
      "upload_url": "https://{upload-bucket}.s3.amazonaws.com/",
      "upload_fields": {
        "key": "{upload_id}/report.csv",
        "AWSAccessKeyId": "...",
        "policy": "...",
        "signature": "..."
      },
      "type": "document"
    }
  ]
}
```

**Field Details:**
- `upload_id`: UUID grouping this batch — pass associated `s3_uri` values as `input_objects` when starting the execution
- `upload_url` + `upload_fields`: Use these to perform a multipart POST upload directly to S3 (standard S3 presigned POST format)
- `type`: `"image"` for `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp` files; `"document"` otherwise
- Presigned URLs expire in **1 hour**
- Maximum file size: **50 MB** per file (enforced via S3 policy condition)

**Uploading a file (example with curl):**
```bash
curl -X POST {upload_url} \
  -F "key={upload_id}/report.csv" \
  -F "AWSAccessKeyId={AWSAccessKeyId}" \
  -F "policy={policy}" \
  -F "signature={signature}" \
  -F "file=@report.csv"
```

**Error Responses:**
- **400:** `'files' must not be empty`
- **400:** `Too many files. Maximum 20 files allowed.`
- **400:** `Each file entry must have a non-empty 'name' field`
- **400:** `Invalid file name: {name}` (path separators or leading dot)
- **500:** Failed to generate upload URL

**Example:**
```bash
curl -X POST https://api.synteles.dev/v1/api/files \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"files": [{"name": "data.csv"}, {"name": "config.yaml"}]}'
```

---

#### `GET /api/executions/{execution_id}/files`

Lists input files and checks for output.zip for a completed execution, returning presigned S3 GET URLs.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `execution_id` (required): Execution UUID (must be a valid UUID v4 format)

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "input_files": [
    {
      "name": "report.csv",
      "size": 204800,
      "download_url": "https://...",
      "type": "document"
    },
    {
      "name": "banner.png",
      "size": 1024,
      "download_url": "https://...",
      "type": "image"
    }
  ],
  "output_zip": {
    "exists": true,
    "download_url": "https://..."
  }
}
```

**Field Details:**
- `input_files`: Files copied from staging bucket at execution launch; empty array if no input files were provided
- `type`: `"image"` for image extensions; `"document"` for all other files
- `output_zip.exists`: `true` if the agentlet uploaded `output.zip` to `executions/{id}/output/output.zip`
- `output_zip.download_url`: Presigned GET URL (null if `exists` is false)
- All presigned URLs expire in **1 hour**

**Error Responses:**
- **400:** `Invalid execution_id format`
- **401:** User not associated with any organization
- **403:** Not authorized to access this execution (org or user mismatch)
- **404:** Execution not found

**Example:**
```bash
curl https://api.synteles.dev/v1/api/executions/550e8400-e29b-41d4-a716-446655440000/files \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

### Conversations Endpoints

User-scoped conversation history. Conversations store display messages and agent state as JSON blobs in S3 (presigned URL access), with metadata in PostgreSQL. Conversations expire after 90 days.

**Auth:** Bearer token (OIDC)

---

#### `GET /api/conversations`

Lists all conversations for the authenticated user (metadata only, no message content).

**Authorization:** Bearer token (OIDC)

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "conversations": [
    {
      "conversation_id": "conv-uuid-1",
      "title": "My conversation",
      "message_count": 5,
      "created_at": "2025-12-01T10:00:00.000000+00:00",
      "updated_at": "2025-12-01T10:30:00.000000+00:00"
    }
  ]
}
```

**Example:**
```bash
curl https://api.synteles.dev/v1/api/conversations \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

#### `POST /api/conversations`

Creates a new conversation, uploading display messages and agent state to S3.

**Authorization:** Bearer token (OIDC)

**Request Body:**
```json
{
  "title": "My conversation",
  "display_messages": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"}
  ],
  "agent_state": {}
}
```

**Field Details:**
- `title` (optional): Conversation title, max 80 characters (truncated if longer); defaults to `""`
- `display_messages` (required): List of message objects to store in S3
- `agent_state` (required): Arbitrary agent state object to store in S3

**Response:**
- **Status:** `201 Created`
- **Body:**
```json
{
  "conversation_id": "conv-uuid",
  "title": "My conversation",
  "message_count": 2,
  "created_at": "2025-12-01T10:00:00.000000+00:00",
  "updated_at": "2025-12-01T10:00:00.000000+00:00"
}
```

**Error Responses:**
- **400:** Validation error
- **401:** Unauthenticated

**Example:**
```bash
curl -X POST https://api.synteles.dev/v1/api/conversations \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My conversation",
    "display_messages": [{"role": "user", "content": "Hello"}],
    "agent_state": {}
  }'
```

---

#### `GET /api/conversations/{conv_id}`

Gets a conversation's metadata and returns presigned S3 URLs for display messages and agent state.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `conv_id` (required): Conversation UUID

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "conversation_id": "conv-uuid",
  "title": "My conversation",
  "message_count": 2,
  "created_at": "2025-12-01T10:00:00.000000+00:00",
  "updated_at": "2025-12-01T10:30:00.000000+00:00",
  "display_url": "https://s3.amazonaws.com/...presigned...",
  "agent_state_url": "https://s3.amazonaws.com/...presigned..."
}
```

**Field Details:**
- `display_url`: Presigned GET URL for `conversations/{user_id}/{conv_id}/display.json` — fetch this to get the message list
- `agent_state_url`: Presigned GET URL for `conversations/{user_id}/{conv_id}/agent_state.json`
- Presigned URLs expire in **5 minutes** (300 seconds)

**Error Responses:**
- **401:** Unauthenticated
- **403:** Not the owner of this conversation
- **404:** Conversation not found

**Example:**
```bash
curl https://api.synteles.dev/v1/api/conversations/conv-uuid \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

#### `PATCH /api/conversations/{conv_id}`

Updates a conversation's title, display messages, and/or agent state.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `conv_id` (required): Conversation UUID

**Request Body:**
```json
{
  "title": "Updated title",
  "display_messages": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi!"},
    {"role": "user", "content": "How are you?"}
  ],
  "agent_state": {"step": 2}
}
```

**Field Details:**
- `title` (optional): New title (max 80 chars, truncated if longer)
- `display_messages` (optional): Replacement message list written to S3
- `agent_state` (optional): Replacement agent state written to S3

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "conversation_id": "conv-uuid",
  "updated_at": "2025-12-01T11:00:00.000000+00:00"
}
```

**Notes:**
- The conversation TTL is reset to 90 days from now on each update

**Error Responses:**
- **400:** Validation error
- **401:** Unauthenticated
- **403:** Not the owner
- **404:** Not found

**Example:**
```bash
curl -X PATCH https://api.synteles.dev/v1/api/conversations/conv-uuid \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated title"}'
```

---

#### `DELETE /api/conversations/{conv_id}`

Deletes a conversation and its S3 objects.

**Authorization:** Bearer token (OIDC)

**Path Parameters:**
- `conv_id` (required): Conversation UUID

**Response:**
- **Status:** `200 OK`
- **Body:**
```json
{
  "conversation_id": "conv-uuid",
  "deleted": true
}
```

**Notes:**
- S3 objects (`display.json`, `agent_state.json`) are deleted after the database record is removed

**Error Responses:**
- **401:** Unauthenticated
- **403:** Not the owner
- **404:** Not found

**Example:**
```bash
curl -X DELETE https://api.synteles.dev/v1/api/conversations/conv-uuid \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

### Model Presets Endpoints

User-scoped model configuration presets. Each preset stores a provider, model ID, and optional secret name for a user's LLM configuration. Presets are scoped to the authenticated user (not the org).

**Auth:** Bearer token (OIDC)

---

#### `POST /api/models`

Creates a model preset.

**Request:**
```json
{
  "name": "my_claude",
  "description": "Claude Sonnet for coding",
  "provider": "anthropic",
  "model_id": "claude-sonnet-4-6",
  "secret_name": "my-llm-keys"
}
```

- `name` — required; regex `^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$` (starts with letter or digit, allows hyphens)
- `description` — optional; max 500 chars
- `provider` — required; one of: `anthropic`, `azure`, `azure_ai`, `bedrock`, `gemini`, `openai`, `sagemaker`, `vertex_ai`
- `model_id` — required; max 512 chars
- `secret_name` — optional; name of a user secret holding the API key; max 128 chars

**Response (201):**
```json
{
  "name": "my_claude",
  "description": "Claude Sonnet for coding",
  "provider": "anthropic",
  "model_id": "claude-sonnet-4-6",
  "secret_name": "my-llm-keys",
  "created_at": "2026-03-19T10:00:00+00:00",
  "updated_at": "2026-03-19T10:00:00+00:00"
}
```

**Errors:** `400` validation, `401` unauthenticated, `409` name already exists, `500` database error

---

#### `GET /api/models`

Lists all model presets for the authenticated user.

**Response (200):** Array of preset objects (same shape as POST 201 response)

---

#### `GET /api/models/{preset_name}`

Gets a single model preset.

**Response (200):** Preset object

**Errors:** `401`, `404` not found

---

#### `PATCH /api/models/{preset_name}`

Updates a model preset (partial update). At least one field must be provided.

**Request:** Any subset of `description`, `model_id`, `secret_name`
- Pass `secret_name: ""` (empty string) to remove the secret association

**Response (200):** `{"message": "Model preset updated"}`

**Errors:** `400` validation (including if no fields provided), `401`, `404` not found

---

#### `DELETE /api/models/{preset_name}`

Deletes a model preset.

**Response (204):** No content

**Errors:** `401`, `404` not found

---

### MCP Presets Endpoints

Organization-scoped MCP (Model Context Protocol) server configuration presets. Each preset stores a JSON MCP server configuration that can be applied to agentlets. Presets are scoped to the authenticated user's organization.

**Auth:** Bearer token (OIDC)

---

#### `POST /api/connectors`

Creates an MCP server preset.

**Request:**
```json
{
  "name": "strands_agents",
  "description": "Strands AI toolkit MCP server",
  "mcp_config": "{\"mcpServers\":{\"strands-agents\":{\"command\":\"uvx\",\"args\":[\"strands-agents-mcp-server\"]}}}"
}
```

- `name` — required; regex `^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$` (starts with letter or digit, allows hyphens)
- `description` — optional; max 500 chars
- `mcp_config` — required; JSON string with top-level `mcpServers` key

**Response (201):**
```json
{
  "name": "strands_agents",
  "description": "Strands AI toolkit MCP server",
  "mcp_config": "{\"mcpServers\":{...}}",
  "created_at": "2026-03-19T10:00:00+00:00",
  "updated_at": "2026-03-19T10:00:00+00:00"
}
```

**Errors:** `400` validation, `401` unauthenticated, `409` name already exists, `500` database error

---

#### `GET /api/connectors`

Lists all MCP presets for the authenticated user's organisation.

**Response (200):**
```json
{
  "presets": [
    {
      "name": "strands_agents",
      "description": "Strands AI toolkit",
      "mcp_config": "{\"mcpServers\":{...}}",
      "created_at": "2026-03-19T10:00:00+00:00",
      "updated_at": "2026-03-19T10:00:00+00:00"
    }
  ]
}
```

---

#### `GET /api/connectors/{name}`

Gets a single MCP preset.

**Response (200):** Preset object

**Errors:** `401`, `404` `"Preset '{name}' not found"`

---

#### `PATCH /api/connectors/{name}`

Updates an MCP preset (partial update).

**Request:** Any subset of `description`, `mcp_config`

**Response (200):** Updated preset object

**Errors:** `400` validation, `401`, `404` not found

---

#### `DELETE /api/connectors/{name}`

Deletes an MCP preset.

**Response (200):** `{"message": "Preset '{name}' deleted"}`

**Errors:** `401`, `404` not found

---

### Chat Stream Endpoint

The chat stream endpoint is served by the **synte-service** (a separate FastAPI application). It implements a streaming Server-Sent Events (SSE) interface for interactive AI conversations.

**Service:** `synte-service`

**Authentication:** Bearer token (OIDC JWT). The token signature is verified against OIDC JWKS if `OIDC_ISSUER_URL`/`OIDC_JWKS_URL` are configured; otherwise verification is skipped (local dev mode).

---

#### `POST /chat/stream`

Submits a user message and streams the AI agent's response as Server-Sent Events.

**Authorization:** Bearer token (OIDC)

**Request Body:**
```json
{
  "message": "Create an agentlet that analyzes sales data",
  "messages": [],
  "manager_state": {},
  "org_id": "org-uuid",
  "pending_input_objects": [
    "s3://{upload-bucket}/{upload_id}/data.csv"
  ]
}
```

**Field Details:**
- `message` (required): Current user message
- `messages` (optional): Prior conversation messages for context (default: `[]`)
- `manager_state` (optional): Opaque state object from previous turn (default: `{}`)
- `org_id` (optional): Organization UUID for context resolution
- `pending_input_objects` (optional): List of S3 URIs for files to include in this turn

**Response:**
- **Status:** `200 OK`
- **Content-Type:** `text/event-stream`
- **Headers:**
  - `Cache-Control: no-cache`
  - `X-Accel-Buffering: no`
- **Body:** Server-Sent Events stream

**Error Responses:**
- **401:** Missing or invalid Bearer token

**Example:**
```bash
curl -X POST https://synte.synteles.dev/chat/stream \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Help me create an agentlet",
    "messages": [],
    "manager_state": {}
  }'
```

---

#### `GET /health` (synte-service)

Health check endpoint.

**Response:**
```json
{"status": "ok"}
```

---

## Rate Limits

**FastAPI services:** Rate limiting is handled at the infrastructure level (reverse proxy / API gateway)

Contact the platform team to configure rate limits.

---

## Versioning

**Current Version:** v1

The API version is specified in the URL path: `https://{domain}/v1/...`

Breaking changes will be introduced in new versions (v2, v3, etc.) while maintaining backward compatibility with previous versions.

---

## Support

For API issues or questions:
- GitHub Issues: [platform-infra repository]
- Documentation: See `README.md` in repository root

---

**Last Updated:** 2026-05-27
**API Version:** v1
