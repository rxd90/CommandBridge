---
title: Incident Communications
service: Communications
owner: Comms Lead
category: Infrastructure
tags: [comms, updates, template, stakeholder, incident]
last_reviewed: 2026-01-01
---

# Incident Comms: update template (internal + external)

## Symptoms

- Stakeholders asking for updates without a structured cadence
- Confusion about impact scope across teams
- Inconsistent messaging between internal and external channels

## Update Template

Use the following format for all incident communications:

### Internal Update (Slack #inc-bridge)

```
🔴 INC-YYYY-MMDD-XXX | P<1/2/3> | <Status>

Impact: <What is affected and who is impacted>
Mitigation: <What has been done / is in progress>
Next update: <HH:MM UTC>
IC: <Incident Commander name>
```

### External Update (Status Page)

```
Investigating: <Service Name>

We are aware of issues affecting <service description>.
Users may experience <user-visible symptoms>.
Our team is actively investigating and we will provide an update by <HH:MM UTC>.
```

### Leadership Brief (Email)

```
Subject: [P<X>] <Short summary> - <HH:MM UTC> update

Impact: <Number of users affected, regions, duration so far>
Current status: <Investigating / Mitigating / Monitoring / Resolved>
Mitigation actions: <What has been done>
ETA to resolution: <Best estimate or "Under investigation">
Next update: <HH:MM UTC>
```

## Comms Cadence

| Audience | Channel | Cadence | Owner |
|---|---|---|---|
| Internal Eng | #inc-bridge (Slack) | Every 15 minutes during P1 | Incident Commander |
| Support Desk | #support-ops (Slack) | Every 30 minutes | Comms Lead |
| External Status | Status Page | Hourly | Comms Lead (approval required) |
| Leadership | Email brief | Hourly during P1, on-close for P2/P3 | Deputy IC |

## Checks

- Confirm incident owner and comms cadence on the bridge
- Align status page wording with internal summary (no conflicting information)
- Verify next update time is realistic and committed

## Escalation

!!! info "Escalation threshold"
    Escalate if public channels require **legal or compliance review** (data breach, PII exposure, regulatory reporting).
