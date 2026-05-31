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

"""Integration tests for gateway-level authentication enforcement.

These tests verify that Traefik's middleware configuration correctly restricts
which credential type is accepted per route group:
  - /api/public/* accepts X-API-Key only  (api-key-auth middleware)
  - /api/*        accepts Bearer JWT only  (jwt-auth middleware)

Unit tests cannot cover this — the enforcement lives in Traefik config,
not in application code.
"""

import httpx
import pytest


# ---------------------------------------------------------------------------
# Public routes: X-API-Key accepted, Bearer JWT rejected
# ---------------------------------------------------------------------------

class TestPublicRouteEnforcement:
    def test_api_key_accepted_on_public_route(
        self, apikey_client: httpx.Client, shared_agentlet: dict
    ) -> None:
        response = apikey_client.get(f"/api/public/agentlets/{shared_agentlet['id']}")
        assert response.status_code == 200

    def test_jwt_rejected_on_public_route(
        self, client: httpx.Client, shared_agentlet: dict
    ) -> None:
        """Bearer JWT must be rejected on public routes (api-key-auth strips Authorization)."""
        response = client.get(f"/api/public/agentlets/{shared_agentlet['id']}")
        assert response.status_code == 401

    def test_jwt_rejected_on_public_execution_post(
        self, client: httpx.Client, shared_agentlet: dict
    ) -> None:
        response = client.post(
            f"/api/public/agentlets/{shared_agentlet['id']}/executions",
            json={},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Private routes: Bearer JWT accepted, X-API-Key rejected
# ---------------------------------------------------------------------------

class TestPrivateRouteEnforcement:
    def test_jwt_accepted_on_private_route(self, client: httpx.Client) -> None:
        response = client.get("/api/users/apikeys")
        assert response.status_code == 200

    def test_api_key_rejected_on_private_route(self, apikey_client: httpx.Client) -> None:
        """X-API-Key must be rejected on private routes (jwt-auth strips X-API-Key)."""
        response = apikey_client.get("/api/users/apikeys")
        assert response.status_code == 401

    def test_api_key_rejected_on_private_agentlets_route(
        self, apikey_client: httpx.Client
    ) -> None:
        response = apikey_client.get("/api/agentlets")
        assert response.status_code == 401
