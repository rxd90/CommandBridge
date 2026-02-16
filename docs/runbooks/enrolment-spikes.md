---
title: Enrolment Spikes
service: Enrolment API
owner: Enrolment
category: Backend
tags: [enrolment, queues, scaling, throttling, backlog]
last_reviewed: 2026-01-09
---

# Enrolment Spikes: queue backlog, throttling, timeouts

## Symptoms

- Slow enrolment completion times (> 30s end-to-end)
- SQS queue depth growing faster than consumers can process
- Throttled worker logs (`429 Too Many Requests` from downstream services)
- Users reporting timeouts during account creation

## Checks

1. **Queue depth and consumer concurrency**
    ```bash
    aws sqs get-queue-attributes --queue-url <url> \
      --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
    ```

2. **Rate limiting in API Gateway**
    - Check throttling metrics for enrolment endpoints
    - Verify rate limit configuration has not drifted

3. **Downstream dependency health**
    - IDV provider: latency and error rates
    - Email/SMS delivery: queue depth and delivery success rate
    - Fraud checks: response times and fail-open status

4. **Worker autoscaling status**
    ```bash
    aws ecs describe-services --cluster <cluster> --services enrolment-worker \
      --query 'services[].{desired:desiredCount,running:runningCount,pending:pendingCount}'
    ```

## Mitigations

- **Scale worker pools** to increase processing capacity
    - Use the **Scale Service** action targeting enrolment workers
- **Reduce retry aggressiveness** temporarily to prevent amplification
- **Pause low-priority enrolments** if needed to protect existing user flows
    - Use the **Pause Enrolments** action (requires L2 approval)
- **Enable maintenance mode** as a last resort to stop new enrolment traffic entirely
    - Use the **Maintenance Mode** action (requires L2 approval)

## Escalation

!!! warning "Escalation threshold"
    Escalate if queue backlog continues growing for **30 minutes after scaling**, or if downstream dependencies are confirmed degraded with no provider ETA.
