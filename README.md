# CommandBridge

Internal operations portal for Scottish Government digital identity services (ScotAccount). Enables L1 operators to run pre-approved admin operations, search runbooks, and troubleshoot without escalating to L2/L3.

## Architecture

```
frontend/       -> React SPA (TypeScript, Vite, SCSS) -- builds to site/
site/           -> Built frontend assets -- hosted on CloudFront + S3
lambdas/        -> Serverless backend (Python, API Gateway + Lambda)
rbac/           -> Role-based access control config (consumed by Lambda + CI only)
infra/          -> Terraform modules (Cognito, API GW, Lambda, CloudFront, DynamoDB)
scripts/        -> Operational scripts (deploy, seed KB)
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

Three roles enforced server-side via Cognito Groups + API Gateway JWT authorizer:

| Role | Level | Can Do |
|------|-------|--------|
| `L1-operator` | 1 | Run safe ops (purge cache, pull logs, restart pods). Request approval for high-risk. Read KB articles. |
| `L2-engineer` | 2 | Run + approve most operations. Request rotate-secrets. Create + edit KB articles. |
| `L3-admin` | 3 | Unrestricted. Delete KB articles. Manages portal configuration. |

RBAC config lives in `rbac/` and is **never served to the browser**. Permissions are enforced by the Lambda handler on every API call.

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

This builds the React app, packages the Lambda, runs `terraform apply`, uploads the portal to S3, and invalidates CloudFront. Provisions: Cognito User Pool + Groups, API Gateway HTTP API, Lambda function, S3 + CloudFront, DynamoDB tables (audit + KB).

### Infrastructure changes

**All infrastructure is managed by Terraform.** Never modify AWS resources (Cognito, API Gateway, Lambda, DynamoDB, S3, CloudFront, IAM, etc.) via the AWS CLI or Console. Direct changes cause state drift that breaks future deployments.

To change infrastructure, edit the relevant module in `infra/modules/`, run `terraform plan` to review, then `terraform apply` (or `bash scripts/deploy.sh` for a full deploy).

The only permitted direct AWS CLI operations are read-only queries for debugging and user data management (create users, set passwords, assign groups) — see User Management below.

### User Management

Users are created in Cognito and assigned to RBAC groups (`L1-operator`, `L2-engineer`, `L3-admin`).

To add a user via CLI:

```bash
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
  components/     -> Shared components (Layout, SiteHeader, PageHeader, StatusTag, Modal, etc.)
  pages/          -> Route pages (Home, Login, Callback, Incidents, Status, Actions, KB)
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

## Knowledge Base

The KB is a dynamic, DynamoDB-backed article system with full CRUD, versioning, and search.

### Adding articles

Articles are created through the portal UI (`/kb/new`) by L2+ users, or seeded from markdown files:

```bash
# Seed from docs/runbooks/*.md (uses YAML frontmatter for metadata)
python scripts/seed_kb.py
```

### Runbook source files

The `docs/runbooks/` directory contains markdown runbook templates used as seed data. Each file has YAML frontmatter (`title`, `service`, `owner`, `tags`, `last_reviewed`) and structured content (Symptoms, Checks, Mitigations, Escalation).

## Security Model

- Authentication: Cognito User Pool with PKCE OAuth flow
- Authorization: Cognito Groups in JWT -> API Gateway JWT authorizer -> Lambda RBAC check
- RBAC JSON files never leave the server (bundled with Lambda, not served to browser)
- Audit trail: every action logged to DynamoDB (who, what, when, ticket, result)
- KB writes audited: create, update, delete, restore, and denied attempts all logged
- Client-side role filtering is cosmetic only -- server enforces on every request
