# Contributing to Synteles

Thank you for your interest in contributing to Synteles.

Synteles is an open-source platform for AI workers and long-running enterprise workflows. The project is built for business-described, engineering-customized workflow execution across enterprise-controlled environments.

Contributions are welcome across code, documentation, examples, workflow templates, connectors, tests, developer experience, security hardening, and architecture discussions.

## Table of Contents

- [Ways to Contribute](#ways-to-contribute)
- [Before You Start](#before-you-start)
- [Development Setup](#development-setup)
- [Contribution Workflow](#contribution-workflow)
- [Branch Naming](#branch-naming)
- [Commit Messages](#commit-messages)
- [Pull Request Guidelines](#pull-request-guidelines)
- [CI Checks](#ci-checks)
- [Coding Guidelines](#coding-guidelines)
- [Documentation Guidelines](#documentation-guidelines)
- [Testing Guidelines](#testing-guidelines)
- [Security Guidelines](#security-guidelines)
- [Responsible AI-Assisted Coding](#responsible-ai-assisted-coding)
- [Human Responsibility](#human-responsibility)
- [Disclosure](#disclosure)
- [Developer Certificate of Origin](#developer-certificate-of-origin)
- [Code of Conduct](#code-of-conduct)
- [Security Issues](#security-issues)
- [Governance](#governance)
- [License](#license)

## Ways to Contribute

You can contribute by:

- Reporting bugs
- Improving documentation
- Suggesting product or architecture improvements
- Adding examples and workflow templates
- Building connectors and integrations
- Improving tests and reliability
- Improving local development and Docker setup
- Improving security posture and safe defaults
- Reviewing issues and pull requests
- Sharing feedback from real workflow automation use cases

Good first areas for contribution include:

- Documentation fixes
- Quickstart improvements
- Example workflows
- Connector examples
- Test coverage
- Error messages
- Developer experience improvements

## Before You Start

For small changes, such as typo fixes or documentation improvements, you can open a pull request directly.

For larger changes, please open an issue first to discuss the proposal.

Larger changes may include:

- Public API changes
- Workflow definition format changes
- Runtime architecture changes
- Connector framework changes
- Security-sensitive functionality
- Deployment model changes
- Data model or persistence changes
- Breaking changes to user-facing behavior

A good proposal should explain:

- The problem being solved
- The proposed approach
- Alternatives considered
- Expected impact on users and maintainers
- Security, compatibility, or migration considerations

## Development Setup

Clone the repository and run the setup script:

```bash
git clone https://github.com/Synteles/synteles.git
cd synteles
bash install.sh
```

`install.sh` configures your LLM providers, generates `.env` and `config/platform.toml`, and pulls the agentlet image. Then start the stack:

```bash
docker compose up -d
```

See the README for full setup details and a list of local URLs once the stack is running.

If the setup fails, please open an issue with:

- Operating system
- Docker version
- Error logs
- Steps to reproduce
- Any local configuration differences

## Contribution Workflow

1. Fork the repository.
2. Create a feature branch:

   ```bash
   git checkout -b feature/your-change
   ```

3. Make your changes.
4. Add or update tests where relevant.
5. Add or update documentation where relevant.
6. Add a `CHANGELOG.md` entry under `[Unreleased]` for user-visible changes.
7. Run local checks:

   ```bash
   # Python services — run from each affected service directory
   make check   # lint (Ruff), type-check (Mypy), security scan (Bandit)
   make test    # run tests (pytest)

   # Frontend — run from ux-console/
   pnpm lint
   pnpm test
   ```

8. Commit your changes with a sign-off.
9. Open a pull request against `main`.

Example:

```bash
git commit -s -m "Add document processing workflow example"
```

> **Tip:** If your change only affects a single service, you only need to run checks for that service.

## Branch Naming

Use short, descriptive branch names with a consistent prefix.

| Prefix | Use for | Example |
|---|---|---|
| `feature/` | New features or capabilities | `feature/document-processing-example` |
| `fix/` | Bug fixes | `fix/workflow-retry-handling` |
| `docs/` | Documentation changes only | `docs/quickstart-update` |
| `test/` | Adding or improving tests | `test/connector-runtime` |
| `refactor/` | Code restructuring without behavior change | `refactor/scheduler-error-handling` |
| `chore/` | Maintenance — config, tooling, CI, scripts | `chore/update-docker-compose-healthchecks` |
| `bump/` | Dependency or version bumps | `bump/litellm-1.50` |
| `security/` | Security fixes or hardening | `security/sanitize-execution-logs` |
| `perf/` | Performance improvements | `perf/agentlet-startup-time` |

## Commit Messages

Use clear, descriptive commit messages.

Good examples:

```text
Add document processing example workflow
Fix workflow retry handling
Update Docker Compose quickstart
Add connector interface documentation
```

Avoid vague messages such as:

```text
Update stuff
Fix bug
Changes
WIP
```

## Pull Request Guidelines

Please make sure your pull request:

- Has a clear title and description
- Explains the motivation for the change
- Keeps changes focused and reviewable
- Links to related issues where relevant
- Includes tests where appropriate
- Updates documentation if behavior changes
- Does not include secrets, credentials, private URLs, customer data, or local generated files
- Does not introduce unnecessary dependencies
- Does not include unrelated formatting or refactoring
- Uses a signed-off commit under the Developer Certificate of Origin

A good pull request description includes:

```markdown
## Summary

Briefly explain what changed.

## Motivation

Why is this change needed?

## Testing

How was this tested?

## Notes

Anything reviewers should pay attention to.
```

## CI Checks

Every pull request triggers automated checks that must pass before merging.

**Quality checks** run for each affected service:

| Check | Tool | Scope |
|---|---|---|
| Lint + format | Ruff | All Python services |
| Type checking | Mypy (strict) | All Python services |
| Security scan | Bandit | All Python services |
| Unit tests | pytest | All Python services |
| Unit tests | Vitest | `ux-console` |
| Build | Next.js | `ux-console` |

**Security checks** also run on every PR:

- **Dependency review** — blocks the PR if a newly introduced package has a known CVE
- **Trivy filesystem scan** — scans dependency lockfiles for vulnerabilities; findings appear in the Security → Code scanning tab
- **CodeQL** — static analysis of Python and TypeScript code for common vulnerability patterns (OWASP Top 10, injection flaws, unsafe APIs)

If CI fails on your PR, check the failed job for details. Run `make check && make test` locally in the affected service directory, or `pnpm lint && pnpm test && pnpm build` in `ux-console/`, to reproduce failures before pushing a fix.

## Coding Guidelines

General guidelines:

- Keep changes simple and focused
- Prefer readable code over clever code
- Use explicit names for functions, classes, files, and workflow steps
- Handle errors intentionally
- Avoid hidden side effects
- Avoid unnecessary global state
- Keep interfaces stable where possible
- Document public APIs and configuration options
- Keep dependencies minimal and justified

For workflow and AI-worker-related code:

- Make workflow state explicit
- Make tool calls auditable where practical
- Prefer clear execution boundaries
- Treat human approval steps as first-class workflow steps
- Avoid unsafe default permissions
- Avoid implicit access to external systems
- Design connectors with least-privilege access in mind
- Make failure handling and retries understandable

## Documentation Guidelines

Documentation is a core part of Synteles.

When contributing documentation:

- Be clear and practical
- Prefer examples over abstract explanations
- Keep quickstart instructions copy-pasteable
- Mention required environment variables
- Document assumptions and limitations
- Avoid overstating production readiness
- Use consistent terminology:
  - AI workers
  - workflows
  - long-running workflows
  - human approvals
  - connectors
  - workflow traceability
  - enterprise-controlled environments

If you add a feature, please consider whether it needs updates to:

- `README.md`
- `docs/architecture.md`
- `docs/api-contracts.md`
- `SECURITY.md`
- Example workflows

## Testing Guidelines

Contributions should include tests where practical.

Depending on the change, tests may include:

- Unit tests
- Integration tests
- Connector tests
- Workflow execution tests
- API tests
- UI tests
- Documentation verification
- Docker Compose startup checks

For workflow-related changes, test at least:

- Successful execution path
- Failure path
- Retry or recovery behavior, where applicable
- Human approval path, where applicable
- Error reporting and traceability

If a change is not tested, explain why in the pull request.

## Security Guidelines

Security-sensitive contributions require extra care.

Do not commit:

- API keys
- Access tokens
- Passwords
- Private keys
- Customer data
- Personal data
- Internal URLs or infrastructure details
- Proprietary prompts or private configurations

Use `.env.example` for configuration templates.

Security-related changes should consider:

- Authentication
- Authorization
- Tenant isolation
- Secrets handling
- Connector permissions
- External system access
- Prompt/tool execution boundaries
- Logging of sensitive data
- Safe defaults
- Dependency risk

Automated security scanning runs on every PR and on a weekly schedule. See [CI Checks](#ci-checks) for details. If a scan flags a finding in your PR, address it or explain in the PR description why it is a false positive.

Please report security vulnerabilities privately. Do not open public GitHub issues for vulnerabilities.

See [SECURITY.md](SECURITY.md).

## Responsible AI-Assisted Coding

AI-assisted coding tools are allowed when contributing to Synteles.

Examples include code completion tools, chat-based coding assistants, AI-generated tests, AI-assisted documentation, and refactoring suggestions.

However, contributors remain fully responsible for all submitted work.

By submitting a contribution, you confirm that:

- You understand the code, documentation, or assets you are submitting
- You have reviewed and tested the contribution
- You have the right to submit the contribution under the project license
- The contribution does not knowingly include copyrighted or proprietary material copied from third-party sources without permission
- The contribution does not include confidential information, secrets, personal data, or employer-owned code
- The contribution does not introduce known security vulnerabilities
- The contribution does not rely on AI-generated output that you cannot explain, maintain, or license appropriately

AI-assisted contributions should follow the same quality, security, and licensing standards as any other contribution.

## Human Responsibility

AI tools may assist with drafting, coding, refactoring, testing, or documentation, but they do not replace human judgment.

The contributor is responsible for:

- Correctness
- Security
- Maintainability
- Licensing
- Compatibility with project goals
- Testing
- Reviewing generated code for hallucinated APIs, unsafe patterns, or hidden assumptions

Do not submit AI-generated code that you do not understand.

Do not submit code generated from private, proprietary, or confidential inputs unless you have the right to use and disclose those inputs.

Do not include prompts, generated outputs, or references that expose sensitive information.

## Disclosure

For normal small contributions, disclosure of AI assistance is not required.

For larger or security-sensitive contributions, please mention AI assistance in the pull request if it materially shaped the implementation.

Example:

```text
Parts of this implementation were drafted with AI assistance and manually reviewed, tested, and modified before submission.
```

Maintainers may ask follow-up questions about AI-assisted contributions, especially for security-sensitive, licensing-sensitive, or complex architectural changes.

## Developer Certificate of Origin

Synteles uses the Developer Certificate of Origin, or DCO, for contributions.

By contributing to this project, you certify that you have the right to submit your contribution under the Apache License, Version 2.0.

Each commit must include a sign-off line:

```text
Signed-off-by: Your Name <your.email@example.com>
```

You can add this automatically with:

```bash
git commit -s
```

The sign-off means that you agree to the Developer Certificate of Origin below.

```text
Developer Certificate of Origin
Version 1.1
Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.
Developer's Certificate of Origin 1.1
By making a contribution to this project, I certify that:
(a) The contribution was created in whole or in part by me and I have the right
    to submit it under the open source license indicated in the file; or
(b) The contribution is based upon previous work that, to the best of my knowledge,
    is covered under an appropriate open source license and I have the right under
    that license to submit that work with modifications, whether created in whole
    or in part by me, under the same open source license unless I am permitted to
    submit under a different license, as indicated in the file; or
(c) The contribution was provided directly to me by some other person who certified
    (a), (b), or (c) and I have not modified it.
(d) I understand and agree that this project and the contribution are public and
    that a record of the contribution, including all personal information I submit
    with it, including my sign-off, is maintained indefinitely and may be
    redistributed consistent with this project or the open source license involved.
```

## Code of Conduct

All contributors and participants are expected to follow the project Code of Conduct.

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Security Issues

Please do not report security vulnerabilities through public GitHub issues.

See [SECURITY.md](SECURITY.md).

## Governance

Project governance is described in [GOVERNANCE.md](GOVERNANCE.md).

Synteles is currently a founder-led open-source project. As the community grows, governance may evolve.

## License

By contributing to Synteles, you agree that your contributions will be licensed under the Apache License, Version 2.0, unless explicitly stated otherwise.

See [LICENSE](LICENSE).

The Synteles name, logo, and related brand assets are not licensed under the Apache License, Version 2.0.

See [TRADEMARKS.md](TRADEMARKS.md).
