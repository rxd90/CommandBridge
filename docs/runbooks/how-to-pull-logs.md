---
title: "How To: Pull Logs"
service: CloudWatch
owner: Platform Ops
category: Infrastructure
tags: [logs, cloudwatch, how-to, filtering, diagnostics]
last_reviewed: 2026-02-14
---

# How To: Pull Logs via CommandBridge

## Overview

The **Pull Logs** action streams and filters CloudWatch log groups for a specific service or time range. This is the safest and most commonly used action — available to all roles (L1+) without approval.

## When to Use

- Investigating alerts or user-reported issues
- Verifying that a recent deployment is healthy
- Checking error rates or specific request traces
- Gathering evidence for an incident timeline

## Step-by-Step

1. **Navigate to Actions** in the CommandBridge sidebar
2. **Select "Pull CloudWatch Logs"** from the action list
3. **Fill in the parameters:**
   - **Log Group**: the CloudWatch log group name (e.g., `/ecs/scotaccount-auth`, `/eks/enrolment-api`)
   - **Filter Pattern**: CloudWatch filter syntax (see below)
   - **Time Range**: start and end timestamps (defaults to last 30 minutes)
4. **Enter your ticket number** (e.g., `INC-2026-0214-001`)
5. **Provide a reason** (brief description of what you're investigating)
6. **Click Execute**

## Common Filter Patterns

| What you're looking for | Filter pattern |
|---|---|
| All errors | `?ERROR ?Error ?error` |
| HTTP 5xx responses | `{ $.statusCode >= 500 }` |
| Specific user email | `"user@example.gov.uk"` |
| Slow requests (>2s) | `{ $.duration > 2000 }` |
| Auth failures | `?invalid_token ?unauthorized ?403` |
| Specific request ID | `"req-abc123"` |

## Reading Results

The response includes matching log events with:
- **Timestamp**: when the event occurred
- **Message**: the log line content
- **Log Stream**: which container/instance produced the log

## Tips

- Start with a **short time range** (15-30 min) to avoid pulling excessive data
- Use **specific filter patterns** rather than broad searches
- If you get no results, verify the **log group name** is correct — use the CloudWatch console to browse available groups
- Combine with the **CloudWatch Insights** queries from the relevant troubleshooting runbook for deeper analysis

## Escalation

!!! info "When to escalate"
    If logs reveal errors you cannot diagnose, escalate to L2 Engineering with the log output and your ticket number. Include the time range and filter pattern you used.
