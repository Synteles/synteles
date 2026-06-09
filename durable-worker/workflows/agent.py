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

"""AgentWorkflow — durable LiteLLM ReAct loop with human-in-the-loop support.

Configuration is loaded via the load_agent_config activity as the very first
workflow step, ensuring replay determinism (C1). The upload_output call is
guarded by try/finally + asyncio.shield so it always runs and cannot be
interrupted by cancellation (C2). All execute_activity calls include
heartbeat_timeout so Temporal can detect dead workers (C3).

Tool routing:
  ask_user  → HITL signal pause (workflow waits for provide_user_input signal)
  MCP tools → call_mcp_tool / call_http_mcp_tool activity, one per call
  unknown   → logged and reported back to the LLM as an error string
"""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities import call_http_mcp_tool, load_agent_config, call_llm_step, call_mcp_tool, upload_output
    from workflow_config import AgentWorkflowConfig, HttpServerConfig, StdioServerConfig

_ASK_USER_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": "Ask the human a question when clarification or approval is needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "question_text": {
                    "type": "string",
                    "description": "The question or approval request to present to the user.",
                }
            },
            "required": ["question_text"],
        },
    },
}

# Retry policies are intentionally generous to survive worker container restarts.
# A dead container causes activity failures; the monitor detects this and can
# restart the container (Option 2). Until then, Temporal keeps retrying.
# Budget: 30s → 60s → 120s → 120s … capped, giving ~10+ minutes before giving up.
_LLM_RETRY = RetryPolicy(
    maximum_attempts=10,
    initial_interval=timedelta(seconds=30),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=120),
)
_TOOL_RETRY = RetryPolicy(
    maximum_attempts=5,
    initial_interval=timedelta(seconds=30),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=120),
)
_UPLOAD_RETRY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
)


@workflow.defn
class AgentWorkflow:
    def __init__(self) -> None:
        self._input_needed: bool = False
        self._question: str = ""
        self._user_input: str = ""
        self._last_message: str = ""
        self._config: AgentWorkflowConfig | None = None
        self._output_url: str = ""

    @workflow.run
    async def run(self, execution_id: str) -> str:
        # C1: Load all config via activity so the result is in event history,
        # making replay fully deterministic.
        self._config = await workflow.execute_activity(
            load_agent_config,
            start_to_close_timeout=timedelta(seconds=300),
            heartbeat_timeout=timedelta(seconds=30),
            retry_policy=_LLM_RETRY,
        )
        self._output_url = self._config.output_url

        messages: list[dict] = []
        if self._config.system_prompt:
            messages.append({"role": "system", "content": self._config.system_prompt})
        messages.append({"role": "user", "content": self._config.effective_prompt})

        tools = [_ASK_USER_TOOL] + self._config.tools_schema
        result: str = ""

        # C2: try/finally ensures upload_output always runs (normal completion,
        # failure, and cancellation). asyncio.shield prevents the upload activity
        # itself from being cancelled if the workflow is being cancelled.
        try:
            while True:
                assistant_msg = await workflow.execute_activity(
                    call_llm_step,
                    args=[messages, tools, self._config.model],
                    start_to_close_timeout=timedelta(seconds=120),
                    heartbeat_timeout=timedelta(seconds=30),  # C3
                    retry_policy=_LLM_RETRY,
                )
                messages.append(assistant_msg)
                if assistant_msg.get("content"):
                    self._last_message = assistant_msg["content"]

                tool_calls = assistant_msg.get("tool_calls")
                if not tool_calls:
                    workflow.logger.info("[%s] final answer", execution_id)
                    result = assistant_msg.get("content") or ""
                    break

                for tool_call in tool_calls:
                    tool_name: str = tool_call["function"]["name"]
                    tool_args: dict = json.loads(tool_call["function"]["arguments"])
                    tool_call_id: str = tool_call["id"]
                    workflow.logger.info("[%s] tool call: %s", execution_id, tool_name)

                    if tool_name == "ask_user":
                        self._question = tool_args.get("question_text", "")
                        self._input_needed = True
                        workflow.logger.info(
                            "[%s] waiting for user input: %s", execution_id, self._question
                        )
                        await workflow.wait_condition(lambda: not self._input_needed)
                        workflow.logger.info("[%s] resumed", execution_id)
                        tool_result: str = self._user_input
                        self._user_input = ""
                        self._question = ""

                    else:
                        stdio_ref = self._config.stdio_tool_map.get(tool_name)
                        http_ref = self._config.http_tool_map.get(tool_name)
                        if stdio_ref:
                            tool_result = await workflow.execute_activity(
                                call_mcp_tool,
                                args=[
                                    stdio_ref.command,
                                    stdio_ref.args,
                                    stdio_ref.env,
                                    tool_name,
                                    tool_args,
                                ],
                                start_to_close_timeout=timedelta(seconds=60),
                                heartbeat_timeout=timedelta(seconds=30),  # C3
                                retry_policy=_TOOL_RETRY,
                            )
                        elif http_ref:
                            tool_result = await workflow.execute_activity(
                                call_http_mcp_tool,
                                args=[
                                    http_ref.url,
                                    http_ref.transport,
                                    http_ref.headers,
                                    tool_name,
                                    tool_args,
                                ],
                                start_to_close_timeout=timedelta(seconds=60),
                                heartbeat_timeout=timedelta(seconds=30),  # C3
                                retry_policy=_TOOL_RETRY,
                            )
                        else:
                            tool_result = f"Error: unknown tool '{tool_name}'"
                            workflow.logger.warning(
                                "[%s] unknown tool '%s'", execution_id, tool_name
                            )

                    messages.append(
                        {"role": "tool", "tool_call_id": tool_call_id, "content": tool_result}
                    )
        finally:
            try:
                await asyncio.shield(
                    workflow.execute_activity(
                        upload_output,
                        args=[self._output_url],
                        start_to_close_timeout=timedelta(seconds=300),
                        heartbeat_timeout=timedelta(seconds=30),  # C3
                        retry_policy=_UPLOAD_RETRY,
                    )
                )
            except Exception as upload_exc:
                workflow.logger.warning(
                    "[%s] output upload failed: %s", execution_id, upload_exc
                )

        return result

    @workflow.signal
    def provide_user_input(self, user_input: str) -> None:
        """Deliver the user's response to a pending ask_user call."""
        self._user_input = user_input
        self._input_needed = False

    @workflow.signal
    def update_output_url(self, new_url: str) -> None:
        """Refresh the presigned S3 output URL (sent by the scheduler on signal delivery)."""
        self._output_url = new_url

    @workflow.query
    def is_input_needed(self) -> bool:
        return self._input_needed

    @workflow.query
    def get_pending_question(self) -> str:
        return self._question

    @workflow.query
    def get_last_message(self) -> str:
        return self._last_message
