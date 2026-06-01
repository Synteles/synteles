# Testing Guide

This document covers how to run and extend the Synteles test suite, which has two layers: per-service unit tests and a cross-service integration suite.

---

## Table of Contents

- [Unit Tests](#unit-tests)
- [Integration Tests](#integration-tests)
  - [Prerequisites](#prerequisites)
  - [Environment Setup](#environment-setup)
  - [Running the Suite](#running-the-suite)
  - [Test User Identities](#test-user-identities)
  - [Fixture Hierarchy](#fixture-hierarchy)
  - [What the Tests Cover](#what-the-tests-cover)
- [Adding New Tests](#adding-new-tests)

---

## Unit Tests

Each backend service has its own isolated unit test suite under `<service>/tests/`.

```
core-service/tests/
scheduler-service/tests/
```

Run them with the service `Makefile`:

```bash
# from the repo root
cd core-service      && make test
cd scheduler-service && make test
```

`make check` runs linting (ruff) and type-checking (mypy) alongside the tests. Both must pass before merging.

Unit tests run in-process with no live external dependencies. Database calls and external HTTP requests are mocked.

---

## Integration Tests

The integration suite lives in `tests/integration/`. It runs against a **live stack** (Traefik, core-service, scheduler-service, Keycloak, PostgreSQL, MinIO) and exercises the full request path from HTTP client through gateway to database.

### Prerequisites

Start the full stack:

```bash
docker compose up -d
```

All services must be healthy before running tests. Check with:

```bash
docker compose ps
```

### Environment Setup

Copy the example env file and adjust if needed:

```bash
cp tests/integration/.env.example tests/integration/.env
```

The defaults match the `docker compose` dev configuration and work out of the box for local runs. Key variables:

| Variable | Default | Purpose |
|---|---|---|
| `API_BASE_URL` | `http://localhost:8080` | Traefik gateway entry point |
| `OIDC_ISSUER_URL` | `http://localhost:8080/auth/realms/synteles` | Keycloak realm URL |
| `OIDC_CLIENT_ID` | `synteles-app` | OIDC client used to obtain test tokens |
| `OIDC_CLIENT_SECRET` | `synteles-dev-secret` | Must match `docker compose` value |
| `TEST_USER` | `synteles-test` | Integration test Keycloak user (see below) |
| `TEST_USER_PASSWORD` | `synteles-test` | Password for `TEST_USER` |
| `FRESH_USER` | `synteles-fresh` | Base username for provisioning tests (see below) |
| `FRESH_USER_PASSWORD` | `synteles-fresh` | Password for ephemeral fresh users |
| `KEYCLOAK_PROVISIONER_CLIENT_SECRET` | `provisioner-dev-secret` | Used to create/delete ephemeral Keycloak users |

### Running the Suite

```bash
cd tests/integration
uv run pytest           # full suite
uv run pytest -v        # verbose
uv run pytest test_users.py -v          # single file
uv run pytest -k "provisioning" -v     # by keyword
```

---

### Test User Identities

The Keycloak provisioner (`infra/keycloak/keycloak_provision.py`) creates three distinct users on startup. Each has a different role:

```
┌─────────────────────────────────────────────────────────┐
│              Keycloak (synteles realm)                   │
│                                                         │
│  synteles          ← DEFAULT_USER                       │
│  synteles-test     ← TEST_USER                          │
│  synteles-fresh    ← FRESH_USER base                    │
└─────────────────────────────────────────────────────────┘
```

| User | Env var | Purpose |
|---|---|---|
| `synteles` | `KEYCLOAK_DEFAULT_USER` | Human login account after `docker compose up`. Used for manual browser testing via the UI. **Never used by the test suite.** |
| `synteles-test` | `KEYCLOAK_TEST_USER` | Dedicated integration test identity. All session-scoped fixtures (agentlets, API keys, secrets) are created under this user. |
| `synteles-fresh` | `KEYCLOAK_FRESH_USER` | Credential template for the provisioning test fixture. Not used directly — the fixture derives a unique `synteles-fresh-{uuid}` user from it (see below). |

Keeping the human login user (`synteles`) separate from the test user (`synteles-test`) means test runs never pollute the developer's working environment.

---

### Fixture Hierarchy

All fixtures are session-scoped (set up once, shared across the whole test run). The dependency graph determines setup order:

```
access_token
    └── client ──────────────────────┐
            └── org_id               │
                    └── api_key ──── ├── shared_agentlet
                            └── apikey_client
```

| Fixture | What it does |
|---|---|
| `access_token` | Obtains a Keycloak JWT for `TEST_USER` via the Resource Owner Password Credentials (ROPC) grant. ROPC is only used in tests — never in production code. |
| `client` | `httpx.Client` with `Authorization: Bearer {access_token}`. Used by all private-route tests. |
| `unauth_client` | `httpx.Client` with no credentials. Used to verify 401 responses. |
| `org_id` | Calls `GET /api/users/me` to lazy-provision the test user and return their `org_id`. Must resolve before any fixture that creates org-scoped resources. |
| `api_key` | Creates a platform API key for the session (depends on `org_id` to ensure user is provisioned first). Deletes the key on teardown. |
| `apikey_client` | `httpx.Client` with `X-API-Key: {api_key}`. Used by public-route and API key tests. |
| `shared_agentlet` | Creates one agentlet for the session; deletes it on teardown. |
| `fresh_user_client` | See [Provisioning tests](#provisioning-tests) below. |

---

### What the Tests Cover

#### Authentication enforcement (`test_auth_enforcement.py`)

Verifies that Traefik's `forwardAuth` middleware correctly enforces which credential type is accepted per route group. This cannot be covered by unit tests because the enforcement lives in Traefik configuration, not application code.

```
/api/public/*  →  api-key-auth middleware  →  X-API-Key only
/api/*         →  jwt-auth middleware       →  Bearer JWT only
```

Tests confirm:
- API key accepted on public routes, JWT rejected
- JWT accepted on private routes, API key rejected

#### User provisioning (`test_users.py` — `TestUserProvisioning`)

The provisioning path is the first-login flow where `GET /api/users/me` creates a user record and a default "Personal Workspace" organisation in PostgreSQL if neither exists yet.

To exercise this path on every test run (not just the first), the `fresh_user_client` fixture creates a **unique ephemeral Keycloak user** per session:

```
Session start
    ↓
fresh_user_client fixture
    ├── get synteles-provisioner service-account token
    ├── POST /admin/realms/synteles/users   → creates synteles-fresh-{uuid}
    ├── ROPC token for synteles-fresh-{uuid}
    └── yields httpx.Client

Tests run
    ↓  GET /api/users/me   → no DB record → _provision_user() runs
                           → org created → org_id returned
    ↓  GET /api/users/me   → user exists → _build_profile() runs (idempotent)
    ↓  GET /api/agentlets  → gateway injects X-Org-Id → 200
    ↓  POST /api/users/apikeys → org_id available → 200

Session end
    └── DELETE /admin/realms/synteles/users/{user_id}  (Keycloak only)
```

The ephemeral user's DB record (user + org) remains after teardown — it is test data and does not affect other runs because each session generates a different UUID suffix.

Provisioning tests verify:
- First call to `users/me` returns 200 with `sub`, `org_id`, `org_name`
- `org_id` is a valid UUID
- Second call returns the same `org_id` (idempotent)
- After provisioning, `GET /api/agentlets` passes gateway auth
- After provisioning, `POST /api/users/apikeys` succeeds

---

## Adding New Tests

**Add to an existing file** when the test belongs to an existing resource (agentlets, secrets, etc.). **Create a new file** when covering a new resource or cross-cutting concern.

File naming: `test_<resource>.py`. Class naming: `Test<Action><Resource>` (e.g. `TestCreateAgentlet`).

For tests that need an authenticated client, use the session fixtures from `conftest.py`:

```python
class TestMyFeature:
    def test_happy_path(self, client: httpx.Client, org_id: str) -> None:
        response = client.get("/api/my-resource")
        assert response.status_code == 200
```

For tests that need an API key client (public routes):

```python
def test_api_key_route(self, apikey_client: httpx.Client) -> None:
    response = apikey_client.get("/api/public/agentlets/my-agentlet")
    assert response.status_code == 200
```

For first-login provisioning tests, use `fresh_user_client` — it guarantees a clean DB slate:

```python
def test_provisioning_behaviour(self, fresh_user_client: httpx.Client) -> None:
    response = fresh_user_client.get("/api/users/me")
    assert response.status_code == 200
```

Do not share mutable state between tests via fixtures — all session fixtures are read-only after setup, or perform explicit cleanup in teardown.
