# Changelog

All notable changes to Synteles will be documented in this file.

This project intends to follow semantic versioning once the public APIs, workflow definitions, and runtime interfaces become stable.

Before `v1.0`, breaking changes may occur without a major version bump.

## [Unreleased]

## [0.2.0-alpha] - 2026-06-13

### Added

- **Durable execution** via [Temporal](https://temporal.io): set `execution_backend: durable` on an agentlet for workflows that must survive container restarts or pause for human-in-the-loop (HITL) decisions via the `ask_user` tool — see [docs/durable-execution.md](docs/durable-execution.md)
- HITL signal bridge: executions transition to `waiting_for_signal` when `ask_user` is called; users respond via `POST /api/executions/{id}/signal`; the execution detail UI shows the pending question inline
- GitHub Actions CI, CodeQL, and security scanning workflows; Dependabot for automated dependency updates

### Changed

> **Upgrading from 0.1.0-alpha:** re-run `install.sh` or manually apply the breaking changes below before `docker compose up --build`.

- `platform.toml` moved from `config/platform.toml` to the repository root
- API key authentication now requires the `X-API-Key` header (replaces `Authorization: Bearer`)
- `.env.local` merged into `.env` — a single file now covers all configuration
- `install.sh` overhauled: deferred credential collection, merge mode for existing installs, new provider options

### Fixed

- Execution detail sheet auto-refreshes logs and output on run completion (no manual browser refresh needed)
- Chat input regains focus automatically after streaming completes
- Session no longer resets to the new-conversation view on access token expiry

### Removed

- `activity-worker` service — executions now use the standard Docker or new `durable-worker` backends
- Direct AWS Cognito integration — Cognito is now accessed exclusively through Keycloak as an identity broker

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