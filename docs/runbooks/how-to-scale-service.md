---
title: "How To: Scale Service"
service: ECS / EKS Autoscaling
owner: Platform Ops
category: Infrastructure
tags: [scaling, ecs, eks, how-to, capacity, autoscaling, replicas]
last_reviewed: 2026-02-14
---

# How To: Scale Service via CommandBridge

## Overview

The **Scale Service** action adjusts the desired task count for ECS services or HPA min/max replicas for EKS deployments. This is a medium-risk action available to L1 operators.

## When to Use

- Autoscaler is not responding fast enough to a traffic spike
- Preparing for a known high-traffic event (e.g., enrolment deadline)
- Reducing capacity during a maintenance window to save costs
- Restoring capacity after an incident

## Safe Scaling Guidelines

| Scenario | Recommended Action |
|---|---|
| Gradual traffic increase | Scale up by **25-50%** of current count |
| Sudden spike (>2x normal) | Scale to **2x current** then monitor |
| Pre-planned event | Scale to **anticipated peak + 20% headroom** |
| Post-incident recovery | Return to **normal baseline** count |

!!! warning "Never scale to zero"
    Always maintain at least the minimum healthy task count. Scaling to zero will cause a full outage.

## Step-by-Step

1. **Navigate to Actions** and select **Scale Service**
2. **Select the target service** (e.g., `scotaccount-auth`, `enrolment-api`)
3. **Set the desired count** - the new number of tasks or replicas
4. **Enter your ticket number and reason**
5. **Click Execute**
6. **Monitor scaling:**
   - Check ECS/EKS console for task health
   - Verify new tasks pass health checks (2-5 minutes)
   - Monitor CloudWatch `CPUUtilization` and `MemoryUtilization`

## Pre-Checks

Before scaling, verify:
- Current task count and health status
- Available cluster capacity (CPU/memory headroom)
- Recent deployment status - scaling during a rolling update can cause issues

## Rollback

To rollback, simply scale back to the previous count using the same action. If autoscaling is configured, it will eventually adjust back to normal - but manual scaling overrides the autoscaler temporarily.

## Escalation

!!! info "When to escalate"
    Escalate to L2 if new tasks fail health checks repeatedly, if cluster capacity is exhausted, or if the service does not stabilise within 10 minutes of scaling.
