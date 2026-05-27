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

"""Integration tests for public API key-authenticated endpoints.

Covered:
  GET  /api/public/agentlets/{agentlet_id}
  POST /api/public/agentlets/{agentlet_id}/executions
  GET  /api/public/executions/{execution_id}
"""

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def public_execution(
    apikey_client: httpx.Client, shared_agentlet: dict, client: httpx.Client
) -> dict:
    """Launch a public execution; terminate it on teardown via authenticated client."""
    agentlet_id = shared_agentlet["id"]
    response = apikey_client.post(
        f"/api/public/agentlets/{agentlet_id}/executions",
        json={"timeout": 60},
    )
    assert response.status_code == 202, (
        f"Failed to launch public execution: {response.text}"
    )
    execution = response.json()

    yield execution

    # Terminate via Cognito client (public endpoint has no DELETE)
    client.delete(f"/api/executions/{execution['execution_id']}")


# ---------------------------------------------------------------------------
# GET /api/public/agentlets/{agentlet_id}
# ---------------------------------------------------------------------------

class TestGetPublicAgentlet:
    def test_happy_path_returns_agentlet(
        self, apikey_client: httpx.Client, shared_agentlet: dict
    ) -> None:
        agentlet_id = shared_agentlet["id"]
        response = apikey_client.get(f"/api/public/agentlets/{agentlet_id}")

        assert response.status_code == 200
        data = response.json()
        assert "agentlet_id" in data or "id" in data or "yaml" in data or "YAML" in data or "description" in data

    def test_no_api_key_returns_401_or_403(
        self, unauth_client: httpx.Client, shared_agentlet: dict
    ) -> None:
        agentlet_id = shared_agentlet["id"]
        response = unauth_client.get(f"/api/public/agentlets/{agentlet_id}")

        assert response.status_code in (401, 403)

    def test_nonexistent_agentlet_returns_404(
        self, apikey_client: httpx.Client
    ) -> None:
        response = apikey_client.get("/api/public/agentlets/does-not-exist-000")

        assert response.status_code in (403, 404)


# ---------------------------------------------------------------------------
# POST /api/public/agentlets/{agentlet_id}/executions
# ---------------------------------------------------------------------------

class TestPublicLaunchExecution:
    def test_happy_path_returns_202(
        self, apikey_client: httpx.Client, shared_agentlet: dict, client: httpx.Client
    ) -> None:
        agentlet_id = shared_agentlet["id"]
        response = apikey_client.post(
            f"/api/public/agentlets/{agentlet_id}/executions",
            json={"timeout": 60},
        )

        assert response.status_code == 202
        data = response.json()
        assert "execution_id" in data

        # cleanup via authenticated client
        client.delete(f"/api/executions/{data['execution_id']}")

    def test_no_body_returns_202(
        self, apikey_client: httpx.Client, shared_agentlet: dict, client: httpx.Client
    ) -> None:
        """POST with no request body at all must return 202.

        Regression test: json.loads(None) previously raised TypeError → 400,
        so public API executions with an omitted body were silently dropped
        and never appeared in the execution log.
        """
        agentlet_id = shared_agentlet["id"]
        response = apikey_client.post(
            f"/api/public/agentlets/{agentlet_id}/executions",
        )

        assert response.status_code == 202
        data = response.json()
        assert "execution_id" in data

        client.delete(f"/api/executions/{data['execution_id']}")

    def test_empty_json_body_returns_202(
        self, apikey_client: httpx.Client, shared_agentlet: dict, client: httpx.Client
    ) -> None:
        """POST with an explicit empty JSON body {} must return 202."""
        agentlet_id = shared_agentlet["id"]
        response = apikey_client.post(
            f"/api/public/agentlets/{agentlet_id}/executions",
            json={},
        )

        assert response.status_code == 202
        data = response.json()
        assert "execution_id" in data

        client.delete(f"/api/executions/{data['execution_id']}")

    def test_no_api_key_returns_401_or_403(
        self, unauth_client: httpx.Client, shared_agentlet: dict
    ) -> None:
        agentlet_id = shared_agentlet["id"]
        response = unauth_client.post(
            f"/api/public/agentlets/{agentlet_id}/executions",
            json={},
        )

        assert response.status_code in (401, 403)

    def test_nonexistent_agentlet_returns_404(
        self, apikey_client: httpx.Client
    ) -> None:
        response = apikey_client.post(
            "/api/public/agentlets/does-not-exist-000/executions",
            json={},
        )

        assert response.status_code in (403, 404)


# ---------------------------------------------------------------------------
# GET /api/public/executions/{execution_id}
# ---------------------------------------------------------------------------

class TestPublicGetExecutionStatus:
    def test_happy_path_returns_status(
        self, apikey_client: httpx.Client, public_execution: dict
    ) -> None:
        execution_id = public_execution["execution_id"]
        response = apikey_client.get(f"/api/public/executions/{execution_id}")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ("deploying", "running", "completed", "failed", "terminated")

    def test_no_api_key_returns_401_or_403(
        self, unauth_client: httpx.Client, public_execution: dict
    ) -> None:
        execution_id = public_execution["execution_id"]
        response = unauth_client.get(f"/api/public/executions/{execution_id}")

        assert response.status_code in (401, 403)

    def test_nonexistent_execution_returns_404(
        self, apikey_client: httpx.Client
    ) -> None:
        response = apikey_client.get(
            "/api/public/executions/00000000-0000-0000-0000-000000000000"
        )

        assert response.status_code == 404
