---
title: Change Management Process
service: Operations
owner: Ops Management
category: Infrastructure
tags: [change, deployment, approval, process, governance, tickets]
last_reviewed: 2026-02-14
---

# Change Management Process: tickets, approvals, and deployment windows

## Ticket Requirements

All operational actions in CommandBridge require a valid ticket number. This ensures traceability and compliance.

### Ticket Formats

| Type | Format | When to use |
|---|---|---|
| **Incident** | `INC-2026-0214-001` or `INC-001` | Reactive actions during an incident |
| **Change** | `CHG-1234` or `CHG-release-v2` | Planned changes, maintenance, deployments |

### What Goes in the Ticket

- **Summary**: what action you're taking and why
- **Impact assessment**: which services and users are affected
- **Rollback plan**: how to undo the change if something goes wrong
- **Approvals**: L2/L3 sign-off for high-risk actions

## Approval Workflows

| Action Risk | L1 Operator | L2 Engineer | L3 Admin |
|---|---|---|---|
| **Low risk** (pull-logs) | Execute directly | Execute directly | Execute directly |
| **Medium risk** (purge-cache, restart-pods, scale-service, drain-traffic) | Execute directly | Execute directly | Execute directly |
| **High risk** (maintenance-mode, blacklist-ip, failover-region, pause-enrolments) | Submit request → L2/L3 approves | Execute directly | Execute directly |
| **Critical** (rotate-secrets) | Submit request → L3 approves | Submit request → L3 approves | Execute directly |

### Requesting Approval

1. Navigate to the action in CommandBridge
2. Click **Request Approval**
3. Enter your ticket number, reason, and target
4. The request appears in the approval queue for L2/L3 reviewers

## Deployment Windows

| Window | Time (UTC) | Restrictions |
|---|---|---|
| **Standard** | Tuesday–Thursday, 09:00–16:00 | Normal change process |
| **Off-peak** | Weekdays 22:00–06:00 | Preferred for high-risk changes |
| **Freeze** | Announced quarterly | No changes except P1 incident response |
| **Emergency** | Any time | P1/P2 only, requires IC approval |

## Rollback Procedures

Every action should have a documented rollback:

- **Scale Service**: scale back to previous count
- **Purge Cache**: no rollback needed (cache self-rebuilds)
- **Restart Pods**: pods restart automatically; rollback the deployment if new version is faulty
- **Blacklist IP**: remove IP from WAF IP set (L2+ via Console)
- **Maintenance Mode**: toggle the flag back off
- **Failover Region**: reverse the Route 53 and RDS failover (L3 only)

## Post-Change Verification

After any change:
1. Monitor the affected service for **15 minutes**
2. Verify health checks are passing
3. Check error rates in CloudWatch
4. Update the ticket with the outcome
5. Close the ticket or escalate if issues arise

## Escalation

!!! info "Governance escalation"
    If a change causes unexpected impact, immediately pause further changes, declare an incident, and follow the escalation matrix.
