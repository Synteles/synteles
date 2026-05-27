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

"""Integration tests for GET /api/users/me."""

import httpx


class TestGetMe:
    def test_happy_path_returns_user(self, client: httpx.Client) -> None:
        response = client.get("/api/users/me")

        assert response.status_code == 200
        data = response.json()
        assert "email" in data or "user_id" in data or "sub" in data

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
