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

"""Integration tests for MCP preset endpoints.

Covered:
  POST   /api/connectors
  GET    /api/connectors
  GET    /api/connectors/{name}
  PATCH  /api/connectors/{name}
  DELETE /api/connectors/{name}
"""

import json
import uuid

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique_name() -> str:
    return f"inttest_{uuid.uuid4().hex[:8]}"


def _mcp_config(server_name: str = "test-server") -> str:
    """Return a minimal valid mcp_config JSON string."""
    return json.dumps({
        "mcpServers": {
            server_name: {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-everything"],
            }
        }
    })


@pytest.fixture()
def ephemeral_preset(client: httpx.Client) -> dict:
    """Create an MCP preset for a single test; delete it on teardown."""
    name = _unique_name()
    response = client.post("/api/connectors", json={
        "name": name,
        "description": "Integration test MCP preset",
        "mcp_config": _mcp_config(),
    })
    assert response.status_code == 201, response.text
    preset = response.json()

    yield {"name": name, **preset}

    client.delete(f"/api/connectors/{name}")


# ---------------------------------------------------------------------------
# POST /api/connectors
# ---------------------------------------------------------------------------

class TestCreateMcpPreset:
    def test_happy_path_creates_preset(self, client: httpx.Client) -> None:
        name = _unique_name()
        response = client.post("/api/connectors", json={
            "name": name,
            "description": "My MCP servers",
            "mcp_config": _mcp_config(),
        })

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == name
        assert "mcp_config" in data
        assert "created_at" in data

        client.delete(f"/api/connectors/{name}")

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        response = unauth_client.post("/api/connectors", json={
            "name": _unique_name(), "mcp_config": _mcp_config()
        })
        assert response.status_code == 401

    def test_duplicate_name_returns_409(
        self, client: httpx.Client, ephemeral_preset: dict
    ) -> None:
        response = client.post("/api/connectors", json={
            "name": ephemeral_preset["name"],
            "mcp_config": _mcp_config(),
        })
        assert response.status_code == 409

    def test_missing_mcp_config_returns_400(self, client: httpx.Client) -> None:
        response = client.post("/api/connectors", json={"name": _unique_name()})
        assert response.status_code in (400, 422)

    def test_mcp_config_without_mcp_servers_key_returns_400(
        self, client: httpx.Client
    ) -> None:
        invalid_config = json.dumps({"tools": []})
        response = client.post("/api/connectors", json={
            "name": _unique_name(),
            "mcp_config": invalid_config,
        })
        assert response.status_code in (400, 422)

    def test_invalid_json_mcp_config_returns_400(self, client: httpx.Client) -> None:
        response = client.post("/api/connectors", json={
            "name": _unique_name(),
            "mcp_config": "not-valid-json{",
        })
        assert response.status_code in (400, 422)


# ---------------------------------------------------------------------------
# GET /api/connectors
# ---------------------------------------------------------------------------

class TestListMcpPresets:
    def test_happy_path_returns_list(
        self, client: httpx.Client, ephemeral_preset: dict
    ) -> None:
        response = client.get("/api/connectors")

        assert response.status_code == 200
        data = response.json()
        presets = data.get("presets", data) if isinstance(data, dict) else data
        names = [p["name"] for p in presets]
        assert ephemeral_preset["name"] in names

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        response = unauth_client.get("/api/connectors")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/connectors/{name}
# ---------------------------------------------------------------------------

class TestGetMcpPreset:
    def test_happy_path_returns_preset(
        self, client: httpx.Client, ephemeral_preset: dict
    ) -> None:
        name = ephemeral_preset["name"]
        response = client.get(f"/api/connectors/{name}")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == name
        assert "mcp_config" in data

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, ephemeral_preset: dict
    ) -> None:
        response = unauth_client.get(f"/api/connectors/{ephemeral_preset['name']}")
        assert response.status_code == 401

    def test_nonexistent_preset_returns_404(self, client: httpx.Client) -> None:
        response = client.get("/api/connectors/does_not_exist_000000")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/connectors/{name}
# ---------------------------------------------------------------------------

class TestUpdateMcpPreset:
    def test_update_description(
        self, client: httpx.Client, ephemeral_preset: dict
    ) -> None:
        name = ephemeral_preset["name"]
        response = client.patch(f"/api/connectors/{name}", json={
            "description": "Updated description"
        })
        assert response.status_code == 200

    def test_update_mcp_config(
        self, client: httpx.Client, ephemeral_preset: dict
    ) -> None:
        name = ephemeral_preset["name"]
        response = client.patch(f"/api/connectors/{name}", json={
            "mcp_config": _mcp_config("updated-server"),
        })
        assert response.status_code == 200
        data = response.json()
        assert "updated-server" in data.get("mcp_config", "")

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, ephemeral_preset: dict
    ) -> None:
        response = unauth_client.patch(
            f"/api/connectors/{ephemeral_preset['name']}",
            json={"description": "x"},
        )
        assert response.status_code == 401

    def test_nonexistent_preset_returns_404(self, client: httpx.Client) -> None:
        response = client.patch(
            "/api/connectors/does_not_exist_000000",
            json={"description": "x"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/connectors/{name}
# ---------------------------------------------------------------------------

class TestDeleteMcpPreset:
    def test_happy_path_deletes_preset(self, client: httpx.Client) -> None:
        name = _unique_name()
        create = client.post("/api/connectors", json={
            "name": name, "mcp_config": _mcp_config()
        })
        assert create.status_code == 201

        response = client.delete(f"/api/connectors/{name}")
        assert response.status_code in (200, 204)

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, ephemeral_preset: dict
    ) -> None:
        response = unauth_client.delete(f"/api/connectors/{ephemeral_preset['name']}")
        assert response.status_code == 401

    def test_nonexistent_preset_returns_404(self, client: httpx.Client) -> None:
        response = client.delete("/api/connectors/does_not_exist_000000")
        assert response.status_code == 404
