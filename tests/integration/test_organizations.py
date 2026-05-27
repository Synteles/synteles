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

"""Integration tests for GET /api/organizations/{org_id}."""

import httpx


class TestGetOrganization:
    def test_happy_path_returns_org(self, client: httpx.Client, org_id: str) -> None:
        response = client.get(f"/api/organizations/{org_id}")

        assert response.status_code == 200
        data = response.json()
        assert "org_name" in data or "users" in data

    def test_no_token_returns_401(self, unauth_client: httpx.Client, org_id: str) -> None:
        response = unauth_client.get(f"/api/organizations/{org_id}")

        assert response.status_code == 401

    def test_nonexistent_org_returns_404(self, client: httpx.Client) -> None:
        response = client.get("/api/organizations/nonexistent-org-000000")

        assert response.status_code in (403, 404)
