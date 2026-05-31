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

"""
Session-level fixtures for Synteles Platform integration tests.

Required environment variables (see .env.example):
  API_BASE_URL                       Base URL of the Synteles API (e.g. http://localhost:8080)
  OIDC_ISSUER_URL                    Keycloak realm URL (e.g. http://localhost:8080/auth/realms/synteles)
  OIDC_CLIENT_ID                     OIDC client ID (default: synteles-app)
  OIDC_CLIENT_SECRET                 OIDC client secret
  TEST_USER                          Username of the test user (default: synteles)
  TEST_USER_PASSWORD                 Password of the test user (default: synteles)
  FRESH_USER                         Base username for provisioning tests (default: synteles-fresh)
  FRESH_USER_PASSWORD                Password for FRESH_USER (default: synteles-fresh)
  KEYCLOAK_PROVISIONER_CLIENT_SECRET Secret for synteles-provisioner client (default: provisioner-dev-secret)
"""

import os
import uuid

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Required environment variable '{name}' is not set. "
            "Copy .env.example to .env and populate it."
        )
    return value


def _get_token_via_password_grant(
    issuer_url: str,
    client_id: str,
    client_secret: str,
    username: str,
    password: str,
) -> str:
    """Obtain an OIDC access token using the Resource Owner Password Credentials grant.

    Keycloak supports ROPC in dev mode. This grant is intentionally used only
    in integration tests — never in production code.
    """
    with httpx.Client(timeout=30.0) as c:
        resp = c.post(
            f"{issuer_url}/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": client_id,
                "client_secret": client_secret,
                "username": username,
                "password": password,
                "scope": "openid",
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Token request failed ({resp.status_code}): {resp.text[:300]}\n"
                "Check OIDC_ISSUER_URL, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, "
                "TEST_USER, TEST_USER_PASSWORD."
            )
        return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Session-scoped: environment config
# ---------------------------------------------------------------------------

def rewrite_presigned_url(url: str) -> str:
    """Replace the internal S3 hostname with the publicly reachable one.

    When tests run outside Docker, presigned URLs contain the container-internal
    S3 endpoint (e.g. http://minio:9000). S3_INTERNAL_ENDPOINT_URL and
    S3_PUBLIC_ENDPOINT_URL let the test suite rewrite those URLs so direct
    fetches succeed from the host machine.
    """
    internal = os.environ.get("S3_INTERNAL_ENDPOINT_URL", "").rstrip("/")
    public = os.environ.get("S3_PUBLIC_ENDPOINT_URL", "").rstrip("/")
    if internal and public and url.startswith(internal):
        return public + url[len(internal):]
    return url


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return _require_env("API_BASE_URL").rstrip("/")


# ---------------------------------------------------------------------------
# Session-scoped: OIDC access token
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def access_token() -> str:
    """Obtain an OIDC access token for the test user via Keycloak ROPC grant."""
    issuer_url = _require_env("OIDC_ISSUER_URL").rstrip("/")
    client_id = os.environ.get("OIDC_CLIENT_ID", "synteles-app")
    client_secret = _require_env("OIDC_CLIENT_SECRET")
    username = os.environ.get("TEST_USER", "synteles")
    password = os.environ.get("TEST_USER_PASSWORD", "synteles")

    return _get_token_via_password_grant(
        issuer_url=issuer_url,
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
    )


# ---------------------------------------------------------------------------
# Session-scoped: httpx clients
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def client(api_base_url: str, access_token: str) -> httpx.Client:
    """httpx client pre-configured with OIDC Bearer token."""
    with httpx.Client(
        base_url=api_base_url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30.0,
    ) as c:
        yield c


@pytest.fixture(scope="session")
def unauth_client(api_base_url: str) -> httpx.Client:
    """httpx client with no Authorization header — for 4xx failure paths."""
    with httpx.Client(base_url=api_base_url, timeout=10.0) as c:
        yield c


# ---------------------------------------------------------------------------
# Session-scoped: org_id (resolved from /api/users/me — lazy-provisions user)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def org_id(client: httpx.Client) -> str:
    """Resolve the test user's org_id via GET /api/users/me.

    The first call creates the user + org in PostgreSQL if they don't exist yet.
    """
    resp = client.get("/api/users/me")
    assert resp.status_code == 200, (
        f"GET /api/users/me failed ({resp.status_code}): {resp.text}"
    )
    data = resp.json()
    assert "org_id" in data, f"org_id missing from /api/users/me response: {data}"
    return data["org_id"]


# ---------------------------------------------------------------------------
# Session-scoped: API key (created once, deleted on teardown)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def api_key(client: httpx.Client, org_id: str) -> str:
    """Create a platform API key for the session; delete it after all tests."""
    response = client.post("/api/users/apikeys", json={"key_name": "integration-test-key"})
    assert response.status_code == 200, (
        f"Failed to create API key for test session: {response.text}"
    )
    data = response.json()
    key_id = data["key_id"]
    raw_key = data["key"]

    yield raw_key

    client.delete(f"/api/users/apikeys/{key_id}")


@pytest.fixture(scope="session")
def apikey_client(api_base_url: str, api_key: str) -> httpx.Client:
    """httpx client pre-configured with platform API key."""
    with httpx.Client(
        base_url=api_base_url,
        headers={"X-API-Key": api_key},
        timeout=30.0,
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Session-scoped: shared test agentlet (read-only tests reuse this)
# ---------------------------------------------------------------------------

_AGENTLET_PROVIDER = os.environ.get("AGENTLET_PROVIDER", "bedrock")
_AGENTLET_MODEL_ID = os.environ.get("AGENTLET_MODEL_ID", "meta.llama3-2-1b-instruct-v1:0")

AGENTLET_YAML = f"""\
agentlet:
  name: "simple-assistant"
  version: "1.0.0"

prompt: "What is the capital of France?"

system_prompt: |
  You are a helpful assistant that can answer questions and help with tasks.
  Be concise and clear in your responses.

model:
  provider: "{_AGENTLET_PROVIDER}"
  model_id: "{_AGENTLET_MODEL_ID}"
  parameters:
    temperature: 0.7
    max_tokens: 2048

resource_limits:
  max_execution_time: 60
  max_tokens: 2048

output:
  format: "text"
  streaming: false
  show_reasoning: false
  show_tool_calls: false
"""


# ---------------------------------------------------------------------------
# Session-scoped: fresh (unprovisioned) user for provisioning tests
#
# Each session creates a unique Keycloak user derived from FRESH_USER so it
# is guaranteed to have no record in the Synteles DB. The user is deleted
# from Keycloak on teardown. The DB record (created by users/me) is harmless
# leftover data — it does not affect other tests.
# ---------------------------------------------------------------------------

def _keycloak_admin_url(issuer_url: str) -> str:
    """Derive the Keycloak admin REST URL from the realm issuer URL.

    e.g. http://localhost:8080/auth/realms/synteles
      → http://localhost:8080/auth/admin/realms/synteles
    """
    base, realm_part = issuer_url.rstrip("/").rsplit("/realms/", 1)
    return f"{base}/admin/realms/{realm_part}"


def _get_provisioner_admin_token(issuer_url: str, provisioner_secret: str) -> str:
    """Get a service-account token for synteles-provisioner (has manage-users role)."""
    with httpx.Client(timeout=15.0) as c:
        resp = c.post(
            f"{issuer_url}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "synteles-provisioner",
                "client_secret": provisioner_secret,
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Provisioner token request failed ({resp.status_code}): {resp.text[:300]}"
            )
        return resp.json()["access_token"]


@pytest.fixture(scope="session")
def fresh_user_client(api_base_url: str) -> httpx.Client:
    """httpx client for a brand-new user guaranteed not to exist in the Synteles DB.

    Creates a unique Keycloak user (FRESH_USER + short UUID suffix) via the
    provisioner service account, obtains an ROPC access token, and yields a
    pre-configured httpx.Client. The Keycloak user is deleted on teardown.
    """
    issuer_url = _require_env("OIDC_ISSUER_URL").rstrip("/")
    client_id = os.environ.get("OIDC_CLIENT_ID", "synteles-app")
    client_secret = _require_env("OIDC_CLIENT_SECRET")
    provisioner_secret = os.environ.get(
        "KEYCLOAK_PROVISIONER_CLIENT_SECRET", "provisioner-dev-secret"
    )
    fresh_base = os.environ.get("FRESH_USER", "synteles-fresh")
    fresh_password = os.environ.get("FRESH_USER_PASSWORD", "synteles-fresh")

    admin_url = _keycloak_admin_url(issuer_url)
    admin_token = _get_provisioner_admin_token(issuer_url, provisioner_secret)
    auth_headers = {"Authorization": f"Bearer {admin_token}"}

    # Unique username per session — never exists in Synteles DB
    username = f"{fresh_base}-{uuid.uuid4().hex[:8]}"

    with httpx.Client(timeout=15.0) as adm:
        create_resp = adm.post(
            f"{admin_url}/users",
            headers=auth_headers,
            json={
                "username": username,
                "email": f"{username}@synteles.local",
                "firstName": "Fresh",
                "lastName": "TestUser",
                "enabled": True,
                "emailVerified": True,
                "credentials": [{"type": "password", "value": fresh_password, "temporary": False}],
            },
        )
        if create_resp.status_code not in (201, 409):
            raise RuntimeError(
                f"Failed to create fresh Keycloak user ({create_resp.status_code}): "
                f"{create_resp.text[:300]}"
            )
        # Location header: .../users/{user_id}
        user_id = create_resp.headers.get("Location", "").rstrip("/").rsplit("/", 1)[-1]

    access_token = _get_token_via_password_grant(
        issuer_url=issuer_url,
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=fresh_password,
    )

    with httpx.Client(
        base_url=api_base_url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30.0,
    ) as c:
        yield c

    # Teardown: remove the ephemeral user from Keycloak
    if user_id:
        admin_token = _get_provisioner_admin_token(issuer_url, provisioner_secret)
        with httpx.Client(timeout=15.0) as adm:
            adm.delete(
                f"{admin_url}/users/{user_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )


@pytest.fixture(scope="session")
def shared_agentlet(client: httpx.Client, org_id: str) -> dict:
    """Create one agentlet for the session; delete it on teardown."""
    agentlet_id = f"inttest_{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/agentlets",
        json={"id": agentlet_id, "YAML": AGENTLET_YAML, "description": "integration test"},
    )
    assert response.status_code == 201, (
        f"Failed to create shared agentlet for test session: {response.text}"
    )
    agentlet = response.json()

    yield agentlet

    client.delete(f"/api/agentlets/{agentlet['id']}")

