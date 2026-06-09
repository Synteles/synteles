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

"""Unit tests for the load_agent_config Temporal activity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.testing import ActivityEnvironment

from activities import load_agent_config
from workflow_config import AgentWorkflowConfig


def _make_spec(
    system_prompt: str = "You are helpful.",
    provider: str = "openai",
    model_id: str = "gpt-4o",
    mcp_tools: list | None = None,
) -> MagicMock:
    spec = MagicMock()
    spec.system_prompt = system_prompt
    spec.provider = provider
    spec.model_id = model_id
    spec.mcp_tools = mcp_tools or []
    return spec


# ---------------------------------------------------------------------------
# Error cases that fire before the first activity.heartbeat() call
# ---------------------------------------------------------------------------


async def test_load_agent_config_raises_when_manifest_url_missing() -> None:
    """RuntimeError when SYNTELES_MANIFEST_URL is not configured."""
    with patch("config.SYNTELES_MANIFEST_URL", ""):
        with pytest.raises(RuntimeError, match="SYNTELES_MANIFEST_URL"):
            await load_agent_config()


async def test_load_agent_config_raises_when_execution_id_missing() -> None:
    """RuntimeError when EXECUTION_ID is not configured."""
    with patch("config.EXECUTION_ID", ""):
        with pytest.raises(RuntimeError, match="EXECUTION_ID"):
            await load_agent_config()


# ---------------------------------------------------------------------------
# Cases that need an ActivityEnvironment (activity.heartbeat is called)
# ---------------------------------------------------------------------------


async def test_load_agent_config_raises_when_no_prompt() -> None:
    """RuntimeError when neither manifest prompt nor YAML default is set."""
    env = ActivityEnvironment()
    with (
        patch("manifest.fetch_manifest", new=AsyncMock(return_value={})),
        patch("manifest.parse_agentlet", return_value=_make_spec()),
        patch("manifest.resolve_prompt", return_value=""),
        patch("activities._fetch_mcp_schemas", new=AsyncMock(return_value=([], {}, {}))),
    ):
        with pytest.raises(RuntimeError, match="No prompt available"):
            await env.run(load_agent_config)


async def test_load_agent_config_returns_workflow_config() -> None:
    """Happy path: returns a fully-populated AgentWorkflowConfig."""
    env = ActivityEnvironment()
    manifest_data: dict = {"output_url": "https://bucket/out.zip"}

    with (
        patch("manifest.fetch_manifest", new=AsyncMock(return_value=manifest_data)),
        patch("manifest.parse_agentlet", return_value=_make_spec()),
        patch("manifest.resolve_prompt", return_value="Do the task"),
        patch("activities._fetch_mcp_schemas", new=AsyncMock(return_value=([], {}, {}))),
    ):
        result = await env.run(load_agent_config)

    assert isinstance(result, AgentWorkflowConfig)
    assert result.effective_prompt == "Do the task"
    assert result.model == "openai/gpt-4o"
    assert result.output_url == "https://bucket/out.zip"
    assert result.tools_schema == []


async def test_load_agent_config_uses_synteles_output_url_over_manifest() -> None:
    """SYNTELES_OUTPUT_URL env var takes precedence over manifest.output_url."""
    env = ActivityEnvironment()
    manifest_data: dict = {"output_url": "https://manifest/out.zip"}

    with (
        patch("config.SYNTELES_OUTPUT_URL", "https://env/out.zip"),
        patch("manifest.fetch_manifest", new=AsyncMock(return_value=manifest_data)),
        patch("manifest.parse_agentlet", return_value=_make_spec()),
        patch("manifest.resolve_prompt", return_value="task"),
        patch("activities._fetch_mcp_schemas", new=AsyncMock(return_value=([], {}, {}))),
    ):
        result = await env.run(load_agent_config)

    assert result.output_url == "https://env/out.zip"


async def test_load_agent_config_downloads_input_files_when_present() -> None:
    """When manifest contains input_files, _download_input_files is called."""
    env = ActivityEnvironment()
    manifest_data: dict = {"input_files": [{"name": "doc.pdf", "url": "http://store:9000/doc.pdf"}]}

    with (
        patch("manifest.fetch_manifest", new=AsyncMock(return_value=manifest_data)),
        patch("manifest.parse_agentlet", return_value=_make_spec()),
        patch("manifest.resolve_prompt", return_value="task"),
        patch("activities._fetch_mcp_schemas", new=AsyncMock(return_value=([], {}, {}))),
        patch("activities._download_input_files", new=AsyncMock()) as mock_download,
    ):
        await env.run(load_agent_config)

    mock_download.assert_called_once()
    _, trusted_netloc = mock_download.call_args[0][:2]
    assert trusted_netloc == "localhost"  # from SYNTELES_MANIFEST_URL in conftest


async def test_load_agent_config_system_prompt_passed_through() -> None:
    """The system_prompt field from the agentlet spec is preserved in the config."""
    env = ActivityEnvironment()

    with (
        patch("manifest.fetch_manifest", new=AsyncMock(return_value={})),
        patch(
            "manifest.parse_agentlet", return_value=_make_spec(system_prompt="You are a reviewer.")
        ),
        patch("manifest.resolve_prompt", return_value="Review this."),
        patch("activities._fetch_mcp_schemas", new=AsyncMock(return_value=([], {}, {}))),
    ):
        result = await env.run(load_agent_config)

    assert result.system_prompt == "You are a reviewer."
