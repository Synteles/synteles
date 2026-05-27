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

"""SSE event types and wire format for the chat streaming API."""

from __future__ import annotations

import json
from typing import Any


def format_sse(event: dict[str, Any]) -> bytes:
    event_type = event.get("type", "message")
    payload = {k: v for k, v in event.items() if k != "type"}
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n".encode()


def map_strands_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Map a raw Strands streaming event to our SSE protocol dict.

    Returns None for events that should not be forwarded to the client.

    Event shape written against strands-agents 1.x:
      text delta   : {"data": str}
      tool start   : {"current_tool_use": {"toolUseId": str, "name": str, ...}}
      tool end     : {"message": {"role": "user", "content": [{"toolResult": {"toolUseId": str}}]}}
      error        : {"error": any}
    """
    if event.get("data"):
        return {"type": "text", "delta": event["data"]}

    if "current_tool_use" in event:
        tu = event["current_tool_use"]
        return {
            "type": "tool_start",
            "id": tu.get("toolUseId", ""),
            "name": tu.get("name", ""),
        }

    if "message" in event:
        msg = event["message"]
        if msg.get("role") == "user":
            for item in msg.get("content", []):
                if "toolResult" in item:
                    tr = item["toolResult"]
                    return {"type": "tool_end", "id": tr.get("toolUseId", "")}

    if "error" in event:
        return {"type": "error", "message": str(event["error"])}

    return None
