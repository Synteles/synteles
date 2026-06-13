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

"""Temporal-serializable configuration types that cross the activity→workflow boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StdioServerConfig:
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class HttpServerConfig:
    url: str
    transport: str  # "http" | "sse"
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentWorkflowConfig:
    system_prompt: str
    effective_prompt: str
    model: str
    tools_schema: list[dict[str, Any]]
    output_url: str
    stdio_tool_map: dict[str, StdioServerConfig]
    http_tool_map: dict[str, HttpServerConfig]
