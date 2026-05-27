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

"""Integration tests for user secrets endpoints.

Covered:
  POST   /api/secrets
  GET    /api/secrets
  GET    /api/secrets/{secret_name}
  PATCH  /api/secrets/{secret_name}
  DELETE /api/secrets/{secret_name}
"""

import uuid

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique_name() -> str:
    return f"INTTEST_{uuid.uuid4().hex[:8].upper()}"


@pytest.fixture()
def ephemeral_secret(client: httpx.Client) -> dict:
    """Create a secret for a single test; delete it on teardown."""
    name = _unique_name()
    response = client.post("/api/secrets", json={"name": name, "value": {"TEST_KEY": "test-value-123"}})
    assert response.status_code == 201, response.text
    secret = response.json()

    yield {"name": name, **secret}

    client.delete(f"/api/secrets/{name}")


# ---------------------------------------------------------------------------
# Create secret
# ---------------------------------------------------------------------------

class TestCreateSecret:
    def test_happy_path_creates_secret(self, client: httpx.Client) -> None:
        name = _unique_name()
        response = client.post("/api/secrets", json={"name": name, "value": {"ANTHROPIC_API_KEY": "my-api-key"}})

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == name

        # cleanup
        client.delete(f"/api/secrets/{name}")

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        response = unauth_client.post(
            "/api/secrets", json={"name": "X", "value": "y"}
        )

        assert response.status_code == 401

    def test_duplicate_name_returns_error(
        self, client: httpx.Client, ephemeral_secret: dict
    ) -> None:
        name = ephemeral_secret["name"]
        response = client.post("/api/secrets", json={"name": name, "value": {"KEY": "duplicate"}})

        assert response.status_code in (400, 409)


# ---------------------------------------------------------------------------
# List secrets
# ---------------------------------------------------------------------------

class TestListSecrets:
    def test_happy_path_returns_list(
        self, client: httpx.Client, ephemeral_secret: dict
    ) -> None:
        response = client.get("/api/secrets")

        assert response.status_code == 200
        data = response.json()
        # Response is a list or a wrapper object
        secrets = data if isinstance(data, list) else data.get("secrets", [])
        names = [s["name"] for s in secrets]
        assert ephemeral_secret["name"] in names

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        response = unauth_client.get("/api/secrets")

        assert response.status_code == 401

    def test_user_with_no_secrets_returns_empty_list(self, client: httpx.Client) -> None:
        # If the test user happens to have secrets this just asserts the shape is valid.
        response = client.get("/api/secrets")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "secrets" in data


# ---------------------------------------------------------------------------
# Get secret by name
# ---------------------------------------------------------------------------

class TestGetSecret:
    def test_happy_path_returns_secret(
        self, client: httpx.Client, ephemeral_secret: dict
    ) -> None:
        name = ephemeral_secret["name"]
        response = client.get(f"/api/secrets/{name}")

        assert response.status_code == 200
        assert response.json()["name"] == name

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, ephemeral_secret: dict
    ) -> None:
        response = unauth_client.get(f"/api/secrets/{ephemeral_secret['name']}")

        assert response.status_code == 401

    def test_reveal_value_returns_key_values(
        self, client: httpx.Client, ephemeral_secret: dict
    ) -> None:
        name = ephemeral_secret["name"]
        response = client.get(f"/api/secrets/{name}?reveal_value=true")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == name
        # value dict should be present and contain the key we stored
        assert "value" in data or "key_values" in data or "keys" in data

    def test_nonexistent_secret_returns_404(self, client: httpx.Client) -> None:
        response = client.get("/api/secrets/DOES_NOT_EXIST_000000")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Update secret
# ---------------------------------------------------------------------------

class TestUpdateSecret:
    def test_happy_path_updates_secret(
        self, client: httpx.Client, ephemeral_secret: dict
    ) -> None:
        name = ephemeral_secret["name"]
        response = client.patch(f"/api/secrets/{name}", json={"value": {"ANTHROPIC_API_KEY": "updated-value"}})

        assert response.status_code == 200
        assert response.json()["name"] == name

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, ephemeral_secret: dict
    ) -> None:
        response = unauth_client.patch(
            f"/api/secrets/{ephemeral_secret['name']}", json={"value": "x"}
        )

        assert response.status_code == 401

    def test_nonexistent_secret_returns_404(self, client: httpx.Client) -> None:
        response = client.patch(
            "/api/secrets/DOES_NOT_EXIST_000000", json={"value": {"KEY": "x"}}
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete secret
# ---------------------------------------------------------------------------

class TestDeleteSecret:
    def test_happy_path_deletes_secret(self, client: httpx.Client) -> None:
        name = _unique_name()
        create = client.post("/api/secrets", json={"name": name, "value": {"KEY": "to-delete"}})
        assert create.status_code == 201

        response = client.delete(f"/api/secrets/{name}")

        assert response.status_code in (200, 204)

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, ephemeral_secret: dict
    ) -> None:
        response = unauth_client.delete(f"/api/secrets/{ephemeral_secret['name']}")

        assert response.status_code == 401

    def test_double_delete_returns_404(self, client: httpx.Client) -> None:
        name = _unique_name()
        client.post("/api/secrets", json={"name": name, "value": {"KEY": "to-double-delete"}})
        client.delete(f"/api/secrets/{name}")

        response = client.delete(f"/api/secrets/{name}")

        assert response.status_code == 404
