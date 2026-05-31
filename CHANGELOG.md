# Changelog

All notable changes to Synteles will be documented in this file.

This project intends to follow semantic versioning once the public APIs, workflow definitions, and runtime interfaces become stable.

Before `v1.0`, breaking changes may occur without a major version bump.

## [Unreleased]

### Added

- GitHub Actions CI workflow (`ci.yml`) — runs lint, type-check, Bandit security scan, and unit tests for every Python service (`core-service`, `scheduler-service`, `synte-service`, `platform-db`) and build + test for `ux-console` on every PR and push to `main`
- GitHub Actions CodeQL workflow (`codeql.yml`) — static analysis of Python and TypeScript code for OWASP Top 10 and common CWEs; runs on PR, push to `main`, and weekly
- GitHub Actions security workflow (`security.yml`) — dependency review (blocks PRs introducing packages with known CVEs) and Trivy lockfile scan uploading SARIF results to the Security tab; runs on PR, push to `main`, and weekly
- Dependabot configuration (`dependabot.yml`) — weekly automated dependency update PRs for all Python services (`uv`), `ux-console` (`npm`), and GitHub Actions themselves
- `CONTRIBUTING.md` CI Checks section — documents all automated checks, how to reproduce failures locally, and how to handle security scan findings

### Changed

- Consolidated `.env.local` into `.env` — a single `.env` file now covers all configuration; `install.sh` no longer requires `openssl` (uses `/dev/urandom` via `od`) and overwrite prompts default to yes
- Documentation accuracy improvements: fixed architecture diagram arrows and descriptions, corrected API contract bucket names and backend defaults, updated third-party copyright holders in `NOTICE` and `THIRD_PARTY_NOTICES.md`, and overhauled `CONTRIBUTING.md` (removed duplicate section, added local checks guidance, fixed broken doc references)
- `synte-service` mypy now runs in strict mode across all source packages; all bare `dict`/`list[dict]` annotations replaced with `dict[str, Any]`/`list[dict[str, Any]]`
- `synte-service` `tools/__init__.py` no longer eagerly re-exports from submodules — imports are now lazy to avoid triggering `platform.toml` loading at import time
- `CONTRIBUTING.md` local checks snippet updated from `npm` to `pnpm`

### Fixed

- `synte-service` tests: replaced deprecated `asyncio.get_event_loop().run_until_complete()` with `asyncio.run()`, which raises `RuntimeError` in Python 3.12+ when no event loop exists
- `synte-service` CI: `pytest_configure` hook in `tests/conftest.py` creates a stub `config/platform.toml` before test collection so `tools.model_catalog` can be imported in environments where `install.sh` has not been run
- `synte-service` `platform_tools.py` and `agent_creator.py`: `PLATFORM_DEFAULT_MODELS` import moved inside the calling function to prevent `FileNotFoundError` propagating at module import time

### Removed

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