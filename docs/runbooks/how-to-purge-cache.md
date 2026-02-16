---
title: "How To: Purge Cache"
service: Redis / CloudFront
owner: Platform Ops
category: Infrastructure
tags: [cache, redis, cloudfront, how-to, purge, sessions, cdn]
last_reviewed: 2026-02-14
---

# How To: Purge Cache via CommandBridge

## Overview

The **Purge Cache** action flushes the ElastiCache Redis cluster and invalidates CloudFront CDN distributions. This is a medium-risk action — L1 operators can execute it directly, but L2+ can also approve requests.

## When to Use

- Users experiencing stale content or outdated pages
- Session loops caused by corrupted session tokens in Redis
- Post-deployment cache refresh when new static assets are not loading
- JWKS or OIDC discovery cache needing a forced refresh

## Impact Assessment (Before You Purge)

!!! warning "Understand the impact"
    Cache purging has side effects. Review this checklist before executing.

| Impact | What happens |
|---|---|
| **Session invalidation** | Active user sessions in Redis are destroyed — users must re-authenticate |
| **CDN warming** | CloudFront edge caches are cleared — first requests will be slower until cache warms |
| **Increased backend load** | Temporarily higher request rate to origin servers while caches rebuild |
| **JWKS cache reset** | Auth services will re-fetch signing keys — brief window of increased latency |

## Step-by-Step

1. **Navigate to Actions** and select **Purge Cache**
2. **Select the target:**
   - **Redis only**: flushes ElastiCache cluster (sessions, application cache)
   - **CloudFront only**: invalidates CDN edge caches (static assets, HTML)
   - **Both**: full cache purge (use when unsure)
3. **Enter your ticket number and reason**
4. **Click Execute**
5. **Monitor recovery:**
   - Check CloudWatch `CacheHitRate` metric — should recover within 5-10 minutes
   - Verify login flow works end-to-end after session cache clear

## When NOT to Purge

- If the issue is isolated to a single user — investigate their session specifically
- During peak traffic — prefer off-peak or coordinate with L2
- If the root cause is a code bug — purging cache will only temporarily mask it

## Escalation

!!! info "When to escalate"
    Escalate to L2 Engineering if cache instability recurs within 30 minutes of purge, or if purge does not resolve the user-facing symptoms.
