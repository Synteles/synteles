# Synteles Platform Infrastructure — Documentation

This directory contains all technical documentation for the Synteles Platform Infrastructure project. Documentation is organized by domain.

---

## Structure

```
docs/
├── ADR/           Architecture Decision Records
├── api/           API reference, contracts, and authentication
├── infrastructure/  AWS infrastructure components
├── ui/            Frontend dashboard (Streamlit/EC2)
├── services/      Lambda services and agent tool designs
├── devops/        CI/CD pipelines and deployment
└── testing/       Test specifications and plans
```

---

## Architecture Decision Records

Long-lived decisions about technology choices and system design.

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](ADR/ADR-001-agentlet-file-exchange.md) | Agentlet File Exchange via S3 Pre-signed URLs | Proposed |
| [ADR-002](ADR/ADR-002-model-picker-tool.md) | Model Picker Tool for Chat Agent | Accepted |
| [ADR-003](ADR/ADR-003-ecs-fargate-agentlet-runtime.md) | AWS ECS Fargate as Default Agentlet Runtime | Accepted |
| [ADR-004](ADR/ADR-004-secrets-management-aws.md) | AWS Secrets Manager for User LLM API Keys | Accepted |
| [ADR-005](ADR/ADR-005-active-executions-sparse-gsi.md) | Sparse GSI for Active Execution Monitoring | Accepted |
| [ADR-006](ADR/ADR-006-ux-ec2-cloudfront-deployment.md) | EC2 + CloudFront for UX Dashboard Deployment | Accepted |

---

## API Documentation

| Document | Description |
|----------|-------------|
| [contracts.md](api/contracts.md) | Complete REST API reference (all endpoints, request/response schemas) |
| [versioning.md](api/versioning.md) | API versioning strategy and deprecation policy |
| [auth-api.md](api/auth-api.md) | Authentication API — OAuth2/PKCE, token lifecycle, integration examples |
| [auth-spec.md](api/auth-spec.md) | Authentication API specification (concise endpoint reference) |

---

## Infrastructure Documentation

| Document | Description |
|----------|-------------|
| [ecs-fargate-deployment.md](infrastructure/ecs-fargate-deployment.md) | ECS Fargate implementation plan, architecture, and pitfalls (P1–P13) |
| [dynamodb.md](infrastructure/dynamodb.md) | DynamoDB table analysis, GSI optimization recommendations |
| [cognito-branding.md](infrastructure/cognito-branding.md) | Cognito managed login branding configuration |
| [secrets-management.md](infrastructure/secrets-management.md) | Secrets management subsystem architecture and API design |
| [gsi-migration.md](infrastructure/gsi-migration.md) | Migration plan: execution-status-gsi → active-executions-gsi |

---

## UI Documentation

| Document | Description |
|----------|-------------|
| [ec2-cloudfront.md](ui/ec2-cloudfront.md) | EC2 + CloudFront UX hosting implementation plan (current architecture) |
| [app-runner-history.md](ui/app-runner-history.md) | Prior App Runner implementation plan (superseded by EC2 + CloudFront) |

---

## Services Documentation

Lambda services and agent tool designs.

| Document | Description |
|----------|-------------|
| [agent-creator-tool-design.md](services/agent-creator-tool-design.md) | Agent creator as tool — design specification |
| [agent-creator-tool-plan.md](services/agent-creator-tool-plan.md) | Agent creator as tool — implementation plan |
| [model-picker-tool-design.md](services/model-picker-tool-design.md) | Model picker tool — design specification |
| [tavily-api-key-injection-design.md](services/tavily-api-key-injection-design.md) | Tavily API key ECS injection — design specification |
| [tavily-api-key-injection-plan.md](services/tavily-api-key-injection-plan.md) | Tavily API key ECS injection — implementation plan |

---

## DevOps / CI-CD

| Document | Description |
|----------|-------------|
| [devops/README.md](devops/README.md) | DevOps documentation index |
| [devops/CICD_COMPLETE_GUIDE.md](devops/CICD_COMPLETE_GUIDE.md) | Complete CI/CD guide (GitHub Actions workflows, AWS/GCP setup, deployment) |

---

## Testing

| Document | Description |
|----------|-------------|
| [testing/integration-tests-spec.md](testing/integration-tests-spec.md) | Integration test specification (all API test scenarios) |
| [testing/integration-tests-plan.md](testing/integration-tests-plan.md) | Integration test implementation plan |

---

## Quick Navigation

**I want to understand the API →** [API Contracts](api/contracts.md)

**I want to understand how executions work →** [ECS Fargate Deployment](infrastructure/ecs-fargate-deployment.md) · [ADR-003](ADR/ADR-003-ecs-fargate-agentlet-runtime.md)

**I want to understand secrets →** [Secrets Management Architecture](infrastructure/secrets-management.md) · [ADR-004](ADR/ADR-004-secrets-management-aws.md)

**I want to understand the UX dashboard →** [EC2 + CloudFront](ui/ec2-cloudfront.md) · [ADR-006](ADR/ADR-006-ux-ec2-cloudfront-deployment.md)

**I want to set up CI/CD →** [Complete CI/CD Guide](devops/CICD_COMPLETE_GUIDE.md)

**I want to understand DynamoDB design →** [DynamoDB Analysis](infrastructure/dynamodb.md) · [ADR-005](ADR/ADR-005-active-executions-sparse-gsi.md)
