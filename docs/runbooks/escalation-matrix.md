---
title: Escalation Matrix
service: Operations
owner: Ops Management
category: Infrastructure
tags: [escalation, on-call, severity, process, incident, contacts]
last_reviewed: 2026-02-14
---

# Escalation Matrix: severity definitions, contacts, and procedures

## Severity Definitions

| Severity | Criteria | Response Time | Update Cadence |
|---|---|---|---|
| **P1 — Critical** | Complete service outage or >50% of users affected. Data loss risk. Security breach. | 15 minutes | Every 15 min |
| **P2 — Major** | Significant degradation affecting 10-50% of users. Key workflow blocked. | 30 minutes | Every 30 min |
| **P3 — Minor** | Limited impact affecting <10% of users. Workaround available. | 2 hours | Every 2 hours |

## Escalation Contacts by Service Area

| Service Area | L2 On-Call | L3 Escalation | Vendor |
|---|---|---|---|
| **Auth / OIDC** | Identity Platform on-call | IAM/Security Lead | — |
| **Enrolment** | Enrolment Team on-call | Enrolment Lead | IDV Provider support |
| **MFA / SMS** | Trust & Safety on-call | Security Lead | SMS Gateway support |
| **API Gateway** | Platform Ops on-call | Platform Engineering Lead | AWS Support |
| **EKS / Kubernetes** | Platform Engineering on-call | Platform Engineering Lead | AWS Support |
| **RDS / Aurora** | Data Services on-call | Data Services Lead | AWS Support |
| **Redis / ElastiCache** | Identity Platform on-call | Platform Engineering Lead | AWS Support |
| **WAF / Security** | Security on-call | Security Lead | AWS Support |
| **Fraud / CIFAS** | Risk Ops on-call | Risk Ops Lead | CIFAS support desk |

## Escalation Flow

```
L1 Operator detects issue
    │
    ├── Can resolve with L1 actions? ──→ Execute action, log, close
    │
    └── Needs approval or beyond L1 scope?
        │
        ├── Request approval in CommandBridge (high-risk actions)
        │
        └── Escalate to L2 on-call via Slack #inc-bridge
            │
            ├── L2 resolves ──→ Log, update incident, close
            │
            └── Beyond L2 scope or P1 severity?
                │
                └── Escalate to L3 / Service Lead
                    │
                    ├── Engage vendor support if external dependency
                    └── Notify leadership if P1 > 30 min
```

## When to Engage Vendor Support

- **AWS Support**: Infrastructure-level issues not resolvable via standard operations (e.g., service-level outage, API throttling beyond account limits)
- **IDV Provider**: Document verification failure rates >20% for >15 minutes
- **SMS Gateway**: OTP delivery failure rates >10% or delivery latency >60 seconds
- **CIFAS**: Fraud check timeout rates >25% or complete unavailability

## On-Call Expectations

- Acknowledge pages within **5 minutes**
- Join the incident bridge within **15 minutes** for P1
- Provide first update within the response time for the severity level
- Hand off to next on-call if incident extends beyond your shift

## Escalation

!!! warning "Emergency escalation"
    For suspected data breaches, PII exposure, or regulatory incidents, escalate immediately to the Security Lead and Legal — do not wait for severity assessment.
