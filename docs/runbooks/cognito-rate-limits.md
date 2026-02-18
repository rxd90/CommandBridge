---
title: Cognito Rate Limits
service: Cognito User Pool
owner: Identity Platform
category: Backend
tags: [cognito, rate-limit, throttling, auth, scotaccount]
last_reviewed: 2026-02-17
---

# Cognito Rate Limits: handling throttling during traffic spikes

> **Note:** Replace `$USER_POOL_ID` in commands below with the value from `terraform output cognito_user_pool_id`.

## Symptoms

- `TooManyRequestsException` errors in Lambda or application logs
- Users experiencing intermittent login failures during peak hours
- CloudWatch metric `ThrottleCount` elevated on Cognito user pool

## Background

AWS Cognito enforces rate limits per user pool. Key defaults for eu-west-2:
- **UserAuthentication**: 120 requests/second
- **UserCreation**: 50 requests/second
- **AdminInitiateAuth**: 120 requests/second
- **TokenRefresh**: 120 requests/second

ScotAccount enrolment campaigns (e.g. Disclosure Scotland, Social Security Scotland onboarding) can spike above these limits.

## Checks

1. **Check current throttle rate**
    ```bash
    aws cloudwatch get-metric-statistics \
      --namespace AWS/Cognito \
      --metric-name ThrottleCount \
      --dimensions Name=UserPool,Value=$USER_POOL_ID \
      --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S) \
      --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
      --period 300 \
      --statistics Sum
    ```

2. **Identify the throttled operation** from Lambda error logs
    ```bash
    aws logs filter-log-events \
      --log-group-name /aws/lambda/commandbridge-dev-actions \
      --filter-pattern "TooManyRequestsException" \
      --start-time $(date -d '1 hour ago' +%s000)
    ```

## Mitigations

- **Short-term**: Implement client-side exponential backoff (already in place for ScotAccount SDKs)
- **Medium-term**: Request a Cognito service quota increase via AWS Support
- **If during enrolment spike**: Use the **Pause Enrolments** action to reduce load, then **Scale Service** to increase backend capacity
- **Cache tokens aggressively**: Ensure OIDC token cache TTLs are not too short (see **Flush OIDC Token Cache** runbook)

## Escalation

!!! warning "Escalation threshold"
    Escalate to Platform Ops if throttling persists for more than 15 minutes after applying mitigations, or if it affects more than 5% of authentication attempts.
