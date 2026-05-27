# Security Policy

Security is a top priority for Synteles because the project is designed for AI workers, workflow execution, integrations, and deployment across enterprise-controlled environments.

Synteles is currently in early development. Security support is provided on a best-effort basis until the project reaches a stable release.

## Supported Versions

| Version | Supported |
|---|---|
| `main` | Best effort |
| `v0.x` releases | Best effort |

Breaking changes may occur before `v1.0`.

## Reporting a Vulnerability

Please do not report security vulnerabilities through public GitHub issues.

Report suspected vulnerabilities by email:

```text
security@synteles.io
```

Please include as much detail as possible:

- Description of the vulnerability
- Affected component or version
- Steps to reproduce
- Potential impact
- Any proof-of-concept or logs, if safe to share
- Suggested mitigation, if known
- Your preferred contact details for follow-up

## Response Expectations

We will make a best-effort attempt to:

- Acknowledge the report within 5 business days
- Investigate and validate the issue
- Prioritize a fix or mitigation based on severity
- Coordinate disclosure where appropriate
- Credit the reporter if desired and appropriate

Because Synteles is currently maintained by a small team, response times may vary.

## Responsible Disclosure

Please give the maintainers reasonable time to investigate and address the issue before publicly disclosing details.

Please do not:

- Access, modify, delete, or exfiltrate data that does not belong to you
- Perform testing against systems you do not own or have permission to test
- Disrupt project infrastructure or third-party services
- Use social engineering, phishing, or physical attacks
- Publicly disclose exploit details before a fix or mitigation is available

## Security Scope

Examples of issues that are in scope:

- Authentication or authorization bypass
- Cross-tenant data exposure
- Secrets, token, or credential exposure
- Remote code execution
- Insecure default configuration with meaningful impact
- Unsafe connector permissions
- Unsafe workflow execution paths
- Prompt or tool execution paths that could lead to unauthorized system access
- Injection vulnerabilities
- Supply-chain or dependency risks
- Vulnerabilities in AI worker execution, approval handling, or integration boundaries

## Out of Scope

The following are generally out of scope unless they demonstrate a concrete security impact:

- Reports from automated scanners without exploitability details
- Denial-of-service issues in local-only development environments
- Issues requiring physical access to a developer machine
- Social engineering
- Missing security headers in local development deployments
- Vulnerabilities in third-party services not controlled by the Synteles project
- Best-practice suggestions without a specific vulnerability

## Handling Sensitive Data

When reporting an issue, please avoid sending real secrets, personal data, customer data, or confidential information.

If you accidentally discover sensitive data, stop testing and report the issue immediately.

## Security Best Practices for Users

When running Synteles:

- Do not commit real secrets to the repository
- Use `.env.example` as a template, not as a place for real credentials
- Rotate credentials if they are accidentally exposed
- Use least-privilege credentials for integrations
- Restrict access to production deployments
- Review workflow definitions before production use
- Review connector permissions carefully
- Use separate credentials for development and production
- Protect model provider API keys and integration tokens
- Monitor workflow executions, approvals, and errors

## Production Use

Synteles is currently pre-v1.0.

Before using Synteles in production, teams should perform their own security review, deployment hardening, access-control configuration, dependency review, and compliance assessment.
