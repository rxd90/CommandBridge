---
title: Login Failures
service: ScotAccount Auth (OIDC)
owner: Identity Platform
category: Backend
tags: [login, oidc, jwks, token, auth, scotaccount]
last_reviewed: 2026-01-08
---

# Login Failures: invalid_token, JWKS errors, session loops

## Symptoms

- Sudden 401/403 spikes across regions
- Users stuck in login redirect loops
- JWKS cache misses or `jwks_uri` returning 5xx
- Token validation errors in auth service logs
- `invalid_token` or `token_expired` errors in application logs

## Checks

1. **OIDC discovery endpoint availability**
    ```bash
    curl -s https://auth.scotaccount.gov.uk/.well-known/openid-configuration | jq .
    ```

2. **JWKS endpoint health and cache headers**
    ```bash
    curl -sI https://auth.scotaccount.gov.uk/.well-known/jwks.json
    ```
    Verify `Cache-Control` headers and that the response contains current key IDs.

3. **Time sync (NTP) across gateway and auth services**
    ```bash
    # On EKS pods
    kubectl exec -n auth deploy/oidc-provider -- date -u
    ```
    Token validation is sensitive to clock skew > 30s.

4. **Recent key rotation or config drift**
    - Check if OIDC redirect URIs were modified in the last deploy window
    - Verify key rotation did not remove the active signing key

5. **Redis session cache health**
    - Check eviction rates and memory usage in ElastiCache dashboard
    - Session loops often indicate cache is evicting session tokens

## Mitigations

- **Flush JWKS cache** in all regions and reduce TTL temporarily
    - Use the **Purge Cache** action in CommandBridge
- **Rollback auth config** if changes were introduced in the last deploy window
- **Increase Redis capacity** if eviction rate is elevated
- **Restart OIDC provider pods** if they are holding stale JWKS keys in memory
    - Use the **Restart EKS Pods** action targeting the `auth` namespace

## Escalation

!!! warning "Escalation threshold"
    Escalate to IAM/Security on-call if token validation failures exceed **5% of requests** in two or more regions for longer than 15 minutes.
