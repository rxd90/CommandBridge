# Production Readiness

Outstanding items to address before production deployment.

## Networking & Isolation

- **Lambda not running in a VPC** — The actions Lambda executes in the default AWS Lambda environment with public internet access. It should be placed in an isolated VPC with private subnets and VPC endpoints for all AWS service dependencies.
- **No AWS WAF on API Gateway** — The HTTP API has no WAF WebACL attached. A WAF with rate limiting, IP reputation, and managed rule groups should be configured in front of the API.
- **No IP whitelisting on portal access** — CloudFront and API Gateway accept requests from any IP. Access should be restricted to an allow-list of corporate/VPN IPs via WAF IP sets or CloudFront geo/IP restrictions.

## Identity & Access

- **MFA optional for privileged accounts** — Cognito MFA is not enforced for L2-engineer and L3-admin roles. MFA should be required for any account with elevated privileges.
- **No approval workflow for admin operations** — User creation, role changes, enable/disable are single-admin actions with no second-party review.

## TLS & Certificates

- **CloudFront using default TLS certificate** — The distribution uses the `*.cloudfront.net` default certificate rather than a custom domain certificate via ACM. A custom TLS certificate should be provisioned for the production domain.

## Known VPC Isolation Gaps

Once the Lambda is moved into an isolated VPC (no NAT gateway, no internet gateway):

- **Route 53 API calls will fail** — `failover-region` executor uses the Route 53 global API, which has no regional VPC endpoint in eu-west-2.
- **CloudFront API calls will fail** — `purge-cache` executor's CDN invalidation uses the CloudFront global API, same limitation.
- **Remediation** — Add a NAT gateway in a single AZ (~$32/mo) to restore access to these two global services, or defer until AWS offers regional VPC endpoints for them.
