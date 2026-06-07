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

"""Module-level state set once at startup by worker.main(), read by the workflow and activities.

Values are populated before the Temporal Worker starts polling — safe for workflow
code to read because they never change after that point."""

from dataclasses import dataclass, field


@dataclass
class MCPServerRef:
    """Minimal info needed to launch an MCP stdio server for a tool call."""

    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


system_prompt: str = ""
effective_prompt: str = ""

# LiteLLM model string, e.g. "azure_ai/gpt-5.3-chat", "openai/gpt-4o", "anthropic/claude-3-5-sonnet"
model: str = "azure_ai/gpt-5.3-chat"

# OpenAI-format tool schemas to pass to litellm — MCP tools discovered at startup
tools_schema: list[dict] = []  # type: ignore[type-arg]

# Maps each MCP tool name to the server that provides it
mcp_tool_map: dict[str, MCPServerRef] = {}
