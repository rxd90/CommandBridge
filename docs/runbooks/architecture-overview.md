---
title: Architecture Overview
service: Platform
owner: Platform Engineering
category: Infrastructure
tags: [architecture, overview, aws, infrastructure, reference, scotaccount]
last_reviewed: 2026-02-17
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
    │ (Cache) │ │(Aurora)│ │ (4 tables)│ │  Manager  │
    └─────────┘ └──────┘ └───────────┘ └───────────┘
```

## Authentication Flow

1. User navigates to the CommandBridge portal (CloudFront)
2. Portal presents an in-app login form (no redirect to Cognito Hosted UI)
3. User enters email + password; the portal authenticates via **SRP (Secure Remote Password)** using the Amplify Auth SDK directly against Cognito
4. If MFA is enabled, user enters TOTP code; if first login, user sets a new password
5. Cognito issues **JWT tokens** (access, ID, refresh)
6. Portal stores tokens in session storage and includes the ID token in API requests
7. **API Gateway JWT Authorizer** validates tokens against the Cognito User Pool
8. Lambda handler extracts the user's email from the JWT and resolves the role from DynamoDB

## Key AWS Services

| Service | Purpose | Region |
|---|---|---|
| **Cognito** | User authentication | eu-west-2 |
| **API Gateway** | HTTP API with JWT authorization | eu-west-2 |
| **Lambda** | CommandBridge backend (actions, KB, audit, users, activity) | eu-west-2 |
| **DynamoDB** | Audit log, Knowledge Base, Users, Activity tracking | eu-west-2 |
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

All infrastructure is managed by **Terraform** in the `infra/` directory. Never modify AWS resources directly via the CLI or Console - see the Infrastructure Changes section in the README.
