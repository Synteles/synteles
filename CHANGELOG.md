# Changelog

All notable changes to Synteles will be documented in this file.

This project intends to follow semantic versioning once the public APIs, workflow definitions, and runtime interfaces become stable.

Before `v1.0`, breaking changes may occur without a major version bump.

## [Unreleased]

### Added

- None

### Changed

- Consolidated `.env.local` into `.env` — a single `.env` file now covers all configuration; `install.sh` no longer requires `openssl` (uses `/dev/urandom` via `od`) and overwrite prompts default to yes
- Documentation accuracy improvements: fixed architecture diagram arrows and descriptions, corrected API contract bucket names and backend defaults, updated third-party copyright holders in `NOTICE` and `THIRD_PARTY_NOTICES.md`, and overhauled `CONTRIBUTING.md` (removed duplicate section, added local checks guidance, fixed broken doc references)

### Fixed

- None

### Removed

- None

### Security

- None

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

- Early alpha release
- APIs may change
- Runtime interfaces may change
- Production deployment requires manual review and hardening
- Security support is best-effort before stable release