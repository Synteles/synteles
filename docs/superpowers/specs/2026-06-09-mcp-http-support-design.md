# MCP HTTP Transport Support — Design Spec

**Date:** 2026-06-09
**Scope:** `durable-worker/` only
**Status:** Approved

---

## Problem

The durable-worker's `parse_agentlet()` silently skips any MCP tool entry whose `server` field is not `"stdio"`. The `agentlet-schema.json` already defines and validates `server: "http"` (Streamable HTTP) and `server: "sse"` (legacy SSE) — the gap is purely in the durable-worker implementation.

---

## Goal

Support all three MCP transport types in the durable-worker:

| `server` value | Transport | Auth |
|---|---|---|
| `stdio` | subprocess stdin/stdout | env vars injected into process |
| `http` | MCP Streamable HTTP (spec 2025-03) | `headers` + `api_key_env` |
| `sse` | Server-Sent Events (legacy) | none (in-network only) |

The agentlet YAML schema (`agentlet-schema.json`) requires **no changes**.

---

## YAML Schema (no changes required)

The `MCPToolConfig` definition in `agentlet-schema.json` already covers:

```yaml
mcp_tools:
  # existing — unchanged
  - name: file_reader
    server: stdio
    command: uvx
    args: ["mcp-file-reader"]
    env:
      BASE_DIR: /tmp/input

  # new — Streamable HTTP
  - name: web_search
    server: http
    url: "http://search-mcp:8000/mcp"
    headers:
      Authorization: "Bearer ${SEARCH_API_KEY}"
    # or equivalently:
    api_key_env: "SEARCH_API_KEY"

  # new — legacy SSE (unauthenticated)
  - name: crm_tools
    server: sse
    url: "http://crm-mcp:9000/sse"
```

**Header value rules (http only):**
- `${VAR_NAME}` placeholders in header values are resolved from the container's environment at worker startup.
- `api_key_env: "VAR"` adds `Authorization: Bearer <env[VAR]>` if no `Authorization` header is already present.
- SSE: `headers` and `api_key_env` are ignored (per schema description).

---

## Data Model

### `manifest.py` — two spec types replace the single `MCPToolSpec`

```
StdioMCPToolSpec
  name:    str
  command: str
  args:    list[str]          default []
  env:     dict[str, str]     default {}

HttpMCPToolSpec
  name:       str
  url:        str
  transport:  Literal["http", "sse"]
  headers:    dict[str, str]  default {}   ← raw, unresolved values from YAML
  api_key_env: str | None     default None

MCPToolSpec = StdioMCPToolSpec | HttpMCPToolSpec

AgentletSpec.mcp_tools: list[MCPToolSpec]   ← was list[StdioMCPToolSpec]
```

### `agent_config.py` — two server ref types replace the single `MCPServerRef`

```
StdioServerRef
  command: str
  args:    list[str]
  env:     dict[str, str]

HttpServerRef
  url:       str
  transport: Literal["http", "sse"]
  headers:   dict[str, str]   ← already resolved (${VAR} expanded, api_key_env applied)

MCPServerRef = StdioServerRef | HttpServerRef
```

`HttpServerRef` carries **resolved** headers. Resolution happens once at worker startup in `_fetch_mcp_schemas()`, not on every tool call.

---

## Component Changes

### `manifest.py` — `parse_agentlet()`

Replace the `if tool.get("server") == "stdio"` filter with a three-way branch:

```
for tool in config.get("mcp_tools") or []:
    server = tool.get("server")
    if server == "stdio" and tool.get("command"):
        append StdioMCPToolSpec(name, command, args, env)
    elif server in ("http", "sse") and tool.get("url"):
        append HttpMCPToolSpec(name, url, transport=server, headers, api_key_env)
    else:
        log warning and skip
```

Entries with `server: http` or `server: sse` but no `url` are skipped with a warning (same behaviour as today for unknown server types).

---

### `worker.py` — `_fetch_mcp_schemas()`

Add an `isinstance` dispatch inside the existing loop. The stdio branch is unchanged.

**HTTP/SSE branch — header resolution:**

```
resolved = {}
for key, value in spec.headers.items():
    resolved[key] = re.sub(r"\$\{([^}]+)\}", lambda m: os.environ.get(m.group(1), ""), value)

if spec.api_key_env and "Authorization" not in resolved:
    key_value = os.environ.get(spec.api_key_env, "")
    if key_value:
        resolved["Authorization"] = f"Bearer {key_value}"
```

**Tool discovery:**

```
if spec.transport == "http":
    ctx = streamablehttp_client(spec.url, headers=resolved)
    async with ctx as (read, write, _):
        async with ClientSession(read, write) as session: ...
elif spec.transport == "sse":
    async with sse_client(spec.url) as (read, write):
        async with ClientSession(read, write) as session: ...
```

On connection failure, log a warning and skip the server — same behaviour as stdio.

Builds an `HttpServerRef(url, transport, headers=resolved)` and populates `tool_map`.

---

### `activities.py` — new `call_http_mcp_tool` activity

```python
@activity.defn
async def call_http_mcp_tool(
    url: str,
    transport: str,           # "http" | "sse"
    headers: dict[str, str],  # already resolved
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
```

- `transport == "http"` → `streamablehttp_client(url, headers=headers)`
- `transport == "sse"` → `sse_client(url)` (headers ignored)
- Returns joined text content, same as `call_mcp_tool`.
- Registered in `Worker(activities=[call_llm_step, call_mcp_tool, call_http_mcp_tool, upload_output])`.
- Same retry policy as `call_mcp_tool`: 5 attempts, 30 s initial, ×2 backoff, 120 s max.

---

### `workflows/agent.py` — activity dispatch

The existing `mcp_ref` branch becomes a two-way dispatch:

```python
if isinstance(mcp_ref, StdioServerRef):
    tool_result = await workflow.execute_activity(
        call_mcp_tool,
        args=[mcp_ref.command, mcp_ref.args, mcp_ref.env, tool_name, tool_args],
        start_to_close_timeout=timedelta(seconds=60),
        retry_policy=_TOOL_RETRY,
    )
else:  # HttpServerRef
    tool_result = await workflow.execute_activity(
        call_http_mcp_tool,
        args=[mcp_ref.url, mcp_ref.transport, mcp_ref.headers, tool_name, tool_args],
        start_to_close_timeout=timedelta(seconds=60),
        retry_policy=_TOOL_RETRY,
    )
```

`call_http_mcp_tool` must be imported inside the `workflow.unsafe.imports_passed_through()` block alongside `call_mcp_tool`.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| `server: http` / `sse` entry with no `url` | Skipped in `parse_agentlet()`, warning logged |
| `server` value not in `{"stdio","http","sse"}` | Skipped, warning logged (existing behaviour) |
| HTTP/SSE server unreachable at startup | Server skipped, its tools not registered; warning logged |
| `api_key_env` set but env var missing | Header not added; warning logged |
| `${VAR}` placeholder with no matching env var | Resolves to empty string; warning logged |
| Tool call to unreachable HTTP/SSE server | Temporal retry policy applies (5 attempts) |

---

## Tests

New test cases in `tests/test_manifest.py`:

- `parse_agentlet` with `server: http` produces `HttpMCPToolSpec` with correct fields
- `parse_agentlet` with `server: sse` produces `HttpMCPToolSpec` with `transport="sse"`
- Entry with `server: http` but no `url` is skipped
- Mixed YAML (stdio + http + sse) produces the right mix of spec types

New test file `tests/test_activities.py` additions (or new file `tests/test_http_mcp.py`):

- `call_http_mcp_tool` with `transport="http"` calls `streamablehttp_client`
- `call_http_mcp_tool` with `transport="sse"` calls `sse_client`

New test cases in `tests/test_worker.py`:

- `_fetch_mcp_schemas` resolves `${VAR}` in headers from env
- `_fetch_mcp_schemas` applies `api_key_env` when no Authorization header present
- `_fetch_mcp_schemas` skips `api_key_env` injection when Authorization header already set
- `_fetch_mcp_schemas` logs warning and skips server on connection failure

---

## Out of Scope

- `tool_filters` (allowed/rejected) — defined in schema but not implemented for stdio either; separate feature
- `prefix` — same
- WebSocket transport (`mcp.client.websocket`) — not in schema
- Standard agentlet containers (non-durable path) — unaffected
