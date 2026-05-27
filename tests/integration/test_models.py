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

"""Integration tests for model preset endpoints.

Covered:
  POST   /api/models
  GET    /api/models
  GET    /api/models/{preset_name}
  PATCH  /api/models/{preset_name}
  DELETE /api/models/{preset_name}
"""

import uuid

import httpx
import pytest


def _unique_name() -> str:
    return f"inttest_{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def ephemeral_preset(client: httpx.Client) -> dict:
    """Create a preset for a single test; delete on teardown."""
    name = _unique_name()
    response = client.post("/api/models", json={
        "name": name,
        "provider": "openai",
        "model_id": "gpt-4.1",
        "description": "Integration test preset",
    })
    assert response.status_code == 201, response.text
    preset = response.json()

    yield {"name": name, **preset}

    client.delete(f"/api/models/{name}")


class TestCreateModelPreset:
    def test_happy_path_creates_preset(self, client: httpx.Client) -> None:
        name = _unique_name()
        response = client.post("/api/models", json={
            "name": name,
            "provider": "bedrock",
            "model_id": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "description": "EU Claude Sonnet",
            "secret_name": "bedrock-creds",
        })

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == name
        assert data["provider"] == "bedrock"
        assert data["secret_name"] == "bedrock-creds"

        client.delete(f"/api/models/{name}")

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        response = unauth_client.post("/api/models", json={
            "name": "x", "provider": "openai", "model_id": "gpt-4o"
        })
        assert response.status_code == 401

    def test_duplicate_name_returns_409(self, client: httpx.Client, ephemeral_preset: dict) -> None:
        response = client.post("/api/models", json={
            "name": ephemeral_preset["name"],
            "provider": "openai",
            "model_id": "gpt-4o",
        })
        assert response.status_code == 409

    def test_invalid_provider_returns_400(self, client: httpx.Client) -> None:
        response = client.post("/api/models", json={
            "name": _unique_name(),
            "provider": "unknown_llm",
            "model_id": "some-model",
        })
        assert response.status_code in (400, 422)

    def test_missing_model_id_returns_400(self, client: httpx.Client) -> None:
        response = client.post("/api/models", json={
            "name": _unique_name(),
            "provider": "openai",
        })
        assert response.status_code in (400, 422)


class TestListModelPresets:
    def test_happy_path_returns_list(self, client: httpx.Client, ephemeral_preset: dict) -> None:
        response = client.get("/api/models")

        assert response.status_code == 200
        data = response.json()
        names = [p["name"] for p in (data if isinstance(data, list) else data.get("presets", []))]
        assert ephemeral_preset["name"] in names

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        response = unauth_client.get("/api/models")
        assert response.status_code == 401


class TestGetModelPreset:
    def test_happy_path(self, client: httpx.Client, ephemeral_preset: dict) -> None:
        name = ephemeral_preset["name"]
        response = client.get(f"/api/models/{name}")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == name
        assert data["provider"] == "openai"
        assert data["model_id"] == "gpt-4.1"

    def test_not_found_returns_404(self, client: httpx.Client) -> None:
        response = client.get("/api/models/nonexistent_preset_xyz")
        assert response.status_code == 404


class TestUpdateModelPreset:
    def test_update_description(self, client: httpx.Client, ephemeral_preset: dict) -> None:
        name = ephemeral_preset["name"]
        response = client.patch(f"/api/models/{name}", json={"description": "Updated tagline"})
        assert response.status_code == 200

    def test_update_model_id(self, client: httpx.Client, ephemeral_preset: dict) -> None:
        name = ephemeral_preset["name"]
        response = client.patch(f"/api/models/{name}", json={"model_id": "gpt-5"})
        assert response.status_code == 200

    def test_update_secret_name(self, client: httpx.Client, ephemeral_preset: dict) -> None:
        name = ephemeral_preset["name"]
        response = client.patch(f"/api/models/{name}", json={"secret_name": "new-secret"})
        assert response.status_code == 200

    def test_no_fields_returns_400(self, client: httpx.Client, ephemeral_preset: dict) -> None:
        name = ephemeral_preset["name"]
        response = client.patch(f"/api/models/{name}", json={})
        assert response.status_code in (400, 422)

    def test_not_found_returns_404(self, client: httpx.Client) -> None:
        response = client.patch("/api/models/nonexistent_xyz", json={"description": "x"})
        assert response.status_code == 404


class TestDeleteModelPreset:
    def test_happy_path(self, client: httpx.Client) -> None:
        name = _unique_name()
        client.post("/api/models", json={"name": name, "provider": "openai", "model_id": "gpt-4o"})
        response = client.delete(f"/api/models/{name}")
        assert response.status_code == 204

    def test_not_found_returns_404(self, client: httpx.Client) -> None:
        response = client.delete("/api/models/nonexistent_xyz")
        assert response.status_code == 404
