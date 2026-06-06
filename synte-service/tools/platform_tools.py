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

"""Strands custom tools wrapping the Synteles Platform API.

All tools use ToolContext.invocation_state to receive the OIDC access token,
which must be passed at agent invocation time:
    agent(prompt, access_token=st.session_state["access_token"])
"""

from __future__ import annotations

import logging
import os
from typing import Any, cast

import requests
from strands import ToolContext, tool

log = logging.getLogger("synteles.ux.tools")

_API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.synteles.dev/v1")

_HTTP_200_OK = 200
_HTTP_400_BAD_REQUEST = 400
_DEFAULT_LIST_LIMIT = 50


class PlatformAPIError(Exception):
    """Raised when the Synteles Platform API returns an error."""


def _normalize_list(data: dict[str, Any] | list[dict[str, Any]], key: str) -> dict[str, Any]:
    """Normalize a list API response that may be a bare list or a paginated envelope."""
    if isinstance(data, list):
        return {key: data, "count": len(data), "next_token": None}  # nosec B105
    items = data.get(key, data.get("items", []))
    return {
        key: items,
        "count": data.get("count", len(items)),
        "next_token": data.get("next_token"),
    }


class PlatformTools:
    """Synteles Platform API tools for the Strands chat agent.

    Usage::

        tools = PlatformTools()
        agent = Agent(tools=[
            tools.get_current_user,
            tools.get_organization,
            tools.create_agentlet,
            ...
        ])
        agent(prompt, access_token=st.session_state["access_token"])
    """

    def __init__(self, api_base_url: str = _API_BASE_URL) -> None:
        self.api_base_url = api_base_url

    # ── Internal HTTP helper ──────────────────────────────────────────────────

    def _make_request(
        self,
        method: str,
        endpoint: str,
        access_token: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> requests.Response:
        if not access_token:
            raise PlatformAPIError("No access token available — user must be authenticated.")

        url = f"{self.api_base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                params=params,
                timeout=30,
            )
            if response.status_code >= _HTTP_400_BAD_REQUEST:
                error_msg = "Unknown error"
                if response.text:
                    try:
                        error_msg = response.json().get("error", response.text[:200])
                    except Exception:
                        error_msg = response.text[:200]
                raise PlatformAPIError(
                    f"API request failed (HTTP {response.status_code}): {error_msg}"
                )
            return response
        except requests.exceptions.RequestException as e:
            raise PlatformAPIError(f"Request failed: {e}") from e

    # ── User & Organization ───────────────────────────────────────────────────

    @tool(context=True)
    def get_current_user(self, tool_context: ToolContext) -> dict[str, Any]:
        """Get the authenticated user's profile including organization information.

        Returns the current user's OIDC user ID, email, name, and organization
        details (org_id, org_name) if they belong to one.
        """
        token = tool_context.invocation_state.get("access_token", "")
        response = self._make_request("GET", "/api/users/me", token)
        return cast(dict[str, Any], response.json())

    @tool(context=True)
    def get_organization(self, org_id: str, tool_context: ToolContext) -> dict[str, Any]:
        """Get organization metadata and list of member user IDs.

        Args:
            org_id: Organization UUID
        """
        token = tool_context.invocation_state.get("access_token", "")
        response = self._make_request("GET", f"/api/organizations/{org_id}", token)
        return cast(dict[str, Any], response.json())

    # ── Agentlet Management ───────────────────────────────────────────────────

    @tool(context=True)
    def create_agentlet(
        self,
        org_id: str,
        agentlet_id: str,
        tool_context: ToolContext,
        description: str | None = None,
        yaml_definition: str | None = None,
        execution_backend: str = "standard",
    ) -> dict[str, Any]:
        """Create a new agentlet in the organization.

        Args:
            org_id: Organization UUID
            agentlet_id: Unique identifier — must start with a letter or underscore,
                         contain only alphanumeric characters and underscores
            description: Optional human-readable description
            yaml_definition: Optional YAML configuration string
            execution_backend: Execution backend — 'standard' (default) or 'durable'.
                               'durable' enables checkpointing, retries, and HITL signals via Temporal.
        """
        token = tool_context.invocation_state.get("access_token", "")
        body: dict[str, Any] = {"id": agentlet_id, "execution_backend": execution_backend}
        if description is not None:
            body["description"] = description
        if yaml_definition is not None:
            body["YAML"] = yaml_definition
        response = self._make_request("POST", "/api/agentlets", token, json_data=body)
        return cast(dict[str, Any], response.json())

    @tool(context=True)
    def list_agentlets(
        self,
        org_id: str,
        tool_context: ToolContext,
        limit: int = _DEFAULT_LIST_LIMIT,
        next_token: str | None = None,
    ) -> dict[str, Any]:
        """List agentlets in the organization with pagination.

        Returns basic summaries without YAML content. Use get_agentlet() for full details.

        Args:
            org_id: Organization UUID
            limit: Maximum results per page (default: 50, max: 100)
            next_token: Pagination token from a previous response
        """
        token = tool_context.invocation_state.get("access_token", "")
        params: dict[str, str] = {}
        if limit != _DEFAULT_LIST_LIMIT:
            params["limit"] = str(limit)
        if next_token is not None:
            params["next_token"] = next_token
        response = self._make_request("GET", "/api/agentlets", token, params=params)
        return _normalize_list(
            cast(dict[str, Any] | list[dict[str, Any]], response.json()), "agentlets"
        )

    @tool(context=True)
    def get_agentlet(
        self, org_id: str, agentlet_id: str, tool_context: ToolContext
    ) -> dict[str, Any]:
        """Get the full agentlet definition including its YAML configuration.

        Args:
            org_id: Organization UUID
            agentlet_id: Agentlet identifier
        """
        token = tool_context.invocation_state.get("access_token", "")
        response = self._make_request("GET", f"/api/agentlets/{agentlet_id}", token)
        return cast(dict[str, Any], response.json())

    @tool(context=True)
    def update_agentlet(
        self,
        org_id: str,
        agentlet_id: str,
        tool_context: ToolContext,
        description: str | None = None,
        yaml_definition: str | None = None,
        execution_backend: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing agentlet's description, YAML configuration, and/or execution backend.

        Only the provided fields are updated; omitted fields are left unchanged.

        Args:
            org_id: Organization UUID
            agentlet_id: Agentlet identifier
            description: Updated description (optional)
            yaml_definition: Updated YAML configuration string (optional)
            execution_backend: Updated execution backend — 'standard' or 'durable' (optional)
        """
        token = tool_context.invocation_state.get("access_token", "")
        body: dict[str, str] = {}
        if description is not None:
            body["description"] = description
        if yaml_definition is not None:
            body["YAML"] = yaml_definition
        if execution_backend is not None:
            body["execution_backend"] = execution_backend
        response = self._make_request(
            "PATCH",
            f"/api/agentlets/{agentlet_id}",
            token,
            json_data=body,
        )
        return cast(dict[str, Any], response.json())

    # ── API Key Management ────────────────────────────────────────────────────

    @tool(context=True)
    def list_api_keys(
        self,
        tool_context: ToolContext,
        limit: int = _DEFAULT_LIST_LIMIT,
        next_token: str | None = None,
    ) -> dict[str, Any]:
        """List all API keys for the current user with pagination.

        Key values are never returned — only metadata (key_id, key_name, created_at,
        last_used).

        Args:
            limit: Maximum results per page (default: 50, max: 100)
            next_token: Pagination token from a previous response
        """
        token = tool_context.invocation_state.get("access_token", "")
        params: dict[str, str] = {}
        if limit != _DEFAULT_LIST_LIMIT:
            params["limit"] = str(limit)
        if next_token is not None:
            params["next_token"] = next_token
        response = self._make_request("GET", "/api/users/apikeys", token, params=params)
        return _normalize_list(
            cast(dict[str, Any] | list[dict[str, Any]], response.json()), "api_keys"
        )

    # ── Secrets ────────────────────────────────────────────────────

    @tool(context=True)
    def list_secrets(self, tool_context: ToolContext) -> dict[str, Any]:
        """List all secret names available to the current user (metadata only, no values).

        Returns secret names and descriptions. Secret values are never exposed via API.
        Use the returned names in the agentlet YAML 'secrets' list to inject credentials
        at execution time.
        """
        token = tool_context.invocation_state.get("access_token", "")
        response = self._make_request("GET", "/api/secrets", token)
        return cast(dict[str, Any], response.json())

    # ── Model Presets ─────────────────────────────────────────────────────────

    @tool(context=True)
    def list_model_presets(self, tool_context: ToolContext) -> dict[str, Any]:
        """List all model configuration presets for the current user.

        Returns a list of presets with name, description, provider, model_id,
        and optional secret_name. Call this at the start of agentlet creation
        to check if the user has saved model presets to offer as a shortcut.

        Returns:
            {"presets": [...], "count": N}
        """
        token = tool_context.invocation_state.get("access_token", "")
        try:
            response = self._make_request("GET", "/api/models", token)
            return _normalize_list(
                cast(dict[str, Any] | list[dict[str, Any]], response.json()), "presets"
            )
        except PlatformAPIError as e:
            return {"error": str(e)}

    # ── MCP Presets ───────────────────────────────────────────────────────────

    @tool(context=True)
    def list_mcp_presets(self, tool_context: ToolContext) -> dict[str, Any]:
        """List all MCP server configuration presets for the organization.

        Returns presets with name, description, and mcp_config.
        Call this before creating or updating an agentlet to ask the user
        which MCP presets they want to include.

        Returns:
            {"presets": [...], "count": N}
        """
        token = tool_context.invocation_state.get("access_token", "")
        try:
            response = self._make_request("GET", "/api/connectors", token)
            return _normalize_list(
                cast(dict[str, Any] | list[dict[str, Any]], response.json()), "presets"
            )
        except PlatformAPIError as e:
            return {"error": str(e)}

    @tool(context=True)
    def create_mcp_preset(
        self,
        name: str,
        mcp_config: str,
        tool_context: ToolContext,
        description: str = "",
    ) -> dict[str, Any]:
        """Create a new org-level MCP server configuration preset.

        Args:
            name: Preset identifier — letters, numbers, underscores only.
            mcp_config: Full MCP server config as JSON string with a top-level
                        'mcpServers' key, e.g.:
                        '{"mcpServers":{"my-server":{"command":"uvx","args":["my-mcp"]}}}'
            description: Optional human-readable description.

        Returns:
            Created preset data or {"error": "..."} on failure.
        """
        token = tool_context.invocation_state.get("access_token", "")
        payload: dict[str, Any] = {"name": name, "mcp_config": mcp_config}
        if description:
            payload["description"] = description
        try:
            response = self._make_request("POST", "/api/connectors", token, json_data=payload)
            return cast(dict[str, Any], response.json())
        except PlatformAPIError as e:
            return {"error": str(e)}

    # ── Execution Management ──────────────────────────────────────────────────

    @tool(context=True)
    def create_agentlet_execution(
        self,
        org_id: str,
        agentlet_id: str,
        tool_context: ToolContext,
        prompt: str | None = None,
        timeout: int = 900,
    ) -> dict[str, Any]:
        """Start a new agentlet execution (fire-and-forget async).

        Returns an execution_id immediately. Use get_execution_status() to poll progress
        and get_execution_logs() once the status reaches 'completed' or 'failed'.

        Args:
            org_id: Organization UUID — must match the authenticated user's organization
            agentlet_id: Agentlet identifier
            prompt: Optional task description injected as PROMPT env var in the container
            timeout: Maximum execution time in seconds (1–86400, default: 900)
        """
        token = tool_context.invocation_state.get("access_token", "")
        # Prefer the org_id injected from the authenticated session (invocation_state)
        # to prevent LLM hallucination. Falls back to the explicit parameter when not set.
        org_id = tool_context.invocation_state.get("org_id") or org_id
        pending_files: list[str] = tool_context.invocation_state.get("pending_input_objects") or []
        body: dict[str, Any] = {"agentlet_id": agentlet_id, "timeout": timeout}
        if prompt is not None:
            body["prompt"] = prompt
        if pending_files:
            body["input_objects"] = pending_files
        response = self._make_request(
            "POST",
            "/api/executions",
            token,
            json_data=body,
        )
        return cast(dict[str, Any], response.json())

    @tool(context=True)
    def get_execution_status(self, execution_id: str, tool_context: ToolContext) -> dict[str, Any]:
        """Get the current status and metadata of an agentlet execution.

        Status lifecycle: deploying → running → completed / failed / terminated

        Args:
            execution_id: Execution UUID
        """
        token = tool_context.invocation_state.get("access_token", "")
        response = self._make_request("GET", f"/api/executions/{execution_id}", token)
        return cast(dict[str, Any], response.json())

    @tool(context=True)
    def get_execution_logs(
        self,
        execution_id: str,
        tool_context: ToolContext,
        log_format: str = "json",
    ) -> dict[str, Any]:
        """Retrieve execution logs from S3 storage.

        Logs are only available after execution reaches 'completed' or 'failed' status.
        Returns logs_available=false with a 202 status if execution is still running.

        Args:
            execution_id: Execution UUID
            log_format: Response format — "json" (parsed log entries) or "text"
                        (raw log text), default: "json"
        """
        token = tool_context.invocation_state.get("access_token", "")
        params: dict[str, str] = {}
        if log_format != "json":
            params["format"] = log_format
        response = self._make_request(
            "GET", f"/api/executions/{execution_id}/logs", token, params=params
        )
        if log_format == "text" and response.status_code == _HTTP_200_OK:
            return {
                "execution_id": execution_id,
                "status": response.headers.get("X-Execution-Status", "unknown"),
                "logs_available": True,
                "s3_uri": response.headers.get("X-S3-Uri", ""),
                "logs_text": response.text,
            }
        return cast(dict[str, Any], response.json())

    @tool(context=True)
    def get_execution_files(self, execution_id: str, tool_context: ToolContext) -> dict[str, Any]:
        """List input files and check for output archive for a completed execution.

        Returns presigned download URLs for input files and output.zip (if it exists).
        Call this when the user asks for execution results, before retrieving logs.

        Args:
            execution_id: Execution UUID

        Returns:
            {
                "execution_id": str,
                "input_files": [{"name": str, "size": int, "download_url": str}],
                "output_zip": {"exists": bool, "download_url": str | None}
            }
        """
        token = tool_context.invocation_state.get("access_token", "")
        response = self._make_request("GET", f"/api/executions/{execution_id}/files", token)
        return cast(dict[str, Any], response.json())

    @tool(context=True)
    def terminate_execution(self, execution_id: str, tool_context: ToolContext) -> dict[str, Any]:
        """Terminate a running agentlet execution.

        If the execution is already completed/failed/terminated, only the database
        status is updated.

        Args:
            execution_id: Execution UUID
        """
        token = tool_context.invocation_state.get("access_token", "")
        response = self._make_request("DELETE", f"/api/executions/{execution_id}", token)
        return cast(dict[str, Any], response.json())

    @tool(context=True)
    def list_executions(
        self,
        tool_context: ToolContext,
        agentlet_id: str | None = None,
        status: str | None = None,
        created_at_start: str | None = None,
        created_at_end: str | None = None,
        completed_at_start: str | None = None,
        completed_at_end: str | None = None,
        limit: int = _DEFAULT_LIST_LIMIT,
        next_token: str | None = None,
    ) -> dict[str, Any]:
        """List executions for the user's organization with optional filtering and pagination.

        Args:
            agentlet_id: Filter by agentlet identifier (optional)
            status: Filter by status — deploying, running, completed, failed, terminated
                    (optional)
            created_at_start: Filter by creation date start, ISO 8601 inclusive (optional)
            created_at_end: Filter by creation date end, ISO 8601 inclusive (optional)
            completed_at_start: Filter by completion date start, ISO 8601 inclusive (optional)
            completed_at_end: Filter by completion date end, ISO 8601 inclusive (optional)
            limit: Maximum results per page (default: 50, max: 100)
            next_token: Pagination token from a previous response
        """
        token = tool_context.invocation_state.get("access_token", "")
        params: dict[str, str] = {}
        if agentlet_id is not None:
            params["agentlet_id"] = agentlet_id
        if status is not None:
            params["status"] = status
        if created_at_start is not None:
            params["created_at_start"] = created_at_start
        if created_at_end is not None:
            params["created_at_end"] = created_at_end
        if completed_at_start is not None:
            params["completed_at_start"] = completed_at_start
        if completed_at_end is not None:
            params["completed_at_end"] = completed_at_end
        if limit != _DEFAULT_LIST_LIMIT:
            params["limit"] = str(limit)
        if next_token is not None:
            params["next_token"] = next_token
        response = self._make_request("GET", "/api/executions", token, params=params)
        return cast(dict[str, Any], response.json())

    # ── Model selection ───────────────────────────────────────────────────────

    @tool
    def get_model_options(
        self,
        use_case: str | None = None,
    ) -> dict[str, Any]:
        """Return platform default models available for agentlet creation.

        Always call this in parallel with list_model_presets() when the user is
        creating or updating an agentlet and has not specified a model. Present
        platform defaults and user presets as a unified numbered list.

        Args:
            use_case: Short description of what the agentlet will do, e.g.
                      "code review", "data analysis", "web research".
                      Used to select the recommended option.

        Returns:
            {
              "options": [
                {
                  "id": str,                 # stable key for selection
                  "label": str,              # display name shown to user
                  "provider": str,           # LiteLLM provider
                  "model_id": str,
                  "secret": "default",       # always "default" for platform models
                  "default_temperature": float,
                  "description": str,
                  "is_platform_default": True,
                  "recommended": bool,
                }
              ],
              "recommended_id": str,
              "recommendation_reason": str,
            }
        """
        from .model_catalog import PLATFORM_DEFAULT_MODELS

        use_case_lower = (use_case or "").lower()

        options: list[dict[str, Any]] = []
        for model in PLATFORM_DEFAULT_MODELS:
            score = sum(1 for kw in model.get("best_for", []) if kw in use_case_lower)
            options.append(
                {
                    "id": model["id"],
                    "label": f"{model['label']} ✦ platform default",
                    "provider": model["provider"],
                    "model_id": model["model_id"],
                    "secret": model["secret_literal"],
                    "default_temperature": model["default_temperature"],
                    "description": model.get("description", ""),
                    "is_platform_default": True,
                    "recommended": False,
                    "_score": score,
                }
            )

        best = max(options, key=lambda o: (o["_score"], 1))
        best["recommended"] = True

        for o in options:
            o.pop("_score", None)

        _reason_map = {
            "platform_deepseek": "Strong reasoning model — well suited for this use case.",
            "platform_qwen3": "Large multilingual model — well suited for this use case.",
            "platform_gpt53": "Fast general-purpose model — solid default choice.",
        }
        reason = _reason_map.get(best["id"], "Recommended based on your use case.")

        return {
            "options": options,
            "recommended_id": best["id"],
            "recommendation_reason": reason,
        }
