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

"""Tests for adapters/server.py — FastAPI endpoints."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from adapters.server import app

client = TestClient(app, raise_server_exceptions=False)


# ── /health ──────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_body(self):
        response = client.get("/health")
        assert response.json() == {"status": "ok"}


# ── /chat/stream — auth validation ───────────────────────────────────────────

class TestChatStreamAuth:
    def test_missing_authorization_header_returns_422(self):
        response = client.post(
            "/chat/stream",
            json={"message": "hello"},
        )
        assert response.status_code == 422

    def test_non_bearer_token_returns_401(self):
        response = client.post(
            "/chat/stream",
            json={"message": "hello"},
            headers={"Authorization": "InvalidToken xyz"},
        )
        assert response.status_code == 401

    def test_non_bearer_token_error_detail(self):
        response = client.post(
            "/chat/stream",
            json={"message": "hello"},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code == 401
        assert "Bearer" in response.json().get("detail", "")


# ── /chat/stream — success path ───────────────────────────────────────────────

class TestChatStreamSuccess:
    def test_success_returns_200(self, mocker):
        async def _fake_stream(message, messages, manager_state, access_token, org_id=None, pending_input_objects=None):
            yield {"type": "start"}
            yield {"type": "done"}

        mocker.patch("core.agent.stream_turn", new=_fake_stream)

        response = client.post(
            "/chat/stream",
            json={"message": "hello"},
            headers={"Authorization": "Bearer valid-token"},
        )
        assert response.status_code == 200

    def test_success_content_type_is_event_stream(self, mocker):
        async def _fake_stream(message, messages, manager_state, access_token, org_id=None, pending_input_objects=None):
            yield {"type": "start"}

        mocker.patch("core.agent.stream_turn", new=_fake_stream)

        response = client.post(
            "/chat/stream",
            json={"message": "hello"},
            headers={"Authorization": "Bearer valid-token"},
        )
        assert "text/event-stream" in response.headers["content-type"]

    def test_success_body_contains_sse_data_lines(self, mocker):
        async def _fake_stream(message, messages, manager_state, access_token, org_id=None, pending_input_objects=None):
            yield {"type": "start"}
            yield {"type": "done"}

        mocker.patch("core.agent.stream_turn", new=_fake_stream)

        response = client.post(
            "/chat/stream",
            json={"message": "hello"},
            headers={"Authorization": "Bearer valid-token"},
        )
        assert b"data:" in response.content

    def test_success_body_contains_start_event(self, mocker):
        async def _fake_stream(message, messages, manager_state, access_token, org_id=None, pending_input_objects=None):
            yield {"type": "start"}
            yield {"type": "done"}

        mocker.patch("core.agent.stream_turn", new=_fake_stream)

        response = client.post(
            "/chat/stream",
            json={"message": "hello"},
            headers={"Authorization": "Bearer valid-token"},
        )
        assert b'event: start' in response.content

    def test_bearer_token_stripped_and_passed(self, mocker):
        received_token = []

        async def _fake_stream(message, messages, manager_state, access_token, org_id=None, pending_input_objects=None):
            received_token.append(access_token)
            yield {"type": "done"}

        mocker.patch("core.agent.stream_turn", new=_fake_stream)

        client.post(
            "/chat/stream",
            json={"message": "hi"},
            headers={"Authorization": "Bearer my-secret-token"},
        )
        assert received_token == ["my-secret-token"]


# ── /chat/stream — optional fields ───────────────────────────────────────────

class TestChatStreamOptionalFields:
    def test_org_id_passed_to_stream_turn(self, mocker):
        received_kwargs: dict = {}

        async def _fake_stream(message, messages, manager_state, access_token, org_id=None, pending_input_objects=None):
            received_kwargs["org_id"] = org_id
            yield {"type": "done"}

        mocker.patch("core.agent.stream_turn", new=_fake_stream)

        client.post(
            "/chat/stream",
            json={"message": "hi", "org_id": "org-abc"},
            headers={"Authorization": "Bearer tok"},
        )
        assert received_kwargs.get("org_id") == "org-abc"

    def test_pending_input_objects_passed_to_stream_turn(self, mocker):
        received_kwargs: dict = {}

        async def _fake_stream(message, messages, manager_state, access_token, org_id=None, pending_input_objects=None):
            received_kwargs["pending_input_objects"] = pending_input_objects
            yield {"type": "done"}

        mocker.patch("core.agent.stream_turn", new=_fake_stream)

        client.post(
            "/chat/stream",
            json={"message": "hi", "pending_input_objects": ["file1.csv", "file2.xlsx"]},
            headers={"Authorization": "Bearer tok"},
        )
        assert received_kwargs.get("pending_input_objects") == ["file1.csv", "file2.xlsx"]

    def test_messages_and_manager_state_passed(self, mocker):
        received_kwargs: dict = {}

        async def _fake_stream(message, messages, manager_state, access_token, org_id=None, pending_input_objects=None):
            received_kwargs["messages"] = messages
            received_kwargs["manager_state"] = manager_state
            yield {"type": "done"}

        mocker.patch("core.agent.stream_turn", new=_fake_stream)

        prior_messages = [{"role": "user", "content": "prior question"}]
        state = {"key": "value"}
        client.post(
            "/chat/stream",
            json={"message": "follow-up", "messages": prior_messages, "manager_state": state},
            headers={"Authorization": "Bearer tok"},
        )
        assert received_kwargs["messages"] == prior_messages
        assert received_kwargs["manager_state"] == state


# ── /chat/stream — error event in stream ────────────────────────────────────

class TestChatStreamErrorEvent:
    def test_error_event_still_returns_200(self, mocker):
        async def _fake_stream(message, messages, manager_state, access_token, org_id=None, pending_input_objects=None):
            yield {"type": "error", "message": "something failed"}

        mocker.patch("core.agent.stream_turn", new=_fake_stream)

        response = client.post(
            "/chat/stream",
            json={"message": "hello"},
            headers={"Authorization": "Bearer tok"},
        )
        assert response.status_code == 200

    def test_error_event_in_body(self, mocker):
        async def _fake_stream(message, messages, manager_state, access_token, org_id=None, pending_input_objects=None):
            yield {"type": "error", "message": "something failed"}

        mocker.patch("core.agent.stream_turn", new=_fake_stream)

        response = client.post(
            "/chat/stream",
            json={"message": "hello"},
            headers={"Authorization": "Bearer tok"},
        )
        assert b"error" in response.content
        assert b"something failed" in response.content

    def test_text_event_serialised_in_stream(self, mocker):
        async def _fake_stream(message, messages, manager_state, access_token, org_id=None, pending_input_objects=None):
            yield {"type": "text", "delta": "Hello!"}
            yield {"type": "done"}

        mocker.patch("core.agent.stream_turn", new=_fake_stream)

        response = client.post(
            "/chat/stream",
            json={"message": "hi"},
            headers={"Authorization": "Bearer tok"},
        )
        assert b"Hello!" in response.content


class TestRootRouteRemoved:
    def test_post_root_returns_404(self):
        """POST / was the Lambda Function URL entry point — must not exist in ECS."""
        response = client.post("/", json={"message": "hello"},
                               headers={"Authorization": "Bearer fake-token"})
        # 404: route removed entirely (no handler at / — FastAPI returns Not Found)
        # 405: would only occur if a different-method handler existed at /
        assert response.status_code == 404
