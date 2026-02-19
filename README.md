# CommandBridge

Internal operations portal for Scottish Government digital identity services (ScotAccount). Enables L1 operators to run pre-approved admin operations, search runbooks, and troubleshoot without escalating to L2/L3.

## Architecture

```
frontend/       -> React SPA (TypeScript, Vite, SCSS) -- builds to site/
site/           -> Built frontend assets -- hosted on CloudFront + S3
lambdas/        -> Serverless backend (Python, API Gateway + Lambda)
rbac/           -> Role-based access control config (consumed by Lambda + CI only)
infra/          -> Terraform modules (Cognito, API GW, Lambda, CloudFront, DynamoDB)
scripts/        -> Operational scripts (deploy, seed KB, seed users)
docs/runbooks/  -> Runbook markdown source files (seed data for the dynamic KB)
.github/        -> CI/CD workflows
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite, SCSS |
| Icons | Lucide React (tree-shakeable) |
| Typography | Inter (body) + JetBrains Mono (data/monospace) |
| Design System | Custom dark theme with CSS custom properties (`--cb-*` tokens) |
| Auth | Cognito User Pool with PKCE OAuth flow |
| API | API Gateway HTTP API + Lambda (Python) |
| Knowledge Base | DynamoDB-backed with full CRUD, versioning, and server-side search |
| Audit | DynamoDB-backed immutable audit log with GSI queries |
| Activity | DynamoDB-backed user interaction tracking with GSI queries |
| Infra | Terraform, S3, CloudFront, DynamoDB |

## Design System

The portal uses a custom futuristic dark theme built entirely in SCSS with CSS custom properties. Key characteristics:

- **Dark command center** -- deep navy/charcoal backgrounds (`#0a0e17`), not pure black
- **Glass morphism** -- frosted panels with `backdrop-filter: blur()`, translucent borders
- **Accent glow** -- cyan (`#38bdf8`) as primary accent with subtle glow effects
- **Iconography** -- Lucide React icons throughout: navigation, cards, buttons, forms, status indicators
- **Smooth motion** -- fade-in on mount, hover lifts, pulse on status dots, slide-up modals
- **GPU-only animations** -- `transform` and `opacity` only, no layout thrashing
- **Accessibility** -- `prefers-reduced-motion` disables all animations

All design tokens live in `frontend/src/styles/app.scss` under `:root`. Component styles live in `frontend/src/styles/_commandbridge.scss`. All class names use the `cb_` prefix.

## RBAC Model

Three roles enforced server-side via DynamoDB (source of truth) with Cognito JWT fallback:

| Role | Level | Can Do |
|------|-------|--------|
| `L1-operator` | 1 | Run safe ops (pull logs, purge cache, restart pods, scale service, drain traffic, flush token cache, export audit log). Request approval for high-risk actions. Read KB articles. |
| `L2-engineer` | 2 | Run + approve most operations. Request rotate-secrets. Create + edit KB articles. View audit log. |
| `L3-admin` | 3 | Unrestricted. Delete KB articles. Manage users (enable/disable/role change). Full activity and audit access. |

### Actions (15 operational actions)

| Action | Risk | L1 | L2 | L3 |
|--------|------|----|----|-----|
| pull-logs | low | run | run | run |
| purge-cache | medium | run | run | run |
| restart-pods | medium | run | run | run |
| scale-service | medium | run | run | run |
| drain-traffic | medium | run | run | run |
| flush-token-cache | medium | run | run | run |
| export-audit-log | low | run | run | run |
| maintenance-mode | high | request | run | run |
| blacklist-ip | high | request | run | run |
| failover-region | high | request | run | run |
| pause-enrolments | high | request | run | run |
| revoke-sessions | high | request | run | run |
| toggle-idv-provider | high | request | run | run |
| disable-user | high | request | run | run |
| rotate-secrets | high | request | request | run |

RBAC config lives in `rbac/actions.json`. Permissions are enforced by the Lambda handler on every API call.

## Portal Pages

| Route | Page | Access | Description |
|-------|------|--------|-------------|
| `/` | Home | All | Dashboard with quick links and system overview |
| `/actions` | Actions | All | Execute or request operational actions with ticket tracking |
| `/kb` | Knowledge Base | All | Search and browse runbooks and operational articles |
| `/kb/:id` | Article | All | View a KB article with version history |
| `/kb/new` | New Article | L2+ | Create a new KB article |
| `/kb/:id/edit` | Edit Article | L2+ | Edit an existing KB article |
| `/status` | Status | All | Service health status dashboard |
| `/activity` | Activity | L3 | User activity tracking and audit trail |
| `/admin` | Admin Panel | L3 | User management (enable/disable/role) and RBAC matrix |

## Local Development

### Prerequisites

- Node.js 20+
- npm

### Run the Portal locally

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173`. The portal runs in local dev mode when `localDev` is enabled in [frontend/src/config.ts](frontend/src/config.ts), bypassing Cognito auth and showing a user picker on the login page.

### Build for production

```bash
cd frontend
npm run build
```

Output goes to `site/`.

### Run tests

```bash
# Python (Lambda + RBAC validation)
pip install -r tests/requirements-test.txt
pytest tests/unit/ -v
pytest tests/validate/ -v

# Frontend (React components)
cd frontend
npm test

# Infrastructure
bash tests/validate/test_infra.sh
```

## Live Environment

| Resource | URL |
|----------|-----|
| Portal | `https://d2ej3zpo2eta45.cloudfront.net` |
| API | `https://p4afq4i3i4.execute-api.eu-west-2.amazonaws.com` |
| Cognito | `commandbridge-dev.auth.eu-west-2.amazoncognito.com` |
| S3 | `s3://commandbridge.site` |
| State | `s3://commandbridge.state` |

## Deployment

### Deploy everything

```bash
bash scripts/deploy.sh
```

This builds the React app, packages the Lambda, runs `terraform apply`, uploads the portal to S3, and invalidates CloudFront. Provisions: Cognito User Pool + Groups, API Gateway HTTP API, Lambda function, S3 + CloudFront, DynamoDB tables (audit + KB + users).

### Infrastructure changes

**All infrastructure is managed by Terraform.** Never modify AWS resources (Cognito, API Gateway, Lambda, DynamoDB, S3, CloudFront, IAM, etc.) via the AWS CLI or Console. Direct changes cause state drift that breaks future deployments.

To change infrastructure, edit the relevant module in `infra/modules/`, run `terraform plan` to review, then `terraform apply` (or `bash scripts/deploy.sh` for a full deploy).

The only permitted direct AWS CLI operations are read-only queries for debugging and user data management (create users, set passwords, assign groups) - see User Management below.

### User Management

Users are managed through the Admin panel (`/admin`) by L3 admins: enable/disable accounts, change roles. Users are also stored in the DynamoDB users table and can be seeded from `rbac/users.json`:

#### Cognito — 7 users, all CONFIRMED, all enabled

| Email | Role Group | Password |
|-------|-----------|----------|
| `alice.mcgregor@gov.scot` | L1-operator | `Command@Bridge2026` |
| `bob.fraser@gov.scot` | L1-operator | `Command@Bridge2026` |
| `carol.stewart@gov.scot` | L2-engineer | `Command@Bridge2026` |
| `ricardo@demo` | L3-admin | `Command@Bridge2026` |
| `stuart.mcwilliams@gov.scot` | L3-admin | `Command@Bridge2026` |
| `laurie.brown@gov.scot` | L2-engineer | `Command@Bridge2026` |
| `james.callaghan@gov.scot` | L1-operator | `Command@Bridge2026` |

#### Seeding and syncing

```bash
# Seed users to DynamoDB (idempotent, skips existing)
python3 scripts/seed_users.py --table commandbridge-dev-users

# Sync users to Cognito (create accounts + assign groups)
aws cognito-idp admin-create-user \
  --user-pool-id <POOL_ID> \
  --username "user@example.com" \
  --user-attributes Name=email,Value="user@example.com" Name=email_verified,Value=true \
  --temporary-password "<TEMP_PASSWORD>" \
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password \
  --user-pool-id <POOL_ID> \
  --username "user@example.com" \
  --password "<PERMANENT_PASSWORD>" \
  --permanent

aws cognito-idp admin-add-user-to-group \
  --user-pool-id <POOL_ID> \
  --username "user@example.com" \
  --group-name "L1-operator"
```

## Frontend Structure

```
frontend/src/
  components/     -> Shared components (Layout, SiteHeader, PageHeader, StatusTag, Modal, AuthGuard, etc.)
  pages/          -> Route pages (Home, Login, Actions, Status, KB, Activity, Admin)
  hooks/          -> Custom hooks (useAuth, useRbac)
  lib/            -> Utilities (auth, api, rbac)
  styles/
    app.scss            -> Design tokens (:root CSS vars), reset, keyframes
    _commandbridge.scss -> All component styles (cb_* classes)
  config.ts       -> Environment configuration
  types.ts        -> Shared TypeScript types
  App.tsx         -> React Router configuration
  main.tsx        -> App entry point
```

## API Routes

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/actions/permissions` | JWT | Get actions filtered by caller's role |
| POST | `/actions/execute` | JWT | Execute an action (with ticket + reason) |
| POST | `/actions/request` | JWT | Submit approval request for restricted action |
| GET | `/actions/audit` | JWT | Query audit log (filter by user/action, pagination) |
| GET | `/kb` | JWT | List KB articles (search, filter, paginate) |
| POST | `/kb` | JWT (L2+) | Create a new KB article |
| GET | `/kb/{id}` | JWT | Get article (latest version) |
| PUT | `/kb/{id}` | JWT (L2+) | Update article (creates new version) |
| DELETE | `/kb/{id}` | JWT (L3) | Delete all versions of an article |
| GET | `/kb/{id}/versions` | JWT | List article version history |
| GET | `/kb/{id}/versions/{ver}` | JWT | Get specific article version |
| POST | `/admin/users` | JWT (L3) | Create a new user |
| GET | `/admin/users` | JWT (L3) | List all users |
| POST | `/admin/users/{email}/disable` | JWT (L3) | Disable a user |
| POST | `/admin/users/{email}/enable` | JWT (L3) | Enable a user |
| POST | `/admin/users/{email}/role` | JWT (L3) | Change a user's role |
| POST | `/activity` | JWT | Ingest frontend activity events |
| GET | `/activity` | JWT | Query activity events (admin: any user; others: self) |

## Knowledge Base

The KB is a dynamic, DynamoDB-backed article system with full CRUD, versioning, and search.

### Adding articles

Articles are created through the portal UI (`/kb/new`) by L2+ users, or seeded from markdown files:

```bash
# Seed from docs/runbooks/*.md (uses YAML frontmatter for metadata)
python3 scripts/seed_kb.py
```

### Runbook source files

The `docs/runbooks/` directory contains markdown runbook templates used as seed data. Each file has YAML frontmatter (`title`, `service`, `owner`, `tags`, `last_reviewed`) and structured content (Symptoms, Checks, Mitigations, Escalation).

## Security Model

- Authentication: Cognito User Pool with PKCE OAuth flow
- Authorization: DynamoDB users table (source of truth) with Cognito JWT fallback
- API Gateway JWT authorizer validates tokens; Lambda enforces RBAC per-action
- CORS restricted to CloudFront domain + localhost
- Audit trail: every action, admin operation, and KB write logged to DynamoDB
- Client-side role filtering is cosmetic only -- server enforces on every request
