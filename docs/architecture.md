# CommandBridge Architecture

## Overview

CommandBridge is an operational command portal that provides tiered support staff with a controlled, audited interface for executing infrastructure actions. It is built as a serverless application on AWS.

## System Architecture

```
                         ┌─────────────┐
                         │   Browser   │
                         │  (React SPA)│
                         └──────┬──────┘
                                │
                         ┌──────▼──────┐
                         │ CloudFront  │
                         │ (CDN + SPA  │
                         │  hosting)   │
                         └──────┬──────┘
                                │
               ┌────────────────┼────────────────┐
               │                │                │
        ┌──────▼──────┐ ┌──────▼──────┐  ┌──────▼──────┐
        │  S3 Bucket  │ │   Cognito   │  │ API Gateway │
        │ (static     │ │ (auth +     │  │ (HTTP API + │
        │  assets)    │ │  hosted UI) │  │  JWT auth)  │
        └─────────────┘ └─────────────┘  └──────┬──────┘
                                                │
                                         ┌──────▼──────┐
                                         │   Lambda    │
                                         │ (Python 3.12│
                                         │  handler)   │
                                         └──────┬──────┘
                                                │
                    ┌──────────┬────────┬────────┼────────┬──────────┐
                    │          │        │        │        │          │
              ┌─────▼───┐ ┌───▼──┐ ┌───▼──┐ ┌───▼──┐ ┌───▼──┐ ┌───▼───┐
              │DynamoDB  │ │  S3  │ │ ECS  │ │ SSM  │ │ WAF  │ │ Other │
              │(4 tables)│ │      │ │      │ │      │ │      │ │  AWS  │
              └──────────┘ └──────┘ └──────┘ └──────┘ └──────┘ └───────┘
```

## Request Flow

### 1. Authentication

1. User navigates to the portal (CloudFront distribution).
2. Unauthenticated users are redirected to the Cognito hosted UI login page.
3. After successful login, Cognito redirects back with an authorization code.
4. The frontend exchanges the code for JWT tokens (access + ID token) and stores them in `sessionStorage`.
5. All subsequent API calls include the access token as a `Bearer` header.

### 2. API Request Processing

1. API Gateway receives the request and validates the JWT against Cognito (issuer + audience check).
2. If the token is invalid or expired, API Gateway returns 401 before the Lambda is invoked.
3. On valid auth, API Gateway forwards the request to the single Lambda function.

### 3. Role Resolution and RBAC

1. The Lambda extracts the user's email from the JWT claims.
2. It looks up the user's role from the DynamoDB users table (sole source of truth for authorization).
3. The resolved role (L1-operator, L2-engineer, or L3-admin) is used for all permission checks.

### 4. Action Execution

1. The handler routes the request by HTTP method and path.
2. For action execution (`POST /actions/execute`), input validation runs first: action ID, ticket reference (must match `INC-*` or `CHG-*`), and reason are all required.
3. RBAC check runs against `rbac/actions.json` to determine if the user's role can execute the action.
4. If the role can only `request` (not `run`), the action is logged as `requested` and enters the approval queue.
5. If the role can `run`, the handler dynamically imports the matching executor module from `lambdas/actions/executors/` and invokes it.
6. The executor makes the relevant AWS API call (e.g., ElastiCache for cache purge, ECS for scaling).
7. The result is logged to the audit table and returned to the caller.

### 5. Approval Workflow

1. L1 users submit high-risk actions via `POST /actions/request` or automatically when RBAC returns `needs_approval`.
2. The request is stored in the audit table with status `requested`, including the full request body.
3. L2+ users can view pending requests via `GET /actions/pending`.
4. An approver submits `POST /actions/approve` with the `request_id`.
5. Self-approval is blocked (the requester cannot approve their own request).
6. On approval, the original request body is replayed through the executor, and the audit record is updated.

## RBAC Model

Three roles with increasing privileges:

| Role | Actions | Admin | KB | Audit |
|------|---------|-------|----|-------|
| **L1-operator** | Request only (needs approval) | No access | Read only | Own history only |
| **L2-engineer** | Run + approve requests | No access | Read + write | All entries, filter by action |
| **L3-admin** | Run + approve requests | Full user management | Read + write + delete | All entries, filter by user |

Action permissions are defined in a static `actions.json` file deployed with the Lambda. Each action specifies which roles can `run`, `request`, or `approve` it.

## Data Model

### DynamoDB Tables

| Table | Partition Key | Sort Key | Purpose |
|-------|--------------|----------|---------|
| `commandbridge-{env}-audit` | `user` (email) | `timestamp` | Action audit trail with GSIs for action-type and status queries |
| `commandbridge-{env}-kb` | `id` (article slug) | `version` (number) | Versioned knowledge base articles |
| `commandbridge-{env}-users` | `email` | — | User profiles, roles, team assignments |
| `commandbridge-{env}-activity` | `user` (email) | `timestamp` | Frontend interaction events with TTL |

### Cognito

- User pool with email-based login and strong password policy (12+ chars, mixed case, numbers, symbols).
- Admin-only user creation (no self-signup).
- MFA currently optional.
- Cognito handles authentication only; roles are managed in the DynamoDB users table.

## Operational Actions

The Lambda supports 16 executor modules:

| Action | AWS Service | Risk | Description |
|--------|-------------|------|-------------|
| pull-logs | CloudWatch Logs | Low | Filter and retrieve application logs |
| export-audit-log | DynamoDB, S3 | Low | Export audit records to S3 |
| purge-cache | ElastiCache, CloudFront | Medium | Flush Redis cache and/or invalidate CDN |
| restart-pods | SSM | Medium | Restart pods via SSM RunCommand |
| scale-service | ECS | Medium | Scale ECS service desired count |
| drain-traffic | ELBv2 | Medium | Deregister targets from load balancer |
| flush-token-cache | ElastiCache | Medium | Flush OIDC/JWKS token cache |
| maintenance-mode | AppConfig | High | Toggle maintenance mode via feature flag |
| pause-enrolments | AppConfig | High | Pause new user enrolments |
| blacklist-ip | WAFv2 | High | Add IP to WAF block list |
| failover-region | Route 53 | High | Trigger regional failover via health check |
| rotate-secrets | Secrets Manager | High | Trigger secret rotation |
| revoke-sessions | Cognito | High | Force global sign-out for a user |
| disable-user | Cognito, DynamoDB | High | Disable a user account |
| toggle-idv-provider | SSM | High | Switch identity verification provider |

## Infrastructure

All infrastructure is managed via Terraform modules in `infra/modules/`:

| Module | Resources |
|--------|-----------|
| `cognito` | User pool, app client, domain |
| `storage` | 4 DynamoDB tables with PITR enabled |
| `lambdas` | Lambda function, IAM role and scoped policies |
| `api` | API Gateway HTTP API, JWT authorizer, routes |
| `hosting` | S3 bucket, CloudFront distribution with OAC, security headers |

Terraform state is stored in S3 (`commandbridge.state`) with DynamoDB locking (`commandbridge.lock`).

## Frontend

React SPA built with Vite and TypeScript. Key characteristics:

- Session tokens stored in `sessionStorage` (cleared on tab close) with expiry validation.
- Client-side role checks are display-only; all authorization is enforced server-side.
- Security headers delivered via CloudFront function (HSTS, CSP, X-Frame-Options, Permissions-Policy).
- No `dangerouslySetInnerHTML` usage; KB markdown rendered safely via `react-markdown`.
