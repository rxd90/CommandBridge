---
title: Architecture Overview
service: Platform
owner: Platform Engineering
category: Infrastructure
tags: [architecture, overview, aws, infrastructure, reference, scotaccount]
last_reviewed: 2026-02-14
---

# Architecture Overview: ScotAccount Platform

## Service Map

```
                          ┌──────────────┐
                          │  CloudFront  │
                          │   (CDN/WAF)  │
                          └──────┬───────┘
                                 │
                          ┌──────┴───────┐
                          │ API Gateway  │
                          │  (HTTP API)  │
                          └──────┬───────┘
                                 │
                   ┌─────────────┼─────────────┐
                   │             │             │
            ┌──────┴──────┐ ┌───┴────┐ ┌──────┴──────┐
            │  EKS Pods   │ │ Lambda │ │  ECS Tasks  │
            │ (Auth/IDV)  │ │ (Ops)  │ │ (Enrolment) │
            └──────┬──────┘ └───┬────┘ └──────┬──────┘
                   │            │             │
         ┌─────────┼────────────┼─────────────┤
         │         │            │             │
    ┌────┴────┐ ┌──┴───┐ ┌─────┴─────┐ ┌─────┴─────┐
    │  Redis  │ │ RDS  │ │ DynamoDB  │ │  Secrets  │
    │ (Cache) │ │(Aurora)│ │ (Audit/KB)│ │  Manager  │
    └─────────┘ └──────┘ └───────────┘ └───────────┘
```

## Authentication Flow

1. User navigates to the CommandBridge portal (CloudFront)
2. Portal redirects to **Cognito Hosted UI** for login (PKCE OAuth flow)
3. User authenticates with email + password (optionally with MFA)
4. Cognito issues **JWT tokens** (access, ID, refresh) containing `cognito:groups` claim
5. Portal stores tokens in session storage and includes access token in API requests
6. **API Gateway JWT Authorizer** validates tokens against the Cognito User Pool
7. Lambda handler extracts `cognito:groups` from the JWT to enforce RBAC

## Key AWS Services

| Service | Purpose | Region |
|---|---|---|
| **Cognito** | User authentication, RBAC groups | eu-west-2 |
| **API Gateway** | HTTP API with JWT authorization | eu-west-2 |
| **Lambda** | CommandBridge backend (actions, KB, audit) | eu-west-2 |
| **DynamoDB** | Audit log + Knowledge Base storage | eu-west-2 |
| **S3** | Static portal hosting | eu-west-2 |
| **CloudFront** | CDN, HTTPS termination, WAF integration | Global |
| **EKS** | ScotAccount auth and IDV services | eu-west-2 |
| **ECS** | Enrolment API services | eu-west-2 |
| **RDS Aurora** | Primary relational database | eu-west-2 (multi-AZ) |
| **ElastiCache Redis** | Session cache, application cache | eu-west-2 |
| **Route 53** | DNS, health checks, regional failover | Global |
| **WAF** | Web application firewall, IP blocking | Global (CloudFront) |
| **Secrets Manager** | Service-to-service credentials | eu-west-2 |
| **AppConfig** | Feature flags (maintenance mode) | eu-west-2 |

## Failover Topology

- **Primary region**: eu-west-2 (London)
- **DNS failover**: Route 53 health checks monitor primary region; failover to eu-west-1 (Ireland) if primary is unhealthy
- **RDS**: Aurora with cross-region read replicas; failover promotes replica to writer
- **Redis**: ElastiCache with automatic failover within the region (multi-AZ)

## Infrastructure Management

All infrastructure is managed by **Terraform** in the `infra/` directory. Never modify AWS resources directly via the CLI or Console — see the Infrastructure Changes section in the README.
