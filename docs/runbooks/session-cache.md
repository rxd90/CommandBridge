---
title: Session Cache
service: Redis / ElastiCache
owner: Identity Platform
category: Backend
tags: [sessions, redis, caching, login-loops, evictions]
last_reviewed: 2026-01-10
---

# Session Cache Instability: logouts, session loops

## Symptoms

- Users repeatedly logged out or stuck in session renewal loops
- Redis eviction rate spiking above normal baseline
- `CacheMiss` rate increasing in application metrics
- Session token TTL behaving inconsistently across regions

## Checks

1. **Redis cluster health**
    ```bash
    aws elasticache describe-cache-clusters --cache-cluster-id <id> \
      --show-cache-node-info --query 'CacheClusters[].CacheNodes[]'
    ```

2. **Eviction rate and memory usage**
    - Check CloudWatch `Evictions`, `CurrConnections`, `BytesUsedForCache`
    - Compare against baseline - evictions should be near zero under normal load

3. **Sticky session configuration at the edge**
    - Verify ALB session stickiness settings
    - Check if recent deployments changed cookie configuration

4. **Cache key namespace for recent releases**
    - Verify that a new deployment did not change the session key prefix
    - Different key prefix = all existing sessions become invisible = mass logout

## Mitigations

- **Increase cache capacity** or adjust eviction policy (from `allkeys-lru` to `volatile-lru`)
- **Purge stale session keys** for affected cohorts
    - Use the **Purge Cache** action
- **Scale up Redis node type** if memory pressure is the root cause
- **Verify and fix cache key namespace** if a deployment changed the prefix

## Escalation

!!! warning "Escalation threshold"
    Escalate if session churn causes **auth service saturation** across regions, or if cache instability persists for longer than 20 minutes after mitigation.
