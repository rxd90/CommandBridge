---
title: CommandBridge User Guide
service: CommandBridge
owner: Platform Ops
category: Frontend
tags: [commandbridge, guide, rbac, actions, portal, reference, onboarding]
last_reviewed: 2026-02-17
---

# CommandBridge User Guide

## What is CommandBridge?

CommandBridge is the internal operations portal for Scottish Government digital identity services (ScotAccount). It allows operators to run pre-approved admin operations, search runbooks, and troubleshoot issues - all without requiring direct AWS Console access.

## Roles and Permissions

CommandBridge uses three RBAC roles, managed in the DynamoDB users table:

| Role | What you can do |
|---|---|
| **L1 Operator** | Run safe ops (pull logs, purge cache, restart pods, scale service, drain traffic, flush token cache, export audit log). Request approval for high-risk actions. Read all KB articles. |
| **L2 Engineer** | Everything L1 can do, plus: run and approve most high-risk actions, create and edit KB articles. Must request approval for rotate-secrets only. |
| **L3 Admin** | Unrestricted. Can run all actions, delete KB articles, manage users, and view activity/audit logs. |

## Portal Sections

### Actions

The **Actions** page lists all 15 operational actions available in CommandBridge. Each action shows:
- **Name and description** - what it does
- **Risk level** - low, medium, or high
- **Your permission** - whether you can run it directly, need approval, or are locked out

To execute an action:
1. Click the action card
2. Fill in the required parameters
3. Enter a valid ticket number (e.g., `INC-2026-0214-001` or `CHG-1234`)
4. Provide a reason
5. Click Execute (or Submit Request for approval-required actions)

### Knowledge Base

The **Knowledge Base** contains runbooks, how-to guides, architecture docs, and operational procedures. Use the search bar to find articles by title, service, owner, or tags.

- **All roles** can read articles
- **L2+** can create and edit articles
- **L3 only** can delete articles

### Status

The **Status** page shows the health of ScotAccount services and AWS infrastructure.

## Authentication Flow

CommandBridge authenticates directly against AWS Cognito using **SRP (Secure Remote Password)** via the AWS Amplify Auth SDK. There is no redirect to an external hosted UI - the login form is built into the portal.

### Login sequence

```
1. User visits any page        → AuthGuard checks session
2. No session found            → Redirect to /login
3. User enters email + password→ Amplify signIn() performs SRP auth with Cognito
4. Cognito responds            → DONE, MFA challenge, or new-password challenge
   4a. MFA required            → User enters TOTP code → confirmSignIn()
   4b. New password required   → User sets new password → confirmSignIn()
5. Auth complete               → fetchAuthSession() retrieves tokens
6. Tokens stored               → sessionStorage['cb_session']
7. AuthContext updated          → refreshUser() reads new session
8. Navigate to /               → AuthGuard sees user, renders page
```

### Session storage

| Key | Purpose | Lifetime |
|---|---|---|
| `cb_session` | Access token, ID token, expiry timestamp | Until token expires or tab closes |

### Token details

- **ID token** - JWT containing user email and name (roles are resolved from DynamoDB, not the JWT)
- **Access token** - Sent as `Authorization: Bearer` header on all API requests
- Amplify handles token refresh automatically via the Cognito refresh token
- Tokens expire based on Cognito User Pool settings (default 1 hour)

### MFA and first-login flows

- **TOTP MFA** - If MFA is enabled for the user, a 6-digit authenticator code is required after entering credentials
- **Temporary password** - First-time users with admin-assigned passwords must set a new password on first login. Password requirements: 12+ characters, uppercase, lowercase, number, and symbol

### Troubleshooting login issues

- **"Incorrect email or password"** - Verify credentials. After multiple failed attempts, Cognito may temporarily lock the account.
- **MFA code rejected** - Ensure the authenticator app clock is synchronised. TOTP codes are time-based and expire after 30 seconds.
- **Session expires quickly** - Token lifetime is set in the Cognito User Pool. Check the app client token expiration settings.
- **Blank screen after login** - Clear sessionStorage (`cb_session` key) and retry.

## Ticket Number Format

All actions require a ticket number. Accepted formats:
- `INC-001` or `INC-2026-0214-001` (incidents)
- `CHG-1234` or `CHG-release-v2` (changes)

## Audit Trail

Every action you execute is logged to the audit trail with: who, what, when, ticket number, and result. This is non-deletable and used for compliance and post-incident review.

## Getting Help

- Search the **Knowledge Base** for troubleshooting guides
- Ask in **#inc-bridge** (Slack) during active incidents
- Escalate to L2 Engineering if you need approval for a high-risk action
- Contact Platform Ops for portal access or role changes
