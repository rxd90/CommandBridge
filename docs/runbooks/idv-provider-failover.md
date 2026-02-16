---
title: IDV Provider Failover
service: Document Verification Service
owner: Enrolment
category: Backend
tags: [idv, identity-verification, documents, failover, provider, scotaccount]
last_reviewed: 2026-02-16
---

# IDV Provider Failover: switch identity verification backend

## Symptoms

- Document verification requests timing out or returning 5xx from the primary IDV provider
- Elevated latency (>30s) on identity document checks
- Users reporting "verification unavailable" during enrolment
- IDV provider status page reporting degraded service

## Checks

1. **Check IDV provider health**
    ```bash
    aws logs filter-log-events \
      --log-group-name /aws/lambda/commandbridge-dev-actions \
      --filter-pattern "idv" \
      --start-time $(date -d '30 minutes ago' +%s000)
    ```
    Look for timeout, 5xx, or connection refused patterns.

2. **Check current active provider**
    ```bash
    aws ssm get-parameter \
      --name /scotaccount/idv/active-provider \
      --query 'Parameter.Value' --output text
    ```

3. **Check success rate metrics**
    - CloudWatch dashboard: IDV verification success rate
    - Normal: >95% success. Degraded: <90%. Outage: <50%

## Mitigations

- **Switch to backup IDV provider** using the **Toggle IDV Provider** action in CommandBridge
    - Target should be the standby provider name (e.g. `provider-b`)
    - The switch takes effect immediately via SSM parameter update
- Monitor verification success rate for 10 minutes after switchover
- **Pause enrolments** using the **Pause Enrolments** action if both providers are down

## Escalation

!!! warning "Escalation threshold"
    Escalate to Enrolment team lead if IDV verification success rate drops below 80% for more than 15 minutes, or if both providers are simultaneously degraded.
