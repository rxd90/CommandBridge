# CommandBridge Knowledge Base — Seed Data

This directory contains the markdown source files used to seed the dynamic Knowledge Base.

The KB is now a DynamoDB-backed system with full CRUD, versioning, and search — managed through the portal UI and the Lambda API. These markdown files serve as the initial seed data.

## Troubleshooting Runbooks

| Runbook | Service | Owner | Category |
|---|---|---|---|
| [Login Failures](runbooks/login-failures.md) | ScotAccount Auth (OIDC) | Identity Platform | Backend |
| [MFA Issues](runbooks/mfa-issues.md) | MFA / SMS / Push | Trust & Safety | Backend |
| [IDV Failures](runbooks/idv-failures.md) | Document Verification | Enrolment | Backend |
| [Fraud & Risk Checks](runbooks/fraud-risk-checks.md) | CIFAS / AML | Risk Ops | Backend |
| [API Gateway 5xx](runbooks/api-gateway-5xx.md) | API Gateway | Platform Ops | Infrastructure |
| [EKS Instability](runbooks/eks-instability.md) | Kubernetes / EKS | Platform Engineering | Infrastructure |
| [RDS Connection Storms](runbooks/rds-connection-storms.md) | RDS / Aurora | Data Services | Infrastructure |
| [Incident Comms](runbooks/incident-comms.md) | Communications | Comms Lead | Infrastructure |
| [Enrolment Spikes](runbooks/enrolment-spikes.md) | Enrolment API | Enrolment | Backend |
| [Session Cache](runbooks/session-cache.md) | Redis / ElastiCache | Identity Platform | Backend |
| [Common CloudWatch Errors](runbooks/common-cloudwatch-errors.md) | CloudWatch | Platform Ops | Infrastructure |

## How-To Guides

| Guide | Service | Owner | Category |
|---|---|---|---|
| [How To: Pull Logs](runbooks/how-to-pull-logs.md) | CloudWatch | Platform Ops | Infrastructure |
| [How To: Purge Cache](runbooks/how-to-purge-cache.md) | Redis / CloudFront | Platform Ops | Infrastructure |
| [How To: Scale Service](runbooks/how-to-scale-service.md) | ECS / EKS Autoscaling | Platform Ops | Infrastructure |
| [WAF IP Blocking Guide](runbooks/waf-ip-blocking-guide.md) | WAF | Security | Security |
| [Secrets Rotation Guide](runbooks/secrets-rotation-guide.md) | Secrets Manager | Security | Security |
| [Regional Failover Procedure](runbooks/regional-failover-procedure.md) | Route 53 / RDS | Platform Engineering | Infrastructure |

## Architecture & Reference

| Article | Service | Owner | Category |
|---|---|---|---|
| [Architecture Overview](runbooks/architecture-overview.md) | Platform | Platform Engineering | Infrastructure |
| [CommandBridge User Guide](runbooks/commandbridge-user-guide.md) | CommandBridge | Platform Ops | Frontend |
| [AWS Service Dependencies](runbooks/aws-service-dependencies.md) | Platform | Platform Engineering | Infrastructure |

## Escalation & Process

| Article | Service | Owner | Category |
|---|---|---|---|
| [Escalation Matrix](runbooks/escalation-matrix.md) | Operations | Ops Management | Infrastructure |
| [Change Management Process](runbooks/change-management-process.md) | Operations | Ops Management | Infrastructure |

## Seeding

```bash
python scripts/seed_kb.py
```

This parses YAML frontmatter + markdown content from each file and inserts them as version 1 articles into the `commandbridge-dev-kb` DynamoDB table.
