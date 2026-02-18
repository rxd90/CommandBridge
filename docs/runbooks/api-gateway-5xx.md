---
title: API Gateway 5xx
service: API Gateway
owner: Platform Ops
category: Infrastructure
tags: [api, 5xx, latency, rate-limit, gateway, throttling]
last_reviewed: 2026-01-04
---

# API Gateway: 5xx spike, throttling, latency waterfall

## Symptoms

- Sudden 5xx error rate at the edge exceeding 1%
- Client retry storms amplifying load
- High p95 latency (> 2s for normally sub-200ms endpoints)
- CloudWatch alarms firing on `5XXError` metric

## Checks

1. **Identify top failing routes**
    ```bash
    # CloudWatch Insights - top 5xx routes in last 30 minutes
    fields @timestamp, httpMethod, path, status
    | filter status >= 500
    | stats count() as errors by path
    | sort errors desc
    | limit 10
    ```

2. **Downstream dependency health**
    - Check if backend services (EKS pods, Lambda functions) are healthy
    - Look for connection refused or timeout errors in backend logs

3. **Client retry storms**
    - Check request rate by client/IP for exponential growth patterns
    - Verify circuit breaker settings in API Gateway

4. **Regional routing and health checks**
    - Verify Route 53 health checks are passing for all active regions
    - Check if traffic is correctly distributed across healthy regions

## Mitigations

- **Apply temporary rate limits** for expensive endpoints
- **Shift traffic to healthier regions** if the issue is localised
    - Use the **Drain Traffic** action to remove the faulty AZ from ALB
- **Scale backend services** if the issue is capacity-related
    - Use the **Scale Service** action
- **Enable maintenance mode** if the issue is affecting all regions
    - Use the **Maintenance Mode** action (requires L2 approval)

## Escalation

!!! warning "Escalation threshold"
    Escalate if error rates exceed SLO (99.9%) in **two or more regions** for longer than 10 minutes.
