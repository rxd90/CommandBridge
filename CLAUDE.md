# CommandBridge — Claude Code Instructions

## Infrastructure Management

**All AWS infrastructure changes MUST go through Terraform.** Never use the AWS CLI, Console, or SDK to create, modify, or delete infrastructure resources directly.

This includes but is not limited to:
- Cognito (user pools, clients, domains, groups)
- API Gateway (APIs, routes, integrations, authorizers)
- Lambda (functions, layers, permissions)
- DynamoDB (tables, indexes, capacity)
- S3 (buckets, policies, CORS)
- CloudFront (distributions, cache behaviors, invalidations)
- IAM (roles, policies)
- WAF, Route 53, Secrets Manager, SSM, ECS

### How to make infrastructure changes

1. Edit the relevant Terraform module in `infra/modules/`
2. Run `terraform plan` to verify changes
3. Run `terraform apply` (or use `scripts/deploy.sh` for full deployment)
4. Never run `aws` CLI commands that mutate infrastructure state

### Exceptions

The only permitted direct AWS CLI operations are **read-only queries** for debugging:
- `aws cognito-idp describe-*` (inspect state)
- `aws dynamodb get-item` / `scan` / `query` (read data)
- `aws logs filter-log-events` (read logs)
- `aws cloudfront list-distributions` (inspect state)

And **user data operations** that Terraform does not manage:
- `aws cognito-idp admin-create-user` (create users)
- `aws cognito-idp admin-set-user-password` (set passwords)
- `aws cognito-idp admin-add-user-to-group` (assign roles)

## Testing

Run the full test suite before committing:
```bash
# Python
pytest tests/unit/ -v
pytest tests/validate/ -v

# Frontend
cd frontend && npm test

# Infrastructure
bash tests/validate/test_infra.sh
```

## Deployment

Always use the deployment script for full deploys:
```bash
bash scripts/deploy.sh
```
