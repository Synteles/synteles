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

"""Integration tests for AgentWorkflow.run using Temporal's time-skipping test server.

Each test starts a lightweight local Temporal server (no real Temporal installation
required — the SDK bundles a test server binary) and exercises the full ReAct loop
with mock activities.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflow_config import AgentWorkflowConfig, HttpServerConfig, StdioServerConfig
from workflows.agent import AgentWorkflow

# ---------------------------------------------------------------------------
# Shared mock-activity factory helpers
# ---------------------------------------------------------------------------


def _base_config(
    stdio_tool_map: dict | None = None,
    http_tool_map: dict | None = None,
    tools_schema: list | None = None,
    output_url: str = "",
) -> AgentWorkflowConfig:
    return AgentWorkflowConfig(
        system_prompt="You are a test agent.",
        effective_prompt="Do the task.",
        model="openai/gpt-4o",
        tools_schema=tools_schema or [],
        output_url=output_url,
        stdio_tool_map=stdio_tool_map or {},
        http_tool_map=http_tool_map or {},
    )


def _final_answer_msg(text: str = "All done.") -> dict:
    return {"role": "assistant", "content": text, "tool_calls": None}


def _tool_call_msg(tool_name: str, arguments: dict, call_id: str = "tc1") -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": tool_name, "arguments": json.dumps(arguments)},
            }
        ],
    }


# ---------------------------------------------------------------------------
# Test: final answer on first LLM call (no tool calls)
# ---------------------------------------------------------------------------


async def test_workflow_run_returns_final_answer() -> None:
    """Workflow terminates and returns content when LLM gives no tool calls."""
    async with await WorkflowEnvironment.start_time_skipping() as env:

        @activity.defn(name="load_agent_config")
        async def mock_load_config() -> AgentWorkflowConfig:
            return _base_config()

        @activity.defn(name="call_llm_step")
        async def mock_llm(messages: list, tools: list, model: str) -> dict:
            return _final_answer_msg("The answer is 42.")

        @activity.defn(name="upload_output")
        async def mock_upload(output_url: str) -> None:
            pass

        @activity.defn(name="call_mcp_tool")
        async def mock_mcp(cmd: str, args: list, env: dict, name: str, arguments: dict) -> str:
            return ""

        @activity.defn(name="call_http_mcp_tool")
        async def mock_http_mcp(
            url: str, transport: str, headers: dict, name: str, arguments: dict
        ) -> str:
            return ""

        async with Worker(
            env.client,
            task_queue="test-q",
            workflows=[AgentWorkflow],
            activities=[mock_load_config, mock_llm, mock_upload, mock_mcp, mock_http_mcp],
        ):
            result = await env.client.execute_workflow(
                AgentWorkflow.run,
                "exec-001",
                id="wf-final-answer",
                task_queue="test-q",
            )

    assert result == "The answer is 42."


# ---------------------------------------------------------------------------
# Test: LLM calls a stdio MCP tool, then returns final answer
# ---------------------------------------------------------------------------


async def test_workflow_run_dispatches_stdio_mcp_tool() -> None:
    """Workflow calls call_mcp_tool when LLM returns a stdio-mapped tool call."""
    stdio_map = {"search_web": StdioServerConfig(command="search-server", args=[], env={})}
    tool_schema = [{"type": "function", "function": {"name": "search_web", "parameters": {}}}]

    llm_responses = [
        _tool_call_msg("search_web", {"query": "hello"}),
        _final_answer_msg("Found results."),
    ]
    mcp_call_log: list[str] = []

    async with await WorkflowEnvironment.start_time_skipping() as env:

        @activity.defn(name="load_agent_config")
        async def mock_load_config() -> AgentWorkflowConfig:
            return _base_config(stdio_tool_map=stdio_map, tools_schema=tool_schema)

        @activity.defn(name="call_llm_step")
        async def mock_llm(messages: list, tools: list, model: str) -> dict:
            return llm_responses.pop(0)

        @activity.defn(name="call_mcp_tool")
        async def mock_mcp(cmd: str, args: list, env: dict, name: str, arguments: dict) -> str:
            mcp_call_log.append(name)
            return "search result"

        @activity.defn(name="call_http_mcp_tool")
        async def mock_http_mcp(
            url: str, transport: str, headers: dict, name: str, arguments: dict
        ) -> str:
            return ""

        @activity.defn(name="upload_output")
        async def mock_upload(output_url: str) -> None:
            pass

        async with Worker(
            env.client,
            task_queue="test-q2",
            workflows=[AgentWorkflow],
            activities=[mock_load_config, mock_llm, mock_mcp, mock_http_mcp, mock_upload],
        ):
            result = await env.client.execute_workflow(
                AgentWorkflow.run,
                "exec-002",
                id="wf-stdio-tool",
                task_queue="test-q2",
            )

    assert result == "Found results."
    assert mcp_call_log == ["search_web"]


# ---------------------------------------------------------------------------
# Test: LLM calls an HTTP MCP tool, then returns final answer
# ---------------------------------------------------------------------------


async def test_workflow_run_dispatches_http_mcp_tool() -> None:
    """Workflow calls call_http_mcp_tool when LLM returns an http-mapped tool call."""
    http_map = {
        "get_contact": HttpServerConfig(
            url="http://crm:9000/mcp", transport="http", headers={"X-Key": "val"}
        )
    }
    tool_schema = [{"type": "function", "function": {"name": "get_contact", "parameters": {}}}]

    llm_responses = [
        _tool_call_msg("get_contact", {"id": "42"}),
        _final_answer_msg("Contact retrieved."),
    ]
    http_call_log: list[str] = []

    async with await WorkflowEnvironment.start_time_skipping() as env:

        @activity.defn(name="load_agent_config")
        async def mock_load_config() -> AgentWorkflowConfig:
            return _base_config(http_tool_map=http_map, tools_schema=tool_schema)

        @activity.defn(name="call_llm_step")
        async def mock_llm(messages: list, tools: list, model: str) -> dict:
            return llm_responses.pop(0)

        @activity.defn(name="call_http_mcp_tool")
        async def mock_http_mcp(
            url: str, transport: str, headers: dict, name: str, arguments: dict
        ) -> str:
            http_call_log.append(name)
            return "contact data"

        @activity.defn(name="call_mcp_tool")
        async def mock_mcp(cmd: str, args: list, env: dict, name: str, arguments: dict) -> str:
            return ""

        @activity.defn(name="upload_output")
        async def mock_upload(output_url: str) -> None:
            pass

        async with Worker(
            env.client,
            task_queue="test-q3",
            workflows=[AgentWorkflow],
            activities=[mock_load_config, mock_llm, mock_http_mcp, mock_mcp, mock_upload],
        ):
            result = await env.client.execute_workflow(
                AgentWorkflow.run,
                "exec-003",
                id="wf-http-tool",
                task_queue="test-q3",
            )

    assert result == "Contact retrieved."
    assert http_call_log == ["get_contact"]


# ---------------------------------------------------------------------------
# Test: LLM calls an unknown tool — error message is fed back
# ---------------------------------------------------------------------------


async def test_workflow_run_returns_error_for_unknown_tool() -> None:
    """Unknown tool name produces an error tool result and the LLM continues."""
    llm_responses = [
        _tool_call_msg("nonexistent_tool", {}),
        _final_answer_msg("I couldn't use that tool."),
    ]

    async with await WorkflowEnvironment.start_time_skipping() as env:

        @activity.defn(name="load_agent_config")
        async def mock_load_config() -> AgentWorkflowConfig:
            return _base_config()

        @activity.defn(name="call_llm_step")
        async def mock_llm(messages: list, tools: list, model: str) -> dict:
            return llm_responses.pop(0)

        @activity.defn(name="upload_output")
        async def mock_upload(output_url: str) -> None:
            pass

        @activity.defn(name="call_mcp_tool")
        async def mock_mcp(cmd: str, args: list, env: dict, name: str, arguments: dict) -> str:
            return ""

        @activity.defn(name="call_http_mcp_tool")
        async def mock_http_mcp(
            url: str, transport: str, headers: dict, name: str, arguments: dict
        ) -> str:
            return ""

        async with Worker(
            env.client,
            task_queue="test-q4",
            workflows=[AgentWorkflow],
            activities=[mock_load_config, mock_llm, mock_upload, mock_mcp, mock_http_mcp],
        ):
            result = await env.client.execute_workflow(
                AgentWorkflow.run,
                "exec-004",
                id="wf-unknown-tool",
                task_queue="test-q4",
            )

    assert result == "I couldn't use that tool."


# ---------------------------------------------------------------------------
# Test: update_output_url signal mid-workflow (ask_user HITL path)
# ---------------------------------------------------------------------------


async def test_workflow_run_ask_user_hitl_with_signal() -> None:
    """Workflow pauses on ask_user and resumes when provide_user_input signal arrives."""
    resumed: list[str] = []

    async with await WorkflowEnvironment.start_time_skipping() as env:

        @activity.defn(name="load_agent_config")
        async def mock_load_config() -> AgentWorkflowConfig:
            return _base_config()

        call_count = {"n": 0}

        @activity.defn(name="call_llm_step")
        async def mock_llm(messages: list, tools: list, model: str) -> dict:
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _tool_call_msg("ask_user", {"question_text": "Are you sure?"})
            resumed.append(messages[-1]["content"])
            return _final_answer_msg("Done after approval.")

        @activity.defn(name="upload_output")
        async def mock_upload(output_url: str) -> None:
            pass

        @activity.defn(name="call_mcp_tool")
        async def mock_mcp(cmd: str, args: list, env: dict, name: str, arguments: dict) -> str:
            return ""

        @activity.defn(name="call_http_mcp_tool")
        async def mock_http_mcp(
            url: str, transport: str, headers: dict, name: str, arguments: dict
        ) -> str:
            return ""

        async with Worker(
            env.client,
            task_queue="test-q5",
            workflows=[AgentWorkflow],
            activities=[mock_load_config, mock_llm, mock_upload, mock_mcp, mock_http_mcp],
        ):
            handle = await env.client.start_workflow(
                AgentWorkflow.run,
                "exec-005",
                id="wf-ask-user",
                task_queue="test-q5",
            )

            # Poll until the workflow is waiting for user input
            for _ in range(50):
                is_waiting: bool = await handle.query(AgentWorkflow.is_input_needed)
                if is_waiting:
                    break
                await asyncio.sleep(0.1)

            await handle.signal(AgentWorkflow.provide_user_input, "Approved!")
            result = await handle.result()

    assert result == "Done after approval."
    assert resumed == ["Approved!"]
