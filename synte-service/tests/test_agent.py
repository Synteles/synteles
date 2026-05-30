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

"""Tests for core/agent.py — stream_turn async generator."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

from core.agent import stream_turn

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _collect(gen):
    """Drain an async generator into a list."""
    return [e async for e in gen]


def _run(coro):
    return asyncio.run(coro)


def _make_mock_agent(stream_events=None):
    """Return a MagicMock agent whose stream_async yields *stream_events*."""
    agent = MagicMock()
    agent.messages = []
    agent.conversation_manager = MagicMock()
    agent.conversation_manager.restore_from_session.return_value = None
    agent.conversation_manager.get_state.return_value = {"managed": True}

    events = stream_events or []

    async def _mock_stream_async(msg, **kwargs):
        for evt in events:
            yield evt

    agent.stream_async = _mock_stream_async
    return agent


# ── Basic lifecycle events ────────────────────────────────────────────────────


class TestStreamTurnLifecycle:
    def test_yields_start_event_first(self, mocker):
        agent = _make_mock_agent()
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        assert events[0] == {"type": "start"}

    def test_yields_state_event_before_done(self, mocker):
        agent = _make_mock_agent()
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        types = [e["type"] for e in events]
        state_idx = types.index("state")
        done_idx = types.index("done")
        assert state_idx < done_idx

    def test_yields_done_event_last(self, mocker):
        agent = _make_mock_agent()
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        assert events[-1] == {"type": "done"}

    def test_empty_stream_produces_start_state_done(self, mocker):
        agent = _make_mock_agent(stream_events=[])
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        types = [e["type"] for e in events]
        assert types == ["start", "state", "done"]


# ── Text events ───────────────────────────────────────────────────────────────


class TestStreamTurnTextEvent:
    def test_text_event_from_data_key(self, mocker):
        agent = _make_mock_agent(stream_events=[{"data": "Hello"}])
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        text_events = [e for e in events if e.get("type") == "text"]
        assert len(text_events) == 1
        assert text_events[0]["delta"] == "Hello"

    def test_multiple_text_chunks_all_yielded(self, mocker):
        raw = [{"data": "chunk1"}, {"data": "chunk2"}, {"data": "chunk3"}]
        agent = _make_mock_agent(stream_events=raw)
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        text_events = [e for e in events if e.get("type") == "text"]
        assert len(text_events) == 3
        deltas = [e["delta"] for e in text_events]
        assert deltas == ["chunk1", "chunk2", "chunk3"]


# ── Tool events ───────────────────────────────────────────────────────────────


class TestStreamTurnToolEvents:
    def test_tool_start_event_from_current_tool_use(self, mocker):
        raw = [{"current_tool_use": {"toolUseId": "t1", "name": "calculator"}}]
        agent = _make_mock_agent(stream_events=raw)
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        tool_start = [e for e in events if e.get("type") == "tool_start"]
        assert len(tool_start) == 1
        assert tool_start[0]["id"] == "t1"
        assert tool_start[0]["name"] == "calculator"

    def test_tool_end_event_from_user_message_tool_result(self, mocker):
        raw = [
            {
                "message": {
                    "role": "user",
                    "content": [{"toolResult": {"toolUseId": "t1"}}],
                }
            }
        ]
        agent = _make_mock_agent(stream_events=raw)
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        tool_end = [e for e in events if e.get("type") == "tool_end"]
        assert len(tool_end) == 1
        assert tool_end[0]["id"] == "t1"


# ── None events filtered ──────────────────────────────────────────────────────


class TestStreamTurnNoneEventsFiltered:
    def test_events_returning_none_are_filtered_out(self, mocker):
        # An assistant message event returns None from map_strands_event
        raw = [
            {"message": {"role": "assistant", "content": []}},
            {"data": "visible"},
        ]
        agent = _make_mock_agent(stream_events=raw)
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        types = [e["type"] for e in events]
        assert "text" in types
        # The assistant message (returns None) should not appear
        non_protocol_types = [t for t in types if t not in ("start", "state", "done", "text")]
        assert non_protocol_types == []

    def test_empty_event_not_forwarded(self, mocker):
        raw: list[dict[str, Any]] = [{}]
        agent = _make_mock_agent(stream_events=raw)
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        types = [e["type"] for e in events]
        # Only start, state, done — no unknown type
        assert set(types) == {"start", "state", "done"}


# ── Prior messages / conversation state ──────────────────────────────────────


class TestStreamTurnWithPriorMessages:
    def test_agent_messages_set_from_prior_messages(self, mocker):
        agent = _make_mock_agent()
        mocker.patch("core.agent._build_agent", return_value=agent)

        prior = [{"role": "user", "content": "prior question"}]
        _run(_collect(stream_turn("follow-up", prior, {}, "token")))

        assert agent.messages == prior

    def test_restore_from_session_called_with_manager_state(self, mocker):
        agent = _make_mock_agent()
        mocker.patch("core.agent._build_agent", return_value=agent)

        state = {"session_key": "session_value"}
        _run(_collect(stream_turn("hi", [{"role": "user", "content": "x"}], state, "token")))

        agent.conversation_manager.restore_from_session.assert_called_once_with(state)

    def test_no_prior_messages_skips_restore(self, mocker):
        agent = _make_mock_agent()
        mocker.patch("core.agent._build_agent", return_value=agent)

        _run(_collect(stream_turn("fresh start", [], {}, "token")))

        agent.conversation_manager.restore_from_session.assert_not_called()

    def test_prepend_from_restore_session(self, mocker):
        agent = _make_mock_agent()
        prepend = [{"role": "system", "content": "prepended"}]
        agent.conversation_manager.restore_from_session.return_value = prepend
        mocker.patch("core.agent._build_agent", return_value=agent)

        prior = [{"role": "user", "content": "prior"}]
        _run(_collect(stream_turn("hi", prior, {}, "token")))

        # agent.messages should have been set to prepend + prior
        assert agent.messages[0] == prepend[0]
        assert agent.messages[1] == prior[0]


# ── Optional invocation kwargs ────────────────────────────────────────────────


class TestStreamTurnInvocationKwargs:
    def test_access_token_always_passed(self, mocker):
        agent = _make_mock_agent()
        received_kwargs: dict[str, Any] = {}

        async def _capture_stream(msg, **kwargs):
            received_kwargs.update(kwargs)
            return
            yield  # make it an async generator

        agent.stream_async = _capture_stream
        mocker.patch("core.agent._build_agent", return_value=agent)

        _run(_collect(stream_turn("hi", [], {}, "my-token")))
        assert received_kwargs.get("access_token") == "my-token"

    def test_org_id_passed_when_provided(self, mocker):
        agent = _make_mock_agent()
        received_kwargs: dict[str, Any] = {}

        async def _capture_stream(msg, **kwargs):
            received_kwargs.update(kwargs)
            return
            yield

        agent.stream_async = _capture_stream
        mocker.patch("core.agent._build_agent", return_value=agent)

        _run(_collect(stream_turn("hi", [], {}, "token", org_id="org-123")))
        assert received_kwargs.get("org_id") == "org-123"

    def test_org_id_not_passed_when_none(self, mocker):
        agent = _make_mock_agent()
        received_kwargs: dict[str, Any] = {}

        async def _capture_stream(msg, **kwargs):
            received_kwargs.update(kwargs)
            return
            yield

        agent.stream_async = _capture_stream
        mocker.patch("core.agent._build_agent", return_value=agent)

        _run(_collect(stream_turn("hi", [], {}, "token")))
        assert "org_id" not in received_kwargs

    def test_pending_input_objects_passed_when_provided(self, mocker):
        agent = _make_mock_agent()
        received_kwargs: dict[str, Any] = {}

        async def _capture_stream(msg, **kwargs):
            received_kwargs.update(kwargs)
            return
            yield

        agent.stream_async = _capture_stream
        mocker.patch("core.agent._build_agent", return_value=agent)

        _run(_collect(stream_turn("hi", [], {}, "token", pending_input_objects=["f.csv"])))
        assert received_kwargs.get("pending_input_objects") == ["f.csv"]

    def test_pending_input_objects_not_passed_when_none(self, mocker):
        agent = _make_mock_agent()
        received_kwargs: dict[str, Any] = {}

        async def _capture_stream(msg, **kwargs):
            received_kwargs.update(kwargs)
            return
            yield

        agent.stream_async = _capture_stream
        mocker.patch("core.agent._build_agent", return_value=agent)

        _run(_collect(stream_turn("hi", [], {}, "token")))
        assert "pending_input_objects" not in received_kwargs


# ── State event ───────────────────────────────────────────────────────────────


class TestStreamTurnStateEvent:
    def test_state_event_has_messages_key(self, mocker):
        agent = _make_mock_agent()
        agent.messages = [{"role": "assistant", "content": "reply"}]
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        state_events = [e for e in events if e.get("type") == "state"]
        assert len(state_events) == 1
        assert "messages" in state_events[0]

    def test_state_event_has_manager_state_key(self, mocker):
        agent = _make_mock_agent()
        agent.conversation_manager.get_state.return_value = {"k": "v"}
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        state_events = [e for e in events if e.get("type") == "state"]
        assert "manager_state" in state_events[0]
        assert state_events[0]["manager_state"] == {"k": "v"}

    def test_state_event_messages_come_from_agent(self, mocker):
        agent = _make_mock_agent()
        agent.messages = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        state_events = [e for e in events if e.get("type") == "state"]
        assert state_events[0]["messages"] == agent.messages


# ── Exception handling ────────────────────────────────────────────────────────


class TestStreamTurnException:
    def test_exception_yields_error_event(self, mocker):
        agent = _make_mock_agent()

        async def _raise_stream(msg, **kwargs):
            raise RuntimeError("agent crashed")
            yield  # make it an async generator

        agent.stream_async = _raise_stream
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1
        assert "agent crashed" in error_events[0]["message"]

    def test_exception_no_state_or_done_after_error(self, mocker):
        agent = _make_mock_agent()

        async def _raise_stream(msg, **kwargs):
            raise RuntimeError("boom")
            yield

        agent.stream_async = _raise_stream
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        types = [e["type"] for e in events]
        assert "state" not in types
        assert "done" not in types

    def test_exception_sequence_is_start_then_error(self, mocker):
        agent = _make_mock_agent()

        async def _raise_stream(msg, **kwargs):
            raise ValueError("bad value")
            yield

        agent.stream_async = _raise_stream
        mocker.patch("core.agent._build_agent", return_value=agent)

        events = _run(_collect(stream_turn("hi", [], {}, "token")))
        types = [e["type"] for e in events]
        assert types[0] == "start"
        assert types[1] == "error"
