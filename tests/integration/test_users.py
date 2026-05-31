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

"""Integration tests for /api/users/me and the first-login provisioning flow."""

import uuid

import httpx


class TestGetMe:
    def test_happy_path_returns_user(self, client: httpx.Client) -> None:
        response = client.get("/api/users/me")

        assert response.status_code == 200
        data = response.json()
        assert "sub" in data
        assert "org_id" in data
        assert "org_name" in data

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        response = unauth_client.get("/api/users/me")

        assert response.status_code == 401

    def test_invalid_token_returns_401(self, api_base_url: str) -> None:
        with httpx.Client(
            base_url=api_base_url,
            headers={"Authorization": "Bearer this.is.not.valid"},
            timeout=10.0,
        ) as c:
            response = c.get("/api/users/me")

        assert response.status_code == 401


class TestUserProvisioning:
    """Verify the first-login lazy-provisioning path end-to-end.

    Uses a fresh_user_client whose Keycloak user was created this session and
    has never touched the Synteles DB, so every test run exercises the actual
    provisioning code path (not a returning-user shortcut).
    """

    def test_first_call_returns_200_with_org(
        self, fresh_user_client: httpx.Client
    ) -> None:
        """First /api/users/me for an unprovisioned user must create and return an org."""
        response = fresh_user_client.get("/api/users/me")

        assert response.status_code == 200
        data = response.json()
        assert "sub" in data, f"Missing 'sub' in response: {data}"
        assert "org_id" in data, f"Missing 'org_id' in response: {data}"
        assert "org_name" in data, f"Missing 'org_name' in response: {data}"

    def test_org_id_is_valid_uuid(self, fresh_user_client: httpx.Client) -> None:
        response = fresh_user_client.get("/api/users/me")

        assert response.status_code == 200
        org_id = response.json().get("org_id", "")
        try:
            uuid.UUID(org_id)
        except ValueError:
            raise AssertionError(f"org_id is not a valid UUID: {org_id!r}")

    def test_second_call_returns_same_org_id(
        self, fresh_user_client: httpx.Client
    ) -> None:
        """Provisioning must be idempotent — repeated calls return the same org."""
        r1 = fresh_user_client.get("/api/users/me")
        r2 = fresh_user_client.get("/api/users/me")

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["org_id"] == r2.json()["org_id"]

    def test_provisioned_user_can_list_agentlets(
        self, fresh_user_client: httpx.Client
    ) -> None:
        """After provisioning, the user's JWT must pass gateway auth for private routes."""
        # Ensure provisioning has happened first
        me = fresh_user_client.get("/api/users/me")
        assert me.status_code == 200

        response = fresh_user_client.get("/api/agentlets")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_provisioned_user_can_create_api_key(
        self, fresh_user_client: httpx.Client
    ) -> None:
        """After provisioning, the user must be able to create an API key."""
        me = fresh_user_client.get("/api/users/me")
        assert me.status_code == 200

        response = fresh_user_client.post(
            "/api/users/apikeys",
            json={"key_name": "provisioning-test-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "key_id" in data
        assert "key" in data

        # Clean up
        fresh_user_client.delete(f"/api/users/apikeys/{data['key_id']}")
