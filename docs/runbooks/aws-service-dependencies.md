---
title: AWS Service Dependencies
service: Platform
owner: Platform Engineering
category: Infrastructure
tags: [aws, dependencies, services, topology, reference, blast-radius]
last_reviewed: 2026-02-14
---

# AWS Service Dependencies: blast radius and dependency map

## Core Dependency Chain

```
User Login Flow:
  CloudFront → API Gateway → EKS (auth pods) → Cognito → Redis (sessions) → RDS (user data)

Enrolment Flow:
  CloudFront → API Gateway → ECS (enrolment tasks) → IDV Provider (external) → RDS → DynamoDB

Operational Flow (CommandBridge):
  CloudFront → API Gateway → Lambda → DynamoDB (audit + KB)
```

## Service Dependency Matrix

| If this fails... | These are affected | User impact |
|---|---|---|
| **CloudFront** | All user-facing services | Complete outage — no portal access |
| **API Gateway** | Auth, Enrolment, CommandBridge | No API calls — all services degraded |
| **Cognito** | Login, token refresh | Users cannot authenticate; existing sessions may continue briefly |
| **EKS (auth pods)** | Login, MFA, session management | Authentication failures, login loops |
| **ECS (enrolment)** | New account creation | Enrolment blocked; existing users unaffected |
| **RDS Aurora** | All services using relational data | Degraded reads (if replica available), no writes |
| **Redis** | Sessions, caching | Session invalidation, increased latency, login loops |
| **Route 53** | DNS resolution | Gradual degradation as DNS TTLs expire |
| **WAF** | Edge protection | Traffic unfiltered but still flows (fail-open) |
| **Secrets Manager** | Service-to-service auth | Credential refresh failures; existing credentials may still work |
| **DynamoDB** | CommandBridge audit + KB | Operational portal degraded; core ScotAccount services unaffected |

## Third-Party Dependencies

| Provider | Service | Impact if unavailable |
|---|---|---|
| **IDV Provider** | Document verification (passport, driving licence) | Enrolment blocked at IDV step |
| **SMS Gateway** | MFA OTP delivery | MFA-required users cannot authenticate |
| **CIFAS** | Fraud and AML checks | Enrolment blocked at risk check step |
| **Push Notification Service** | Push-based MFA | Fallback to SMS OTP (if configured) |

## Blast Radius Guide

**Low blast radius** (isolated impact):
- DynamoDB issues → only CommandBridge KB/audit affected
- Lambda issues → only CommandBridge operational actions affected
- Single EKS pod failure → handled by pod autoscaling

**Medium blast radius** (service-level impact):
- Redis failure → session disruption, login loops, cache misses
- Single AZ failure → handled by multi-AZ redundancy (brief disruption)
- IDV provider outage → enrolment blocked, existing users unaffected

**High blast radius** (platform-level impact):
- API Gateway failure → all API-dependent services down
- RDS writer failure → writes blocked across all services until failover
- CloudFront failure → total user-facing outage
- Cognito failure → no new authentication possible

## Monitoring

All services are monitored via CloudWatch alarms. Key dashboards:
- **ScotAccount Overview** — aggregate health across all services
- **Auth Health** — login rates, token validation, session metrics
- **Enrolment Health** — application rates, IDV success, queue depth
- **Infrastructure** — EKS/ECS resource utilisation, RDS connections, Redis memory
