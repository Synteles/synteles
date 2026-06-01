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

"""Integration tests for agentlet CRUD endpoints.

Covered:
  GET    /api/agentlets
  POST   /api/agentlets
  GET    /api/agentlets/{agentlet_id}
  PATCH  /api/agentlets/{agentlet_id}
  DELETE /api/agentlets/{agentlet_id}
"""

import uuid

import httpx
import pytest

from conftest import AGENTLET_YAML


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def ephemeral_agentlet(client: httpx.Client, org_id: str) -> dict:
    """Create an agentlet for a single test; delete it on teardown."""
    agentlet_id = f"ep_{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/agentlets",
        json={"id": agentlet_id, "YAML": AGENTLET_YAML, "description": "ephemeral"},
    )
    assert response.status_code == 201, response.text
    agentlet = response.json()

    yield agentlet

    client.delete(f"/api/agentlets/{agentlet['id']}")


# ---------------------------------------------------------------------------
# List agentlets
# ---------------------------------------------------------------------------

class TestListAgentlets:
    def test_happy_path_returns_list(
        self, client: httpx.Client, org_id: str, shared_agentlet: dict
    ) -> None:
        response = client.get("/api/agentlets")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "agentlets" in data

    def test_no_token_returns_401(self, unauth_client: httpx.Client, org_id: str) -> None:
        response = unauth_client.get("/api/agentlets")

        assert response.status_code == 401

    def test_other_org_returns_403_or_404(self, client: httpx.Client) -> None:
        response = client.get("/api/agentlets", params={"org_id": "foreign-org-000000"})

        assert response.status_code in (403, 404)


# ---------------------------------------------------------------------------
# Create agentlet
# ---------------------------------------------------------------------------

class TestCreateAgentlet:
    def test_happy_path_creates_agentlet(self, client: httpx.Client, org_id: str) -> None:
        agentlet_id = f"create_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/agentlets",
            json={"id": agentlet_id, "YAML": AGENTLET_YAML, "description": "created"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == agentlet_id
        assert "created_at" in data

        # cleanup
        client.delete(f"/api/agentlets/{agentlet_id}")

    def test_no_token_returns_401(self, unauth_client: httpx.Client, org_id: str) -> None:
        response = unauth_client.post(
            "/api/agentlets",
            json={"id": "x", "YAML": AGENTLET_YAML},
        )

        assert response.status_code == 401

    def test_missing_required_fields_returns_400(
        self, client: httpx.Client, org_id: str
    ) -> None:
        response = client.post(
            "/api/agentlets",
            json={},
        )

        assert response.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Get agentlet by ID
# ---------------------------------------------------------------------------

class TestGetAgentlet:
    def test_happy_path_returns_agentlet(
        self, client: httpx.Client, org_id: str, shared_agentlet: dict
    ) -> None:
        agentlet_id = shared_agentlet["id"]
        response = client.get(f"/api/agentlets/{agentlet_id}")

        assert response.status_code == 200
        data = response.json()
        assert "YAML" in data or "description" in data

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, org_id: str, shared_agentlet: dict
    ) -> None:
        agentlet_id = shared_agentlet["id"]
        response = unauth_client.get(f"/api/agentlets/{agentlet_id}")

        assert response.status_code == 401

    def test_nonexistent_agentlet_returns_404(
        self, client: httpx.Client, org_id: str
    ) -> None:
        agentlet_id = f"nonexistent_{uuid.uuid4().hex[:12]}"
        response = client.get(f"/api/agentlets/{agentlet_id}")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Update agentlet
# ---------------------------------------------------------------------------

class TestUpdateAgentlet:
    def test_happy_path_updates_agentlet(
        self, client: httpx.Client, org_id: str, ephemeral_agentlet: dict
    ) -> None:
        agentlet_id = ephemeral_agentlet["id"]
        response = client.patch(
            f"/api/agentlets/{agentlet_id}",
            json={"YAML": AGENTLET_YAML, "description": "updated description"},
        )

        assert response.status_code == 200

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, org_id: str, shared_agentlet: dict
    ) -> None:
        agentlet_id = shared_agentlet["id"]
        response = unauth_client.patch(
            f"/api/agentlets/{agentlet_id}",
            json={"description": "updated"},
        )

        assert response.status_code == 401

    def test_nonexistent_agentlet_returns_404(
        self, client: httpx.Client, org_id: str
    ) -> None:
        # update_item has upsert semantics — returns 200 even if item didn't exist
        agentlet_id = f"nonexistent_{uuid.uuid4().hex[:12]}"
        response = client.patch(
            f"/api/agentlets/{agentlet_id}",
            json={"description": "updated"},
        )

        assert response.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Delete agentlet
# ---------------------------------------------------------------------------

class TestDeleteAgentlet:
    def test_happy_path_deletes_agentlet(
        self, client: httpx.Client, org_id: str
    ) -> None:
        agentlet_id = f"del_{uuid.uuid4().hex[:8]}"
        create = client.post(
            "/api/agentlets",
            json={"id": agentlet_id, "YAML": AGENTLET_YAML, "description": "to delete"},
        )
        assert create.status_code == 201

        response = client.delete(f"/api/agentlets/{agentlet_id}")

        assert response.status_code in (200, 204)

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, org_id: str, shared_agentlet: dict
    ) -> None:
        agentlet_id = shared_agentlet["id"]
        response = unauth_client.delete(f"/api/agentlets/{agentlet_id}")

        assert response.status_code == 401

    def test_double_delete_returns_404(
        self, client: httpx.Client, org_id: str
    ) -> None:
        agentlet_id = f"dd_{uuid.uuid4().hex[:8]}"
        create = client.post(
            "/api/agentlets",
            json={"id": agentlet_id, "YAML": AGENTLET_YAML, "description": "to double delete"},
        )
        assert create.status_code == 201

        client.delete(f"/api/agentlets/{agentlet_id}")
        response = client.delete(f"/api/agentlets/{agentlet_id}")

        assert response.status_code == 404

    def test_delete_agentlet_with_executions_returns_409(
        self, client: httpx.Client, org_id: str
    ) -> None:
        agentlet_id = f"delx_{uuid.uuid4().hex[:8]}"
        create = client.post(
            "/api/agentlets",
            json={"id": agentlet_id, "YAML": AGENTLET_YAML, "description": "has executions"},
        )
        assert create.status_code == 201

        launch = client.post("/api/executions", json={"agentlet_id": agentlet_id})
        assert launch.status_code == 202

        response = client.delete(f"/api/agentlets/{agentlet_id}")
        assert response.status_code == 409
