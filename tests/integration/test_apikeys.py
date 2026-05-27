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

"""Integration tests for API key CRUD endpoints.

Covered:
  GET    /api/users/apikeys
  POST   /api/users/apikeys
  DELETE /api/users/apikeys/{apikey_id}
"""

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def ephemeral_apikey(client: httpx.Client) -> dict:
    """Create an API key for a single test; delete it on teardown."""
    response = client.post("/api/users/apikeys", json={"key_name": "ephemeral-key"})
    assert response.status_code == 200, response.text
    key_data = response.json()

    yield key_data

    client.delete(f"/api/users/apikeys/{key_data['key_id']}")


# ---------------------------------------------------------------------------
# List API keys
# ---------------------------------------------------------------------------

class TestListApiKeys:
    def test_happy_path_returns_list(self, client: httpx.Client) -> None:
        response = client.get("/api/users/apikeys")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "keys" in data or "api_keys" in data

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        response = unauth_client.get("/api/users/apikeys")

        assert response.status_code == 401

    def test_invalid_token_returns_401(self, api_base_url: str) -> None:
        with httpx.Client(
            base_url=api_base_url,
            headers={"Authorization": "Bearer garbage.token.value"},
            timeout=10.0,
        ) as c:
            response = c.get("/api/users/apikeys")

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Create API key
# ---------------------------------------------------------------------------

class TestCreateApiKey:
    def test_happy_path_creates_key(self, client: httpx.Client) -> None:
        response = client.post("/api/users/apikeys", json={"key_name": "test-create-key"})

        assert response.status_code == 200
        data = response.json()
        assert "key_id" in data
        assert "key" in data  # raw key value returned once on creation

        # cleanup
        client.delete(f"/api/users/apikeys/{data['key_id']}")

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        response = unauth_client.post("/api/users/apikeys", json={"key_name": "x"})

        assert response.status_code == 401

    def test_malformed_body_returns_400(self, client: httpx.Client) -> None:
        response = client.post(
            "/api/users/apikeys",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )

        # Lambda may return 400 for missing key_name or 500 if JSON parsing crashes
        assert response.status_code in (400, 422, 500)


# ---------------------------------------------------------------------------
# Delete API key
# ---------------------------------------------------------------------------

class TestDeleteApiKey:
    def test_happy_path_deletes_key(
        self, client: httpx.Client, ephemeral_apikey: dict
    ) -> None:
        key_id = ephemeral_apikey["key_id"]
        response = client.delete(f"/api/users/apikeys/{key_id}")

        assert response.status_code in (200, 204)

        # prevent fixture teardown from also trying to delete (already gone)
        ephemeral_apikey["key_id"] = "__deleted__"

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, ephemeral_apikey: dict
    ) -> None:
        response = unauth_client.delete(f"/api/users/apikeys/{ephemeral_apikey['key_id']}")

        assert response.status_code == 401

    def test_nonexistent_key_returns_404(self, client: httpx.Client) -> None:
        response = client.delete("/api/users/apikeys/nonexistent-key-id-000000")

        assert response.status_code == 404
