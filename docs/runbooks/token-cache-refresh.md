---
title: Token Cache Refresh
service: OIDC / JWKS Cache
owner: Identity Platform
category: Backend
tags: [oidc, jwks, token, cache, signing-key, scotaccount]
last_reviewed: 2026-02-17
---

# Token Cache Refresh: flush stale JWKS keys after rotation

> **Note:** Replace `$USER_POOL_ID` in commands below with the value from `terraform output cognito_user_pool_id`.

## Symptoms

- `invalid_signature` errors in token validation logs after a key rotation
- Users unable to authenticate despite valid credentials
- JWKS endpoint returns new key IDs but services still validate against old keys
- Spike in 401 responses from API Gateway authoriser

## Checks

1. **Compare cached vs live JWKS keys**
    ```bash
    # Live JWKS from Cognito
    curl -s https://cognito-idp.eu-west-2.amazonaws.com/$USER_POOL_ID/.well-known/jwks.json | jq '.keys[].kid'
    ```
    Compare the `kid` values against what the authoriser Lambda is logging.

2. **Check ElastiCache hit/miss ratio**
    - CloudWatch metric: `ElastiCache > CacheMisses` - a sudden spike in misses after rotation is expected
    - If hits remain high with old keys, the cache has not been flushed

3. **Check authoriser Lambda logs**
    ```bash
    aws logs filter-log-events \
      --log-group-name /aws/lambda/commandbridge-dev-actions \
      --filter-pattern "invalid_signature" \
      --start-time $(date -d '1 hour ago' +%s000)
    ```

## Mitigations

- **Flush the OIDC token cache** using the **Flush OIDC Token Cache** action in CommandBridge
    - This clears the ElastiCache replication group used for JWKS caching
    - New requests will fetch fresh keys from the Cognito JWKS endpoint
- If the issue persists, **restart the authoriser Lambda** to clear any in-memory key cache
- Verify the new keys are being picked up by checking a successful auth flow in CloudWatch

## Escalation

!!! warning "Escalation threshold"
    Escalate to Identity Platform on-call if token validation failures exceed 10% of requests for more than 10 minutes after cache flush.
