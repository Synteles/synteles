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

"""Integration tests for the conversations API.

Covered:
  GET    /api/conversations
  POST   /api/conversations
  GET    /api/conversations/{conv_id}
  PATCH  /api/conversations/{conv_id}
  DELETE /api/conversations/{conv_id}
"""
import json
import os
import uuid

import httpx
import pytest

from conftest import rewrite_presigned_url

# Presigned URLs are signed against S3_INTERNAL_ENDPOINT_URL; fetching them
# from a different host breaks the HMAC signature (MinIO returns 403).
# Skip direct-fetch tests when the two endpoints differ (i.e. outside Docker).
_s3_internal = os.environ.get("S3_INTERNAL_ENDPOINT_URL", "").rstrip("/")
_s3_public = os.environ.get("S3_PUBLIC_ENDPOINT_URL", "").rstrip("/")
_PRESIGNED_DIRECT_FETCH_UNAVAILABLE = bool(_s3_internal) and _s3_internal != _s3_public

_DISPLAY_MESSAGES = [
    {"role": "assistant", "content": "Hi, I'm SYNTE!", "tool_calls": []},
    {"role": "user", "content": "List my agentlets", "tool_calls": []},
]
_AGENT_STATE = {
    "messages": [
        {"role": "user", "content": [{"text": "List my agentlets"}]},
        {"role": "assistant", "content": [{"text": "Here are your agentlets..."}]},
    ],
    "manager_state": {},
}


@pytest.fixture()
def ephemeral_conversation(client: httpx.Client):
    """Create a conversation before the test; delete it on teardown."""
    resp = client.post(
        "/api/conversations",
        json={
            "title": f"inttest-{uuid.uuid4().hex[:8]}",
            "display_messages": _DISPLAY_MESSAGES,
            "agent_state": _AGENT_STATE,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    yield data

    client.delete(f"/api/conversations/{data['conversation_id']}")


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class TestListConversations:
    def test_happy_path_returns_list(
        self, client: httpx.Client, ephemeral_conversation: dict
    ) -> None:
        resp = client.get("/api/conversations")
        assert resp.status_code == 200
        body = resp.json()
        assert "conversations" in body
        ids = [c["conversation_id"] for c in body["conversations"]]
        assert ephemeral_conversation["conversation_id"] in ids

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        resp = unauth_client.get("/api/conversations")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class TestCreateConversation:
    def test_happy_path_creates_conversation(self, client: httpx.Client) -> None:
        title = f"create-test-{uuid.uuid4().hex[:8]}"
        resp = client.post(
            "/api/conversations",
            json={
                "title": title,
                "display_messages": _DISPLAY_MESSAGES,
                "agent_state": _AGENT_STATE,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "conversation_id" in data
        assert data["title"] == title
        assert data["message_count"] == len(_DISPLAY_MESSAGES)

        # cleanup
        client.delete(f"/api/conversations/{data['conversation_id']}")

    def test_title_truncated_at_80_chars(self, client: httpx.Client) -> None:
        resp = client.post(
            "/api/conversations",
            json={
                "title": "x" * 200,
                "display_messages": _DISPLAY_MESSAGES,
                "agent_state": _AGENT_STATE,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["title"]) == 80
        client.delete(f"/api/conversations/{data['conversation_id']}")

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        resp = unauth_client.post(
            "/api/conversations",
            json={"title": "x", "display_messages": [], "agent_state": {}},
        )
        assert resp.status_code == 401

    def test_missing_required_fields_returns_400(self, client: httpx.Client) -> None:
        resp = client.post("/api/conversations", json={"title": "incomplete"})
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------

class TestGetConversation:
    def test_happy_path_returns_presigned_urls(
        self, client: httpx.Client, ephemeral_conversation: dict
    ) -> None:
        conv_id = ephemeral_conversation["conversation_id"]
        resp = client.get(f"/api/conversations/{conv_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "display_url" in data
        assert "agent_state_url" in data
        assert data["display_url"].startswith(("http://", "https://"))
        assert data["agent_state_url"].startswith(("http://", "https://"))

    @pytest.mark.skipif(
        _PRESIGNED_DIRECT_FETCH_UNAVAILABLE,
        reason="S3 presigned URLs signed with internal endpoint; direct fetch invalid outside Docker",
    )
    def test_presigned_urls_are_fetchable(
        self, client: httpx.Client, ephemeral_conversation: dict
    ) -> None:
        conv_id = ephemeral_conversation["conversation_id"]
        resp = client.get(f"/api/conversations/{conv_id}")
        data = resp.json()

        with httpx.Client(timeout=10) as hx:
            display_resp = hx.get(rewrite_presigned_url(data["display_url"]))
            assert display_resp.status_code == 200
            assert display_resp.json() == _DISPLAY_MESSAGES

            state_resp = hx.get(rewrite_presigned_url(data["agent_state_url"]))
            assert state_resp.status_code == 200
            assert state_resp.json() == _AGENT_STATE

    def test_nonexistent_returns_404(self, client: httpx.Client) -> None:
        resp = client.get(f"/api/conversations/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        resp = unauth_client.get(f"/api/conversations/{uuid.uuid4()}")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class TestUpdateConversation:
    def test_update_title(
        self, client: httpx.Client, ephemeral_conversation: dict
    ) -> None:
        conv_id = ephemeral_conversation["conversation_id"]
        new_title = f"renamed-{uuid.uuid4().hex[:6]}"
        resp = client.patch(f"/api/conversations/{conv_id}", json={"title": new_title})
        assert resp.status_code == 200

        # Verify title updated via GET
        get_resp = client.get(f"/api/conversations/{conv_id}")
        assert get_resp.json()["title"] == new_title

    @pytest.mark.skipif(
        _PRESIGNED_DIRECT_FETCH_UNAVAILABLE,
        reason="S3 presigned URLs signed with internal endpoint; direct fetch invalid outside Docker",
    )
    def test_update_blobs(
        self, client: httpx.Client, ephemeral_conversation: dict
    ) -> None:
        conv_id = ephemeral_conversation["conversation_id"]
        new_messages = [{"role": "user", "content": "new message", "tool_calls": []}]
        new_state = {"messages": [{"role": "user"}], "manager_state": {"updated": True}}
        resp = client.patch(
            f"/api/conversations/{conv_id}",
            json={"display_messages": new_messages, "agent_state": new_state},
        )
        assert resp.status_code == 200

        # Fetch presigned URL and verify blob content
        get_resp = client.get(f"/api/conversations/{conv_id}")
        with httpx.Client(timeout=10) as hx:
            display_resp = hx.get(rewrite_presigned_url(get_resp.json()["display_url"]))
            assert display_resp.json() == new_messages

    def test_nonexistent_returns_404(self, client: httpx.Client) -> None:
        resp = client.patch(f"/api/conversations/{uuid.uuid4()}", json={"title": "x"})
        assert resp.status_code == 404

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        resp = unauth_client.patch(f"/api/conversations/{uuid.uuid4()}", json={"title": "x"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDeleteConversation:
    def test_happy_path_deletes(self, client: httpx.Client) -> None:
        create_resp = client.post(
            "/api/conversations",
            json={
                "title": "to-delete",
                "display_messages": _DISPLAY_MESSAGES,
                "agent_state": _AGENT_STATE,
            },
        )
        assert create_resp.status_code == 201
        conv_id = create_resp.json()["conversation_id"]

        delete_resp = client.delete(f"/api/conversations/{conv_id}")
        assert delete_resp.status_code in (200, 204)

        get_resp = client.get(f"/api/conversations/{conv_id}")
        assert get_resp.status_code == 404

    def test_double_delete_returns_404(self, client: httpx.Client) -> None:
        create_resp = client.post(
            "/api/conversations",
            json={
                "title": "double-delete",
                "display_messages": _DISPLAY_MESSAGES,
                "agent_state": _AGENT_STATE,
            },
        )
        conv_id = create_resp.json()["conversation_id"]
        client.delete(f"/api/conversations/{conv_id}")
        resp = client.delete(f"/api/conversations/{conv_id}")
        assert resp.status_code == 404

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        resp = unauth_client.delete(f"/api/conversations/{uuid.uuid4()}")
        assert resp.status_code == 401
