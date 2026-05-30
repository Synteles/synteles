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

"""Tests for core/protocol.py — format_sse and map_strands_event."""

from __future__ import annotations

import json

from core.protocol import format_sse, map_strands_event

# ── format_sse ───────────────────────────────────────────────────────────────


class TestFormatSse:
    def test_returns_bytes(self):
        result = format_sse({"type": "start"})
        assert isinstance(result, bytes)

    def test_starts_with_event_prefix(self):
        result = format_sse({"type": "start"})
        assert result.startswith(b"event: ")

    def test_ends_with_double_newline(self):
        result = format_sse({"type": "start"})
        assert result.endswith(b"\n\n")

    def test_body_is_valid_json(self):
        payload = {"type": "text", "delta": "hello"}
        result = format_sse(payload)
        # Format: "event: <type>\ndata: <json>\n\n"; extract the data line
        data_line = result.decode().split("\n")[1]
        raw = data_line.removeprefix("data: ")
        parsed = json.loads(raw)
        assert parsed == {"delta": "hello"}

    def test_serialises_nested_dict(self):
        payload = {"type": "state", "messages": [{"role": "user", "content": "hi"}]}
        result = format_sse(payload)
        data_line = result.decode().split("\n")[1]
        raw = data_line.removeprefix("data: ")
        parsed = json.loads(raw)
        assert parsed["messages"][0]["role"] == "user"

    def test_serialises_empty_dict(self):
        result = format_sse({})
        data_line = result.decode().split("\n")[1]
        raw = data_line.removeprefix("data: ")
        assert json.loads(raw) == {}

    def test_wire_format_exact(self):
        event = {"type": "done"}
        expected = b"event: done\ndata: {}\n\n"
        assert format_sse(event) == expected


# ── map_strands_event ────────────────────────────────────────────────────────


class TestMapStrandsEvent:
    def test_text_event_with_data(self):
        result = map_strands_event({"data": "Hello world"})
        assert result == {"type": "text", "delta": "Hello world"}

    def test_text_event_data_takes_priority_over_other_keys(self):
        # data key wins even when other keys are present
        result = map_strands_event({"data": "Hi", "current_tool_use": {"toolUseId": "x"}})
        assert result is not None
        assert result["type"] == "text"

    def test_tool_start_event(self):
        event = {"current_tool_use": {"toolUseId": "tool-123", "name": "calculator"}}
        result = map_strands_event(event)
        assert result == {"type": "tool_start", "id": "tool-123", "name": "calculator"}

    def test_tool_start_event_missing_fields_uses_defaults(self):
        result = map_strands_event({"current_tool_use": {}})
        assert result == {"type": "tool_start", "id": "", "name": ""}

    def test_tool_end_event_user_role_with_tool_result(self):
        event = {
            "message": {
                "role": "user",
                "content": [{"toolResult": {"toolUseId": "tool-456"}}],
            }
        }
        result = map_strands_event(event)
        assert result == {"type": "tool_end", "id": "tool-456"}

    def test_tool_end_event_first_tool_result_wins(self):
        event = {
            "message": {
                "role": "user",
                "content": [
                    {"toolResult": {"toolUseId": "first"}},
                    {"toolResult": {"toolUseId": "second"}},
                ],
            }
        }
        result = map_strands_event(event)
        assert result is not None
        assert result["id"] == "first"

    def test_message_role_assistant_returns_none(self):
        event = {
            "message": {
                "role": "assistant",
                "content": [{"toolResult": {"toolUseId": "x"}}],
            }
        }
        result = map_strands_event(event)
        assert result is None

    def test_message_role_user_no_tool_result_returns_none(self):
        event = {
            "message": {
                "role": "user",
                "content": [{"text": "some text"}],
            }
        }
        result = map_strands_event(event)
        assert result is None

    def test_message_role_user_empty_content_returns_none(self):
        event = {"message": {"role": "user", "content": []}}
        result = map_strands_event(event)
        assert result is None

    def test_error_event(self):
        result = map_strands_event({"error": "Something went wrong"})
        assert result == {"type": "error", "message": "Something went wrong"}

    def test_error_event_converts_to_string(self):
        result = map_strands_event({"error": ValueError("bad value")})
        assert result is not None
        assert result["type"] == "error"
        assert "bad value" in result["message"]

    def test_unknown_event_returns_none(self):
        result = map_strands_event({"unknown_key": "value"})
        assert result is None

    def test_empty_event_returns_none(self):
        result = map_strands_event({})
        assert result is None

    def test_data_key_falsy_skips_text_branch(self):
        # data="" is falsy — should not produce a text event
        result = map_strands_event({"data": ""})
        assert result is None

    def test_data_key_none_skips_text_branch(self):
        result = map_strands_event({"data": None})
        assert result is None
