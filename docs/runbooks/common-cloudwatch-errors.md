---
title: Common CloudWatch Error Patterns
service: CloudWatch
owner: Platform Ops
category: Infrastructure
tags: [errors, cloudwatch, logs, patterns, troubleshooting, diagnostics]
last_reviewed: 2026-02-14
---

# Common CloudWatch Error Patterns: what they mean and how to respond

## Overview

This reference lists the most common error patterns found in ScotAccount CloudWatch logs, their likely causes, and suggested first-response actions.

## Authentication Errors

| Pattern | Meaning | First Response |
|---|---|---|
| `invalid_token` | JWT failed validation (expired, wrong audience, bad signature) | Check clock sync (NTP), verify JWKS cache, check recent key rotation |
| `token_expired` | Access token past its TTL | Normal if occasional; investigate if >5% of requests |
| `jwks_uri_error` | Cannot fetch signing keys from OIDC provider | Check OIDC discovery endpoint health, purge JWKS cache |
| `session_not_found` | Session token not in Redis | Check Redis eviction rate, check for key namespace change |
| `redirect_loop_detected` | Auth redirects exceeding browser limit | Check callback URL config, cookie settings, session cache |

## API Errors

| Pattern | Meaning | First Response |
|---|---|---|
| `502 Bad Gateway` | Upstream service unreachable | Check EKS/ECS task health, verify target group registrations |
| `503 Service Unavailable` | No healthy targets or service at capacity | Check autoscaling, scale service if needed |
| `504 Gateway Timeout` | Upstream response took >30s | Check RDS connection count, slow query log, Lambda timeout |
| `429 Too Many Requests` | API Gateway throttling | Check rate limit config, identify high-volume callers |
| `CORS_ERROR` | Preflight request blocked | Check API Gateway CORS configuration |

## Database Errors

| Pattern | Meaning | First Response |
|---|---|---|
| `too many connections` | RDS connection pool exhausted | Check connection count, restart connection-leaking pods |
| `ProvisionedThroughputExceededException` | DynamoDB capacity exceeded | Check read/write capacity, enable auto-scaling |
| `ConditionalCheckFailedException` | DynamoDB write conflict | Usually benign (optimistic locking), investigate if persistent |
| `connect ETIMEDOUT` | Cannot reach database | Check security groups, VPC routing, RDS instance status |

## Enrolment Errors

| Pattern | Meaning | First Response |
|---|---|---|
| `idv_vendor_timeout` | IDV provider not responding within SLA | Check IDV provider status page, escalate if >15 min |
| `cifas_check_failed` | Fraud check returned error (not fraud result) | Check CIFAS connectivity, verify API credentials |
| `enrolment_queue_full` | SQS queue depth exceeding threshold | Scale enrolment workers, consider pausing enrolments |
| `duplicate_application` | User attempting re-enrolment | Normal flow - application idempotency check working |

## Infrastructure Errors

| Pattern | Meaning | First Response |
|---|---|---|
| `OOMKilled` | Pod exceeded memory limit | Check for memory leaks, increase pod memory limit |
| `CrashLoopBackOff` | Pod failing to start repeatedly | Check pod logs, recent deployment, config changes |
| `FailedScheduling` | No nodes with available capacity | Scale node group, check resource quotas |
| `UnhealthyTargetCount > 0` | ALB health check failing | Check target pod health, recent deployment |

## Useful CloudWatch Insights Queries

### Error rate by service (last hour)
```
fields @timestamp, @message
| filter @message like /(?i)error|exception|fail/
| stats count() as errors by bin(5m)
| sort @timestamp desc
```

### Top error patterns
```
fields @timestamp, @message
| filter @message like /(?i)error/
| parse @message /(?<error_type>[A-Z][a-z]+Error|[A-Z_]+Exception)/
| stats count() as occurrences by error_type
| sort occurrences desc
| limit 20
```

### Slow requests (>2 seconds)
```
fields @timestamp, @duration, @requestId
| filter @duration > 2000
| sort @duration desc
| limit 50
```

## Escalation

!!! info "When to escalate"
    Escalate if you see error patterns you cannot match to this list, or if known patterns persist after applying the suggested first response.
