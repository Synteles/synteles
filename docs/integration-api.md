# Synteles Integration API

> **Intended audience:** Engineering teams building integrations against Synteles platform. All endpoints here are authenticated with a long-lived API key (`X-API-Key`) and require no Keycloak session. If you are contributing to the Synteles platform, see [platform-api.md](platform-api.md) instead.

The Integration API lets external services and automation pipelines trigger agentlet executions, poll their status, and deliver human-in-the-loop responses — all using a long-lived API key instead of a user session.

## Table of Contents
- [Base URL](#base-url)
- [Authentication](#authentication)
  - [Getting an API Key](#getting-an-api-key)
  - [Using the API Key](#using-the-api-key)
- [Integration Workflow](#integration-workflow)
- [Endpoints](#endpoints)
  - [GET /api/public/agentlets/{agentlet_id}](#get-apipublicagentletsagentlet_id)
  - [POST /api/public/agentlets/{agentlet_id}/executions](#post-apipublicagentletsagentlet_idexecutions)
  - [GET /api/public/executions/{execution_id}](#get-apipublicexecutionsexecution_id)
  - [POST /api/public/executions/{execution_id}/signal](#post-apipublicexecutionsexecution_idsignal)
- [Execution Status Values](#execution-status-values)
- [Error Responses](#error-responses)

---

## Base URL

```
https://{api-domain-name}
```

---

## Authentication

### Getting an API Key

API keys are created through the Synteles UI or by calling `POST /api/users/apikeys` with an OIDC Bearer token (see [platform-api.md — API Key Management Endpoints](platform-api.md#api-key-management-endpoints)):

```bash
curl -X POST https://{api-domain-name}/api/users/apikeys \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"key_name": "my-integration-key"}'
```

Response:

```json
{
  "key_id": "uuid-v4",
  "key": "{api_key}",
  "key_name": "my-integration-key",
  "created_at": "2026-01-01T10:00:00.000000+00:00"
}
```

**The `key` value is shown only once — store it securely.**

Key format: URL-safe base64 string (43 characters), produced by `secrets.token_urlsafe(32)`. The key is stored as a SHA256 hash; the raw value is never persisted.

### Using the API Key

Include the key in every request:

```
X-API-Key: {api_key}
```

The key is passed as-is — no encoding required.

---

## Integration Workflow

Typical integration sequence:

1. **Generate an API key** (`POST /api/users/apikeys`) — one-time setup
2. **Fetch the agentlet definition** (`GET /api/public/agentlets/{agentlet_id}`) — optional; use to inspect YAML before submitting
3. **Submit an execution** (`POST /api/public/agentlets/{agentlet_id}/executions`) — returns immediately with `execution_id`
4. **Poll for status** (`GET /api/public/executions/{execution_id}`) — repeat until status is terminal
5. **Respond to questions** (`POST /api/public/executions/{execution_id}/signal`) — when `status == "waiting_for_signal"`, send the answer to unblock the workflow

Status terminal values: `completed`, `failed`, `terminated`.

---

## Endpoints

### `GET /api/public/agentlets/{agentlet_id}`

Retrieves the agentlet YAML definition. The response automatically injects `synteles.org.id` into the YAML attributes.

**Authorization:** `X-API-Key: {api_key}`

**Path Parameters:**
- `agentlet_id` (required): Agentlet identifier

**Query Parameters:**
- `format` (optional): Set to `yaml` to return YAML instead of JSON

**Headers:**
- `Accept` (optional): Set to `application/x-yaml` for YAML response

**Response (JSON — default):**
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

**Access Control:** The agentlet must belong to the same user who created the API key.

**Error Responses:**
- **401:** Invalid or missing API key
- **404:** Agentlet not found, empty `agentlet_id`, or no YAML definition

**Examples:**

```bash
# JSON response
curl https://{api-domain-name}/api/public/agentlets/my_agentlet \
  -H "X-API-Key: {api_key}"

# YAML via query param
curl "https://{api-domain-name}/api/public/agentlets/my_agentlet?format=yaml" \
  -H "X-API-Key: {api_key}"

# YAML via Accept header
curl https://{api-domain-name}/api/public/agentlets/my_agentlet \
  -H "X-API-Key: {api_key}" \
  -H "Accept: application/x-yaml"
```

---

### `POST /api/public/agentlets/{agentlet_id}/executions`

Submits a new execution for the agentlet. Returns immediately with an `execution_id`; use `GET /api/public/executions/{execution_id}` to poll for completion.

**Authorization:** `X-API-Key: {api_key}`

**Path Parameters:**
- `agentlet_id` (required): Agentlet identifier

**Request Body:**
```json
{
  "prompt": "Generate monthly sales report",
  "timeout": 1800,
  "input_objects": [
    "s3://{upload-bucket}/{upload_id}/data.csv"
  ]
}
```

**Field Details:**
- `prompt` (optional): Task description included in the execution manifest
- `timeout` (optional): Maximum execution time in seconds
  - Default: `3600` (1 hour)
  - Range: `1–86400` (1 second to 24 hours)
- `input_objects` (optional): List of S3 URIs for input files (from `POST /api/files` — see [platform-api.md](platform-api.md#post-apifiles))

**Response:**
- **Status:** `202 Accepted`
- **Body:**
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "agentlet_id": "my_agentlet",
  "created_at": "2026-01-01T10:30:45.000000+00:00"
}
```

**Access Control:** API key must belong to the same user who created the agentlet.

**Error Responses:**
- **400:** Invalid `timeout` value
- **401:** Missing or invalid API key
- **403:** Not authorized to access this agentlet
- **404:** Agentlet not found

**Example:**

```bash
curl -X POST https://{api-domain-name}/api/public/agentlets/my_agentlet/executions \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Generate monthly sales report",
    "timeout": 1800
  }'
```

---

### `GET /api/public/executions/{execution_id}`

Returns the current status and metadata for an execution.

**Authorization:** `X-API-Key: {api_key}`

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
  "created_at": "2026-01-01T10:30:45.000000+00:00",
  "completed_at": "2026-01-01T10:35:50.000000+00:00",
  "elapsed_seconds": 305,
  "prompt": "Generate monthly sales report",
  "workflow_id": "synteles-550e8400-e29b-41d4-a716-446655440000",
  "last_message": "The report has been generated.",
  "pending_question": "Should I delete the old file?"
}
```

**Field Details:**
- `workflow_id`: Temporal workflow ID; **only present** for durable executions that have an associated workflow
- `last_message`: Most recent assistant message; **only present** for active or completed durable executions when a message is available (omitted otherwise)
- `pending_question`: Current `ask_user` question; **only present** when `status == "waiting_for_signal"` and a question is available (omitted otherwise)
- `completed_at`: Null for in-progress executions
- `logs_s3_uri`: Null for in-progress executions
- `elapsed_seconds`: Only present for completed executions

**Error Responses:**
- **401:** Missing or invalid API key
- **403:** Not authorized (org mismatch)
- **404:** Execution not found

**Example:**

```bash
curl https://{api-domain-name}/api/public/executions/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: {api_key}"
```

---

### `POST /api/public/executions/{execution_id}/signal`

Delivers a human response to a durable execution that is paused at an `ask_user` tool call (`status == "waiting_for_signal"`). After delivery the status flips to `running`; the monitor confirms on the next poll tick.

**Authorization:** `X-API-Key: {api_key}`

**Path Parameters:**
- `execution_id` (required): Execution UUID

**Request Body:**
```json
{
  "input": "Yes, proceed with the deletion."
}
```

**Field Details:**
- `input` (required): The human answer to the pending question. Delivered as the `provide_user_input` Temporal signal.

**Response:**
- **Status:** `202 Accepted`
- **Body:**
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running"
}
```

**Notes:**
- Sending the signal also refreshes the presigned output URL and restarts the worker container if it stopped during the HITL pause

**Error Responses:**
- **401:** Missing or invalid API key
- **404:** Execution not found
- **409:** Execution is not durable, not in `waiting_for_signal` state, or has no `workflow_id`
- **500:** Temporal RPC failure

**Example:**

```bash
curl -X POST https://{api-domain-name}/api/public/executions/550e8400-e29b-41d4-a716-446655440000/signal \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{"input": "Yes, proceed."}'
```

---

## Execution Status Values

| Status | Description |
|--------|-------------|
| `deploying` | Container deployment in progress |
| `running` | Container is executing |
| `waiting_for_signal` | Durable execution paused at an `ask_user` call — send a signal to resume |
| `completed` | Execution finished successfully |
| `failed` | Execution encountered an error |
| `terminated` | Execution was stopped (via cancel or delete) |

---

## Error Responses

All errors return JSON with a `detail` field:

```json
{
  "detail": "Error message description"
}
```

| Code | Meaning |
|------|---------|
| 401 | Missing or invalid API key |
| 403 | Not authorized (org mismatch) |
| 404 | Resource not found |
| 409 | Conflict (e.g. execution not in expected state) |
| 500 | Server-side error |
