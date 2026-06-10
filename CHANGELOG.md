# Changelog

All notable changes to Synteles will be documented in this file.

This project intends to follow semantic versioning once the public APIs, workflow definitions, and runtime interfaces become stable.

Before `v1.0`, breaking changes may occur without a major version bump.

## [Unreleased]

### Added

- Durable execution backend via [Temporal](https://temporal.io): agentlets can now be configured with `execution_backend: durable`, wrapping each run in a long-lived Temporal workflow that persists history, survives container crashes, and supports human-in-the-loop (HITL) pausing via the `ask_user` tool — see `docs/durable-execution.md`
- `durable-worker` service: new Python service implementing `AgentWorkflow` (ReAct loop with LiteLLM) and three Temporal activities (`call_llm_step`, `call_mcp_tool`, `upload_output`) with configurable retry policies; supports stdio MCP servers
- HITL signal bridge: monitor now polls `is_input_needed` on durable workflows and transitions executions between `running` and `waiting_for_signal`; `POST /api/executions/{id}/signal` and `POST /api/public/executions/{id}/signal` deliver user input to paused workflows
- `execution_backend` column on the `agentlets` table (`standard` | `durable`, default `standard`) — replaces the previous YAML-level field; visible in all agentlet API responses
- Worker container restart logic (`worker_restart.py`): monitor and signal delivery automatically relaunch a dead `durable-worker` container while the Temporal workflow remains live, refreshing presigned URLs via `update_output_url` signal
- Frontend HITL UI: `ExecutionDetailSheet` shows the pending question and a signal input field when an execution is `waiting_for_signal`; `WatchdogProvider` treats `waiting_for_signal` as an active status for polling; `BackendBadge` component displays execution backend on agentlet cards and run tables; standard/durable `ToggleGroup` in the agentlet create and edit drawers
- `GET /api/executions/{id}` now returns `pending_question`, `last_message`, and `execution_type` fields for durable executions
- DB migrations: `0003_durable_executions` (adds `execution_type`, `workflow_id`, `timeout_at`, `waiting_for_signal` status), `0004_agentlet_execution_backend` (adds `execution_backend` column, backfills from YAML), `0005_drop_signal_name` (drops redundant `signal_name` column)

- GitHub Actions CI workflow (`ci.yml`) — runs lint, type-check, Bandit security scan, and unit tests for every Python service (`core-service`, `scheduler-service`, `synte-service`, `platform-db`) and build + test for `ux-console` on every PR and push to `main`
- GitHub Actions CodeQL workflow (`codeql.yml`) — static analysis of Python and TypeScript code for OWASP Top 10 and common CWEs; runs on PR, push to `main`, and weekly
- GitHub Actions security workflow (`security.yml`) — dependency review (blocks PRs introducing packages with known CVEs) and Trivy lockfile scan uploading SARIF results to the Security tab; runs on PR, push to `main`, and weekly
- Dependabot configuration (`dependabot.yml`) — weekly automated dependency update PRs for all Python services (`uv`), `ux-console` (`npm`), and GitHub Actions themselves
- `CONTRIBUTING.md` CI Checks section — documents all automated checks, how to reproduce failures locally, and how to handle security scan findings

### Changed

- `synte-service` internal refactoring and schema alignment: `tools/yaml_validator.py` renamed to `tools/agentlet_validator.py` (`validate_yaml` → `validate_agentlet_yaml`); `agents/agent_creator.py` renamed to `agents/agentlet_creator.py`; `_load_chat_config` simplified by removing the redundant `_LITELLM_ENV_MAP` translation table — `PLATFORM_SECRET_*` JSON keys are already the target env var names and are passed through directly; `agentlet_creator` system prompt synced with `agentlet-schema.json` — added missing built-in tools (`think`, `use_computer`), `retry_on_errors` to retry config documentation, missing observability fields (`otlp_metrics_endpoint`, `sampler`, `sampler_arg`, `trace_attributes`), and corrected the `agentlet.name` pattern constraint
- Public API authentication reworked: API keys now require the `X-API-Key` header (replacing `Authorization: Bearer`), auth enforcement moved to Traefik `forwardAuth` per route group (`/api/public/*` accepts API keys only, `/api/*` accepts Bearer JWTs only), first-login provisioning unblocked by making `/auth/verify` pass through with an empty `X-Org-Id` for unprovisioned users, and the `last_used` timestamp on API keys now correctly persists (missing `db.commit()` in the verify handler); Keycloak provisioner gains separate `TEST_USER` and `FRESH_USER` identities for integration testing; integration tests added for auth enforcement and the full first-login provisioning flow; API Integration UI updated with `X-API-Key` header, correct route paths, and a runtime-configurable API base URL (`API_PUBLIC_BASE_URL`); `docs/testing.md` and `docs/configuration.md` updated accordingly
- Consolidated `.env.local` into `.env` — a single `.env` file now covers all configuration; `install.sh` no longer requires `openssl` (uses `/dev/urandom` via `od`) and overwrite prompts default to yes
- Documentation accuracy improvements: fixed architecture diagram arrows and descriptions, corrected API contract bucket names and backend defaults, updated third-party copyright holders in `NOTICE` and `THIRD_PARTY_NOTICES.md`, and overhauled `CONTRIBUTING.md` (removed duplicate section, added local checks guidance, fixed broken doc references)
- `synte-service` mypy now runs in strict mode across all source packages; all bare `dict`/`list[dict]` annotations replaced with `dict[str, Any]`/`list[dict[str, Any]]`
- `synte-service` `tools/__init__.py` no longer eagerly re-exports from submodules — imports are now lazy to avoid triggering `platform.toml` loading at import time
- `CONTRIBUTING.md` local checks snippet updated from `npm` to `pnpm`

### Fixed

- Execution detail sheet now auto-refreshes logs and output files when an agentlet run completes, eliminating the need for a manual browser refresh
- Reduced `MONITOR_INTERVAL_SECONDS` default from 60 s to 30 s so the scheduler-service detects run completion roughly twice as fast
- Chat input textarea now automatically regains focus after streaming completes, eliminating the need to manually click or press Tab to continue typing
- Chat no longer resets to the new-conversation view after the access token expires; a `SessionRefresher` component proactively renews the token 60 s before expiry and on tab re-focus, preventing the 401 → full-page-reload cycle that was resetting the selected conversation
- `synte-service` tests: replaced deprecated `asyncio.get_event_loop().run_until_complete()` with `asyncio.run()`, which raises `RuntimeError` in Python 3.12+ when no event loop exists
- `synte-service` CI: `pytest_configure` hook in `tests/conftest.py` creates a stub `config/platform.toml` before test collection so `tools.model_catalog` can be imported in environments where `install.sh` has not been run
- `synte-service` `platform_tools.py` and `agent_creator.py`: `PLATFORM_DEFAULT_MODELS` import moved inside the calling function to prevent `FileNotFoundError` propagating at module import time

### Removed

- `activity-worker` service — was a Zigflow DSL relic; all execution paths now use either the standard Docker backend or the new `durable-worker`
- `synte-service/tests/test_model_catalog.py` — tested platform config loading which requires a populated `config/platform.toml`; removed to keep CI environment-independent (error still raised at runtime when config is missing)
- `ux-console/CLAUDE.md` — removed stale AI assistant context file
- Removed all direct AWS Cognito integration traces (`COGNITO_DOMAIN`, `COGNITO_USER_POOL_ID`) from `core-service`, `synte-service`, and `ux-console`; Cognito is now accessed exclusively through Keycloak as an identity broker

### Security

- Bandit `# nosec` suppressions added for `B105` (hardcoded password false positives on env var name strings) and `B110` (try/except/pass in non-sensitive context) in `synte-service`

## [0.1.0-alpha] - 2026-05-27

### Added

- Initial open-source alpha release of Synteles platform
- Local development setup with Docker Compose
- Apache License 2.0 project licensing
- Code of Conduct, Security policy, and Governance documentation
- DCO-based contribution process
- Responsible AI-assisted coding contribution policy

### Changed

- None

### Fixed

- None

### Removed

- None

### Security

- Added initial security reporting policy

### Known Limitations

- `core-service` conversations router generates presigned S3 URLs using the internal MinIO endpoint, so `display_url` / `agent_state_url` are unreachable by external clients; fix is to use `get_s3_public()` in that router (consistent with `files.py`)
- Early alpha release
- APIs may change
- Runtime interfaces may change
- Production deployment requires manual review and hardening
- Security support is best-effort before stable release