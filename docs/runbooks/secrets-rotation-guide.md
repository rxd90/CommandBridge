---
title: Secrets Rotation Guide
service: Secrets Manager
owner: Security
category: Security
tags: [secrets, rotation, credentials, security, how-to, compliance]
last_reviewed: 2026-02-14
---

# Secrets Rotation Guide: staged rotation for service credentials

## Overview

The **Rotate Secrets** action triggers staged credential rotation via AWS Secrets Manager for service-to-service authentication. This is the highest-risk action in CommandBridge — L1 and L2 must request approval; only L3 can execute directly.

## When to Rotate

| Trigger | Urgency |
|---|---|
| Scheduled rotation (quarterly compliance) | Planned — use CHG ticket, off-peak window |
| Suspected credential compromise | Emergency — rotate immediately, file INC ticket |
| Team member departure with credential access | Within 24 hours |
| Vendor credential refresh | Per vendor schedule |

## Pre-Rotation Checklist

Before initiating rotation, verify:

- [ ] **Identify the secret** — which service-to-service credential is being rotated
- [ ] **Confirm the rotation strategy** — single-user or multi-user rotation
- [ ] **Notify dependent services** — teams whose services consume the credential
- [ ] **Verify rollback capability** — can the previous credential be restored
- [ ] **Confirm deployment window** — off-peak preferred for planned rotations
- [ ] **Have your ticket ready** — INC for emergency, CHG for planned

## Rotation Process

### Staged Rotation (Standard)

AWS Secrets Manager rotation uses stages:

1. **createSecret** — new credential version created with `AWSPENDING` label
2. **setSecret** — new credential applied to the target service
3. **testSecret** — new credential tested (health check)
4. **finishSecret** — new credential promoted to `AWSCURRENT`, old moves to `AWSPREVIOUS`

### Step-by-Step via CommandBridge

1. Navigate to **Actions** and select **Rotate Secrets**
2. Select the **target secret** from the dropdown
3. Enter your **ticket number** and **reason**
4. **Submit for approval** (L1/L2) or **execute** (L3)
5. Monitor the rotation in the Secrets Manager console:
   - Verify the rotation Lambda completes all four stages
   - Check for `RotationFailed` events in CloudTrail

## Post-Rotation Validation

After rotation completes:

1. **Verify service connectivity** — check that dependent services can authenticate with the new credential
2. **Monitor error rates** — watch for `403`, `401`, or connection errors in CloudWatch for 15 minutes
3. **Check application logs** — look for credential-related errors
4. **Confirm both stages exist** — `AWSCURRENT` (new) and `AWSPREVIOUS` (old) should both be present

```bash
aws secretsmanager describe-secret --secret-id <secret-name> \
  --query 'VersionIdsToStages'
```

## Emergency Rotation

If you suspect a credential has been compromised:

1. **Immediately request rotation** via CommandBridge (P1 ticket)
2. **Do not wait for a maintenance window**
3. **Notify Security on-call** — they may need to audit access logs
4. **Monitor for unauthorized access** in CloudTrail for the affected service

## Rollback

If the new credential causes issues:

1. **Restore the previous version** in Secrets Manager:
   ```bash
   aws secretsmanager update-secret-version-stage \
     --secret-id <secret-name> \
     --version-stage AWSCURRENT \
     --move-to-version-id <previous-version-id> \
     --remove-from-version-id <new-version-id>
   ```
2. **Restart dependent services** to pick up the reverted credential
3. **Investigate** why the new credential failed before re-attempting

!!! warning "L3 only"
    Secret rollback via CLI is restricted to L3 admins. L1/L2 must escalate.

## Escalation

!!! warning "Escalation threshold"
    Escalate to Security Lead immediately if rotation fails, if you suspect a credential breach, or if dependent services cannot authenticate after rotation.
