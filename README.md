<p align="center">
  <img src="docs/images/synteles_logo.png" alt="Synteles Logo" width="360"/>
</p>

# Synteles

[![GitHub Release](https://img.shields.io/github/v/release/Synteles/synteles?include_prereleases)](https://github.com/Synteles/synteles/releases/latest)
[![CI](https://github.com/Synteles/synteles/actions/workflows/ci.yml/badge.svg)](https://github.com/Synteles/synteles/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Synteles/synteles/actions/workflows/codeql.yml/badge.svg)](https://github.com/Synteles/synteles/actions/workflows/codeql.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Powered by Synteles Agentlet](https://img.shields.io/badge/powered%20by-Synteles%20Agentlet-6f42c1)](https://github.com/Synteles/agentlet)

**Open-source platform for AI workers and resilient enterprise workflows.**

Synteles is a platform for AI workers, called ([agentlets](https://github.com/Synteles/agentlet)), that execute resilient long-running workflows. Business users can describe tasks in plain language, and Synteles generates and launches multi-agent AI workers in minutes. Engineers can customize them using a [YAML definition](https://github.com/Synteles/agentlet/blob/main/docs/reference/configuration.md) and integrate into existing systems via [APIs](docs/integration-api.md) and MCP connectors. AI workers can run as quick tasks or as stateful workflows that survive failures, resume after restarts, and pause for human input. Synteles runs locally and designed for self-hosted, cloud, on-premises, and air-gapped environments.

⚠️ **Early Development**: Synteles is pre-v1.0. APIs, definitions, and deployment structure may change.

**If you find this useful, please consider [starring this repository](https://github.com/Synteles/synteles) to help other developers discover it!** ⭐

<img src="docs/images/Screenshot1.png" width="49%"/> <img src="docs/images/Screenshot2.png" width="49%"/>
<img src="docs/images/Screenshot3.png" width="49%"/> <img src="docs/images/Screenshot4.png" width="49%"/>

## Why Synteles?

Synteles is designed for organizations that need AI workers to be:

- **Fast to launch**: business teams can describe workflows and run AI workers in minutes.
- **Customizable**: agentlets are defined in YAML and can be reviewed, and adapted by engineers.
- **Stateful**: long-running workflows can survive failures and wait for human input.
- **Portable**: run locally with Docker Compose and evolve toward controlled infrastructure deployments.
- **Traceable**: executions expose tool calls, workflow state, and operational history.

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 24+ with Docker Compose v2

### First-time setup

**1. Clone the repository**

```bash
git clone https://github.com/Synteles/synteles.git
cd synteles
```

**2. Run the install script**

```bash
./install.sh
```

The script walks you through selecting LLM providers and generates `.env` and `platform.toml`. Open `.env` after the script finishes and fill in your provider API keys.

**3. Start the stack**

```bash
docker compose up -d
```

Docker Compose will:
- Start PostgreSQL and run database migrations
- Start MinIO and create the required buckets
- Start Keycloak and provision the realm, client, and default user
- Start the core and scheduler API services
- Start Temporal server and its dependency services (Cassandra/PostgreSQL backend)
- Start the web UI, synte service and API gateway (Traefik)

First boot takes approximately 60–90 seconds while Keycloak initializes. You can watch progress with:

```bash
docker compose logs -f
```

All services are ready when `docker compose ps` shows every container as `healthy` or `exited 0` (one-shot init containers).

**4. Open the UI**

```text
http://localhost:3000
```

Log in with the default credentials:

| Field    | Value      |
|----------|------------|
| Username | `synteles` |
| Password | `synteles` |

### Local consoles and endpoints

Once the stack is running, these URLs are available in your browser:

| Console / Service         | URL                                    | Login                          | What it's for                                      |
|---------------------------|----------------------------------------|--------------------------------|----------------------------------------------------|
| **Synteles UI**           | http://localhost:3000                  | `synteles` / `synteles`        | Main product console — manage agentlets, run executions, view conversations |
| **Keycloak Admin**        | http://localhost:8080/auth/admin       | `admin` / `admin`              | Identity provider — manage users, clients, and realm settings |
| **MinIO Console**         | http://localhost:9001                  | `minioadmin` / `minioadmin`    | Object storage — browse uploaded files, execution logs, and conversation blobs |
| **Traefik Dashboard**     | http://localhost:8081                  | _(no login)_                   | API gateway — inspect routing rules, service health, and middleware |
| **Temporal Web UI**       | http://localhost:8088                  | _(no login)_                   | Temporal cluster UI — inspect durable workflow history, task queues, and execution state |
| **API (all routes)**      | http://localhost:8080                  | Bearer token or API key        | Entry point for all API calls (proxied via Traefik) |

> Default credentials are for local development only. Change them before any shared, remote, or production-like deployment. See the [Production Checklist](docs/configuration.md#production-checklist) in the configuration reference for the full list of values to rotate.

---

### Stop and start

**Stop the stack (data is preserved)**

```bash
docker compose down
```

PostgreSQL and MinIO data are stored in Docker named volumes (`postgres_data`, `minio_data`) and survive a `down`.

**Start again after a stop**

```bash
docker compose up -d
```

Keycloak re-imports the realm configuration on startup, but the provisioner script is idempotent — re-running is safe.

**Full reset (deletes all data)**

```bash
docker compose down -v
```

The `-v` flag removes the named volumes. The next `up` will run migrations and provisioning from scratch.

**Rebuild service images after a code change**

```bash
docker compose up -d --build
```

Only the services with changed Dockerfiles will be rebuilt.

---

### Configuration

There are two local configuration files, both git-ignored:

| File | Purpose |
|---|---|
| `.env` | Secrets and credentials (API keys, Keycloak passwords, encryption key) |
| `platform.toml` | Platform model configuration (chat model, platform default models) |

Both are generated by `install.sh`. To set up manually, copy the examples and fill in your values:

```bash
cp .env.example .env
cp platform.toml.example platform.toml
```

#### Chat engine model

The Synte chat assistant model is configured in `platform.toml` under the `[chat]` section:

```toml
[chat]
model_id    = "openai/gpt-4o"
secret_name = "openai"
```

`model_id` is a [LiteLLM-supported model string](https://docs.litellm.ai/docs/providers). `secret_name` references the matching `PLATFORM_SECRET_*` credential in `.env`. E.g. if secret_name is `openai`, then `PLATFORM_SECRET_OPENAI` defines the platform secret itself (see below the format of `PLATFORM_SECRET_*`).

#### Web search (Tavily)

Synteles uses web search capability for Synte assistant and newly created agentlets using Tavily and therefore needs a Tavily API key. Get a free key at [app.tavily.com](https://app.tavily.com). Once set, the key is automatically available to every agentlet — no per-agentlet configuration needed.

```env
TAVILY_API_KEY=tvly-...
```

#### Model credentials

All model credentials — for both the chat engine and platform default models — are configured the same way.

Each model entry in `platform.toml` has a `secret_name` field. Add a matching `PLATFORM_SECRET_<SECRET_NAME>` entry in `.env` with the provider credentials as a JSON object:

```env
PLATFORM_SECRET_OPENAI={"OPENAI_API_KEY": "sk-..."}
PLATFORM_SECRET_AZURE_AI={"AZURE_AI_API_KEY": "...", "AZURE_AI_API_BASE": "https://my-deployment.openai.azure.com"}
PLATFORM_SECRET_ANTHROPIC={"ANTHROPIC_API_KEY": "sk-ant-..."}
PLATFORM_SECRET_BEDROCK={"AWS_ACCESS_KEY_ID": "...", "AWS_SECRET_ACCESS_KEY": "...", "AWS_REGION_NAME": "eu-central-1"}
```

Models without a matching secret are silently skipped at execution time — the platform continues to work with whichever models are configured.

To add a new platform model or change its metadata (label, description, temperatures), edit `platform.toml` and restart the stack. See `platform.toml.example` for the format.

> For a complete field-by-field reference for both `.env` and `platform.toml`, see [docs/configuration.md](docs/configuration.md).

## Repository Structure

```text
synteles/
  core-service/         # REST API — agentlets, users, secrets, files, org management
  scheduler-service/    # Execution engine — deploys and monitors agentlet containers (see Agentlet Runtime below)
  durable-worker/       # Temporal worker service — AgentWorkflow (ReAct loop + HITL) for durable executions
  synte-service/        # Synte chat assistant — AI agent powering the chat UI
  ux-console/           # Web UI — Next.js frontend (App Router)
  platform-db/          # Shared database library (synteles_db) + Alembic migrations
  platform.toml         # Runtime platform configuration (chat model, platform default models)
  infra/                # Infrastructure definitions — Keycloak realm, Traefik routing
  docs/                 # Documentation
  tests/                # Integration test suite
  docker-compose.yml    # Local development environment
  install.sh            # First-time setup script
```

## Agentlet Runtime

Synteles supports two execution backends, configurable per agentlet via the `execution_backend` field:

**Standard** (`execution_backend: standard`, default) — each execution runs inside an isolated Docker container using the [Synteles Agentlet](https://github.com/Synteles/agentlet) harness. The harness reads the agentlet's YAML definition, injects secrets, reads input files, and runs the agent loop. The default image is `synteles/agentlet:edge`.

**Durable** (`execution_backend: durable`) — each execution is wrapped in a long-lived [Temporal](https://temporal.io) workflow, handled by the `durable-worker` service. Durable executions persist full workflow history, survive container crashes (Temporal keeps retrying), and support human-in-the-loop (HITL) pausing: when an agentlet calls `ask_user`, the execution transitions to `waiting_for_signal` and waits indefinitely for a user response via the signal API before continuing. See [docs/durable-execution.md](docs/durable-execution.md) for the full architecture.

See the [Configuration](#configuration) section and [docs/configuration.md](docs/configuration.md) for how to pin a specific agentlet image release tag via `AGENTLET_IMAGE`.

## Documentation

- [docs/architecture.md](docs/architecture.md) — system overview and component diagram
- [docs/integration-api.md](docs/integration-api.md) — integration API reference
- [docs/configuration.md](docs/configuration.md) — configuration reference: all environment variables and `platform.toml` fields
- [docs/durable-execution.md](docs/durable-execution.md) — durable execution architecture (Temporal, AgentWorkflow, HITL signal bridge)
- [docs/testing.md](docs/testing.md) — unit and integration test guide

## Project Status

Synteles is in early development.

Not yet guaranteed:

- Stable APIs
- Backward-compatible workflow definitions
- Production-ready defaults
- Long-term support guarantees

**Agentlet image channel:** the default agentlet runtime image is `synteles/agentlet:edge`, which tracks the latest development build. For production use or reproducible deployments, pin a specific release tag by setting `AGENTLET_IMAGE` in your `.env`:

```env
AGENTLET_IMAGE=synteles/agentlet:1.2.3
```

Stable release tags are published alongside each GitHub release. See [docs/configuration.md](docs/configuration.md) for full details.

## Roadmap

Planned areas of work include:

- Examples of agentlet definitions
- Kubernetes deployment support with Helm charts
- Evals framework 
- Guardrails implementation
- Security hardening
- Governance, identity, and access management enhancements
- Agentlet versioning
- API and configuration stabilization
- Documentation and developer experience improvements

The roadmap may change based on user feedback and maintainer capacity.

## Contributing

Contributions are welcome.

Good first contribution areas include:

- Bug reports and reproducible issues
- Documentation improvements
- Examples of agentlet definitions
- Tests
- Docker Compose and local setup improvements
- Kubernetes / Helm deployment templates
- Security hardening suggestions


Please read:

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [SECURITY.md](SECURITY.md)
- [GOVERNANCE.md](GOVERNANCE.md)

Synteles uses the Developer Certificate of Origin. Contributions must be signed off.

## Responsible AI-Assisted Contributions

AI-assisted coding is allowed, but contributors remain responsible for the code they submit.

By contributing, you confirm that you understand, reviewed, tested, and have the right to submit your contribution under the project license.

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Security

Please do not report security vulnerabilities through public GitHub issues.

See [SECURITY.md](SECURITY.md) for reporting instructions.

## License

Synteles source code is licensed under the Apache License, Version 2.0.

See [LICENSE](LICENSE).

## Trademark and Brand

The Synteles name, logo, visual identity, and related brand assets are not licensed under Apache License 2.0.

See [TRADEMARKS.md](TRADEMARKS.md).

## Contact

- General: hello@synteles.io
- Security: security@synteles.io
- Legal / trademark: legal@synteles.io
