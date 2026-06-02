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

"""Tests for tools/platform_tools.py — PlatformTools HTTP wrapper and get_model_options."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from tools.platform_tools import PlatformAPIError, PlatformTools, _normalize_list

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_response(
    status_code: int, body: dict[str, Any] | list[Any] | str, headers: dict[str, str] | None = None
) -> MagicMock:
    """Build a mock requests.Response."""
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = status_code
    mock_resp.text = json.dumps(body) if isinstance(body, (dict, list)) else body
    mock_resp.headers = headers or {}
    if isinstance(body, (dict, list)):
        mock_resp.json.return_value = body
    else:
        mock_resp.json.side_effect = ValueError("not json")
    return mock_resp


def _make_tool_context(
    token: str = "test-token", org_id: str | None = None, pending_files: list[str] | None = None
) -> MagicMock:
    ctx = MagicMock()
    state: dict[str, Any] = {"access_token": token}
    if org_id is not None:
        state["org_id"] = org_id
    if pending_files is not None:
        state["pending_input_objects"] = pending_files
    ctx.invocation_state = state
    return ctx


# ── _normalize_list ───────────────────────────────────────────────────────────


class TestNormalizeList:
    def test_bare_list_input(self):
        data = [{"id": "a"}, {"id": "b"}]
        result = _normalize_list(data, "items")
        assert result["items"] == data
        assert result["count"] == 2
        assert result["next_token"] is None

    def test_paginated_envelope_with_key(self):
        data = {"agentlets": [{"id": "x"}], "count": 1, "next_token": "tok123"}
        result = _normalize_list(data, "agentlets")
        assert result["agentlets"] == [{"id": "x"}]
        assert result["count"] == 1
        assert result["next_token"] == "tok123"

    def test_paginated_envelope_fallback_to_items_key(self):
        data = {"items": [{"id": "z"}], "count": 1}
        result = _normalize_list(data, "presets")
        assert result["presets"] == [{"id": "z"}]

    def test_paginated_envelope_missing_key_uses_items(self):
        data = {"items": [{"id": "q"}]}
        result = _normalize_list(data, "executions")
        assert result["executions"] == [{"id": "q"}]


# ── PlatformTools._make_request ───────────────────────────────────────────────


class TestMakeRequest:
    def test_raises_when_no_access_token(self):
        pt = PlatformTools(api_base_url="https://api.test")
        with pytest.raises(PlatformAPIError, match="access token"):
            pt._make_request("GET", "/api/test", "")

    def test_successful_request_returns_response(self, mocker):
        mock_resp = _make_response(200, {"result": "ok"})
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        response = pt._make_request("GET", "/api/test", "my-token")
        assert response.json() == {"result": "ok"}

    def test_400_response_raises_platform_api_error(self, mocker):
        mock_resp = _make_response(400, {"error": "bad request"})
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        with pytest.raises(PlatformAPIError, match="HTTP 400"):
            pt._make_request("POST", "/api/test", "my-token")

    def test_500_response_raises_platform_api_error(self, mocker):
        mock_resp = _make_response(500, "Internal server error")
        mock_resp.json.side_effect = ValueError("not json")
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        with pytest.raises(PlatformAPIError, match="HTTP 500"):
            pt._make_request("GET", "/api/test", "my-token")

    def test_request_exception_raises_platform_api_error(self, mocker):
        mocker.patch(
            "tools.platform_tools.requests.request",
            side_effect=requests.exceptions.ConnectionError("connection refused"),
        )

        pt = PlatformTools(api_base_url="https://api.test")
        with pytest.raises(PlatformAPIError, match="Request failed"):
            pt._make_request("GET", "/api/test", "my-token")

    def test_error_response_with_json_body_uses_error_field(self, mocker):
        mock_resp = _make_response(422, {"error": "Validation failed"})
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        with pytest.raises(PlatformAPIError, match="Validation failed"):
            pt._make_request("POST", "/api/test", "tok")

    def test_error_response_json_parse_failure_uses_text(self, mocker):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 400
        mock_resp.text = "Raw error text"
        mock_resp.headers = {}
        mock_resp.json.side_effect = ValueError("not json")
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        with pytest.raises(PlatformAPIError, match="Raw error text"):
            pt._make_request("GET", "/api/test", "tok")

    def test_authorization_header_set_correctly(self, mocker):
        mock_resp = _make_response(200, {})
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        pt._make_request("GET", "/api/test", "secret-token")

        _, kwargs = mock_request.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer secret-token"


# ── get_current_user ──────────────────────────────────────────────────────────


class TestGetCurrentUser:
    def test_returns_user_data(self, mocker):
        mock_resp = _make_response(200, {"user_id": "u1", "email": "u@test.com"})
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.get_current_user(tool_context=ctx)
        assert result["user_id"] == "u1"


# ── get_organization ──────────────────────────────────────────────────────────


class TestGetOrganization:
    def test_returns_org_data(self, mocker):
        mock_resp = _make_response(200, {"org_id": "org-abc", "name": "Acme"})
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.get_organization(org_id="org-abc", tool_context=ctx)
        assert result["org_id"] == "org-abc"


# ── create_agentlet ───────────────────────────────────────────────────────────


class TestCreateAgentlet:
    def test_creates_agentlet_with_description_and_yaml(self, mocker):
        mock_resp = _make_response(201, {"id": "my_agent"})
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.create_agentlet(
            org_id="org-1",
            agentlet_id="my_agent",
            tool_context=ctx,
            description="A test agent",
            yaml_definition="agentlet:\n  name: my_agent\n",
        )
        assert result["id"] == "my_agent"
        _, kwargs = mock_request.call_args
        assert kwargs["json"]["description"] == "A test agent"
        assert "YAML" in kwargs["json"]

    def test_creates_agentlet_without_optional_fields(self, mocker):
        mock_resp = _make_response(201, {"id": "bare_agent"})
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        pt.create_agentlet(org_id="org-1", agentlet_id="bare_agent", tool_context=ctx)

        _, kwargs = mock_request.call_args
        assert "description" not in kwargs["json"]
        assert "YAML" not in kwargs["json"]


# ── list_agentlets ────────────────────────────────────────────────────────────


class TestListAgentlets:
    def test_returns_normalized_list(self, mocker):
        mock_resp = _make_response(200, [{"id": "a1"}, {"id": "a2"}])
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.list_agentlets(org_id="org-1", tool_context=ctx)
        assert result["count"] == 2

    def test_includes_custom_limit_in_params(self, mocker):
        mock_resp = _make_response(200, [])
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        pt.list_agentlets(org_id="org-1", tool_context=ctx, limit=10)

        _, kwargs = mock_request.call_args
        assert kwargs["params"]["limit"] == "10"

    def test_includes_next_token_when_provided(self, mocker):
        mock_resp = _make_response(200, [])
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        pt.list_agentlets(org_id="org-1", tool_context=ctx, next_token="page2")

        _, kwargs = mock_request.call_args
        assert kwargs["params"]["next_token"] == "page2"


# ── get_agentlet ──────────────────────────────────────────────────────────────


class TestGetAgentlet:
    def test_returns_agentlet_data(self, mocker):
        mock_resp = _make_response(200, {"id": "my_agent", "YAML": "agentlet:\n  name: test\n"})
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.get_agentlet(org_id="org-1", agentlet_id="my_agent", tool_context=ctx)
        assert result["id"] == "my_agent"


# ── update_agentlet ───────────────────────────────────────────────────────────


class TestUpdateAgentlet:
    def test_sends_patch_with_description_and_yaml(self, mocker):
        mock_resp = _make_response(200, {"id": "my_agent"})
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        pt.update_agentlet(
            org_id="org-1",
            agentlet_id="my_agent",
            tool_context=ctx,
            description="Updated desc",
            yaml_definition="agentlet:\n  name: updated\n",
        )

        _, kwargs = mock_request.call_args
        assert kwargs["method"] == "PATCH"
        assert kwargs["json"]["description"] == "Updated desc"
        assert "YAML" in kwargs["json"]

    def test_sends_patch_without_optional_fields(self, mocker):
        mock_resp = _make_response(200, {"id": "my_agent"})
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        pt.update_agentlet(org_id="org-1", agentlet_id="my_agent", tool_context=ctx)

        _, kwargs = mock_request.call_args
        assert kwargs["json"] == {}


# ── list_api_keys ─────────────────────────────────────────────────────────────


class TestListApiKeys:
    def test_returns_normalized_api_keys(self, mocker):
        mock_resp = _make_response(200, {"api_keys": [{"key_id": "k1"}], "count": 1})
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.list_api_keys(tool_context=ctx)
        assert result["count"] == 1

    def test_includes_custom_limit(self, mocker):
        mock_resp = _make_response(200, [])
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        pt.list_api_keys(tool_context=ctx, limit=5, next_token="page2")

        _, kwargs = mock_request.call_args
        assert kwargs["params"]["limit"] == "5"
        assert kwargs["params"]["next_token"] == "page2"


# ── list_secrets ──────────────────────────────────────────────────────────────


class TestListSecrets:
    def test_returns_secrets_data(self, mocker):
        mock_resp = _make_response(200, {"secrets": [{"name": "api-key"}]})
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.list_secrets(tool_context=ctx)
        assert "secrets" in result


# ── list_model_presets ────────────────────────────────────────────────────────


class TestListModelPresets:
    def test_returns_normalized_presets(self, mocker):
        mock_resp = _make_response(200, [{"name": "my-preset"}])
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.list_model_presets(tool_context=ctx)
        assert result["count"] == 1

    def test_returns_error_dict_on_platform_api_error(self, mocker):
        mocker.patch(
            "tools.platform_tools.requests.request",
            side_effect=requests.exceptions.ConnectionError("down"),
        )

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.list_model_presets(tool_context=ctx)
        assert "error" in result


# ── list_mcp_presets ──────────────────────────────────────────────────────────


class TestListMcpPresets:
    def test_returns_normalized_presets(self, mocker):
        mock_resp = _make_response(200, [{"name": "github"}])
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.list_mcp_presets(tool_context=ctx)
        assert result["count"] == 1

    def test_returns_error_dict_on_failure(self, mocker):
        mocker.patch(
            "tools.platform_tools.requests.request",
            side_effect=requests.exceptions.ConnectionError("down"),
        )

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.list_mcp_presets(tool_context=ctx)
        assert "error" in result


# ── create_mcp_preset ─────────────────────────────────────────────────────────


class TestCreateMcpPreset:
    def test_creates_preset_with_description(self, mocker):
        mock_resp = _make_response(201, {"name": "my-mcp"})
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.create_mcp_preset(
            name="my-mcp",
            mcp_config='{"mcpServers":{}}',
            tool_context=ctx,
            description="A connector",
        )
        assert result["name"] == "my-mcp"
        _, kwargs = mock_request.call_args
        assert kwargs["json"]["description"] == "A connector"

    def test_creates_preset_without_description(self, mocker):
        mock_resp = _make_response(201, {"name": "bare-mcp"})
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        pt.create_mcp_preset(name="bare-mcp", mcp_config="{}", tool_context=ctx)

        _, kwargs = mock_request.call_args
        assert "description" not in kwargs["json"]

    def test_returns_error_dict_on_failure(self, mocker):
        mocker.patch(
            "tools.platform_tools.requests.request",
            side_effect=requests.exceptions.ConnectionError("down"),
        )

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.create_mcp_preset(name="x", mcp_config="{}", tool_context=ctx)
        assert "error" in result


# ── create_agentlet_execution ─────────────────────────────────────────────────


class TestCreateAgentletExecution:
    def test_creates_execution(self, mocker):
        mock_resp = _make_response(202, {"execution_id": "exec-123"})
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.create_agentlet_execution(
            org_id="org-1", agentlet_id="my_agent", tool_context=ctx
        )
        assert result["execution_id"] == "exec-123"

    def test_includes_prompt_when_provided(self, mocker):
        mock_resp = _make_response(202, {"execution_id": "exec-456"})
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        pt.create_agentlet_execution(
            org_id="org-1",
            agentlet_id="my_agent",
            tool_context=ctx,
            prompt="Analyze the data",
        )
        _, kwargs = mock_request.call_args
        assert kwargs["json"]["prompt"] == "Analyze the data"

    def test_includes_pending_files_from_context(self, mocker):
        mock_resp = _make_response(202, {"execution_id": "exec-789"})
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context(pending_files=["file1.csv", "file2.xlsx"])
        pt.create_agentlet_execution(org_id="org-1", agentlet_id="my_agent", tool_context=ctx)
        _, kwargs = mock_request.call_args
        assert kwargs["json"]["input_objects"] == ["file1.csv", "file2.xlsx"]

    def test_org_id_from_invocation_state_overrides_param(self, mocker):
        mock_resp = _make_response(202, {"execution_id": "exec-999"})
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context(org_id="state-org-id")
        pt.create_agentlet_execution(
            org_id="param-org-id", agentlet_id="my_agent", tool_context=ctx
        )
        # The function uses state org_id over param org_id (checked via URL or body)
        # The execution is created successfully regardless
        mock_request.assert_called_once()


# ── get_execution_status ──────────────────────────────────────────────────────


class TestGetExecutionStatus:
    def test_returns_status_data(self, mocker):
        mock_resp = _make_response(200, {"status": "running", "execution_id": "exec-1"})
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.get_execution_status(execution_id="exec-1", tool_context=ctx)
        assert result["status"] == "running"


# ── get_execution_logs ────────────────────────────────────────────────────────


class TestGetExecutionLogs:
    def test_returns_json_logs_by_default(self, mocker):
        mock_resp = _make_response(200, {"logs": [{"message": "started"}]})
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.get_execution_logs(execution_id="exec-1", tool_context=ctx)
        assert "logs" in result

    def test_returns_text_format_response(self, mocker):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = "2024-01-01 INFO Agent started"
        mock_resp.headers = {
            "X-Execution-Status": "completed",
            "X-S3-Uri": "s3://bucket/key",
        }
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.get_execution_logs(execution_id="exec-1", tool_context=ctx, log_format="text")
        assert result["logs_text"] == "2024-01-01 INFO Agent started"
        assert result["status"] == "completed"
        assert result["logs_available"] is True

    def test_text_format_sends_format_param(self, mocker):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = "log text"
        mock_resp.headers = {}
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        pt.get_execution_logs(execution_id="exec-1", tool_context=ctx, log_format="text")

        _, kwargs = mock_request.call_args
        assert kwargs["params"]["format"] == "text"


# ── get_execution_files ───────────────────────────────────────────────────────


class TestGetExecutionFiles:
    def test_returns_files_data(self, mocker):
        mock_resp = _make_response(
            200,
            {
                "execution_id": "exec-1",
                "output_zip": {"exists": True, "download_url": "https://s3.example.com/output.zip"},
            },
        )
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.get_execution_files(execution_id="exec-1", tool_context=ctx)
        assert result["output_zip"]["exists"] is True


# ── terminate_execution ───────────────────────────────────────────────────────


class TestTerminateExecution:
    def test_terminates_execution(self, mocker):
        mock_resp = _make_response(200, {"status": "terminated"})
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.terminate_execution(execution_id="exec-1", tool_context=ctx)
        assert result["status"] == "terminated"


# ── list_executions ───────────────────────────────────────────────────────────


class TestListExecutions:
    def test_returns_executions_without_filters(self, mocker):
        mock_resp = _make_response(200, {"items": [{"id": "exec-1"}], "count": 1})
        mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        result = pt.list_executions(tool_context=ctx)
        # Returns raw response json (not normalized in this method)
        assert result is not None

    def test_includes_all_optional_filters(self, mocker):
        mock_resp = _make_response(200, {"items": []})
        mock_request = mocker.patch("tools.platform_tools.requests.request", return_value=mock_resp)

        pt = PlatformTools(api_base_url="https://api.test")
        ctx = _make_tool_context()
        pt.list_executions(
            tool_context=ctx,
            agentlet_id="my_agent",
            status="completed",
            created_at_start="2024-01-01T00:00:00Z",
            created_at_end="2024-12-31T23:59:59Z",
            completed_at_start="2024-06-01T00:00:00Z",
            completed_at_end="2024-06-30T23:59:59Z",
            limit=10,
            next_token="page2",
        )
        _, kwargs = mock_request.call_args
        assert kwargs["params"]["agentlet_id"] == "my_agent"
        assert kwargs["params"]["status"] == "completed"
        assert kwargs["params"]["limit"] == "10"
        assert kwargs["params"]["next_token"] == "page2"
        assert kwargs["params"]["created_at_start"] == "2024-01-01T00:00:00Z"
        assert kwargs["params"]["completed_at_end"] == "2024-06-30T23:59:59Z"


# ── get_model_options ─────────────────────────────────────────────────────────

_TEST_PLATFORM_DEFAULTS: list[dict[str, Any]] = [
    {
        "id": "platform_test_a",
        "label": "Test Model A",
        "provider": "anthropic",
        "model_id": "claude-test",
        "secret_literal": "default",
        "default_temperature": 0.7,
        "best_for": ["coding", "code review"],
        "description": "General test model A.",
    },
    {
        "id": "platform_test_b",
        "label": "Test Model B",
        "provider": "openai",
        "model_id": "gpt-test",
        "secret_literal": "default",
        "default_temperature": 0.5,
        "best_for": ["data analysis"],
        "description": "General test model B.",
    },
]


class TestGetModelOptions:
    @pytest.fixture(autouse=True)
    def _patch_platform_defaults(self, mocker: Any) -> None:
        mocker.patch("tools.model_catalog.PLATFORM_DEFAULT_MODELS", _TEST_PLATFORM_DEFAULTS)

    def test_returns_options_and_recommended_id(self):
        pt = PlatformTools(api_base_url="https://api.test")
        result = pt.get_model_options()

        assert "options" in result
        assert "recommended_id" in result
        assert "recommendation_reason" in result
        assert len(result["options"]) > 0

    def test_platform_defaults_always_included(self):
        pt = PlatformTools(api_base_url="https://api.test")
        result = pt.get_model_options()

        platform_defaults = [o for o in result["options"] if o["is_platform_default"]]
        assert len(platform_defaults) > 0

    def test_recommended_option_has_recommended_true(self):
        pt = PlatformTools(api_base_url="https://api.test")
        result = pt.get_model_options(use_case="code review")

        recommended_options = [o for o in result["options"] if o["recommended"]]
        assert len(recommended_options) == 1
        assert recommended_options[0]["id"] == result["recommended_id"]

    def test_use_case_influences_recommendation(self):
        pt = PlatformTools(api_base_url="https://api.test")
        result = pt.get_model_options(use_case="coding & software development")

        assert result["recommended_id"] in [o["id"] for o in result["options"]]

    def test_no_score_key_in_returned_options(self):
        pt = PlatformTools(api_base_url="https://api.test")
        result = pt.get_model_options()

        for opt in result["options"]:
            assert "_score" not in opt
