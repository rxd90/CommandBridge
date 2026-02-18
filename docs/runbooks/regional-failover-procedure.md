---
title: Regional Failover Procedure
service: Route 53 / RDS
owner: Platform Engineering
category: Infrastructure
tags: [failover, region, route53, rds, disaster-recovery, how-to, dns]
last_reviewed: 2026-02-14
---

# Regional Failover Procedure: decision criteria, execution, and failback

## Overview

The **Failover Region** action overrides Route 53 health checks and triggers RDS failover to shift traffic from a degraded primary region (eu-west-2) to the standby region (eu-west-1). This is a high-risk action - L1 must request approval; L2+ can execute directly.

## Decision Criteria

Initiate regional failover ONLY when:

| Condition | Threshold |
|---|---|
| Primary region completely unreachable | >5 minutes confirmed by multiple monitors |
| Multiple critical services degraded simultaneously | Auth + Enrolment + API all affected |
| RDS writer node unresponsive | Aurora failover not triggered automatically after 3 minutes |
| No improvement after standard mitigations | Cache purge, pod restart, scaling all attempted |

!!! danger "Do not failover for"
    - Single service degradation (use service-level mitigations first)
    - Intermittent issues (wait for sustained failure pattern)
    - Performance degradation without errors (scale first)

## Pre-Failover Checklist

- [ ] **Confirm primary region is genuinely down** - not a monitoring false positive
- [ ] **Verify standby region is healthy** - check eu-west-1 service health
- [ ] **Notify all teams** - post in #inc-bridge: "Preparing for regional failover"
- [ ] **Open a P1 incident ticket** if not already open
- [ ] **Get L2+ approval** (L1 operators must request)

## Failover Procedure

### Step 1: Initiate via CommandBridge

1. Navigate to **Actions** and select **Failover Region**
2. Confirm the **target region** (eu-west-1)
3. Enter your **P1 ticket number** and **reason**
4. **Execute** (L2+) or **submit for approval** (L1)

### Step 2: What Happens Automatically

The failover action:
1. **Inverts Route 53 health check** - marks primary as unhealthy, standby as healthy
2. **DNS propagation** - Route 53 begins routing traffic to eu-west-1 (TTL-dependent, typically 60-300 seconds)
3. **RDS failover** - Aurora promotes the eu-west-1 read replica to writer (1-2 minutes)

### Step 3: Post-Failover Verification

1. **Check DNS resolution** - verify `api.scotaccount.gov.uk` resolves to eu-west-1 endpoints
2. **Test login flow** - complete an end-to-end authentication test
3. **Monitor error rates** - watch for elevated errors during the transition window (5-10 minutes)
4. **Verify data consistency** - check for replication lag or stale reads

## Expected Timeline

| Event | Time |
|---|---|
| Failover initiated | T+0 |
| Route 53 health check updated | T+30s |
| DNS propagation (most clients) | T+1-5 min |
| RDS replica promoted | T+1-2 min |
| Services stable in standby region | T+5-10 min |
| Full DNS propagation (all clients) | T+5-15 min |

## Failback Procedure

Once the primary region is restored:

1. **Verify primary region health** - all services passing health checks
2. **Re-enable RDS replication** - set eu-west-2 as the writer, eu-west-1 as read replica
3. **Update Route 53 health checks** - restore original configuration
4. **Monitor for 30 minutes** - watch for any issues during failback
5. **Close the incident** once stable

!!! warning "Failback timing"
    Do not failback during peak hours. Wait for an off-peak window unless there is a pressing reason to return to primary immediately.

## Escalation

!!! warning "Escalation threshold"
    Escalate to Platform Engineering Lead and AWS Support if failover does not complete within 15 minutes, if the standby region shows issues, or if data inconsistency is detected.
