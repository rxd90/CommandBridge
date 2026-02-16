---
title: Fraud & Risk Checks
service: CIFAS / AML
owner: Risk Ops
category: Backend
tags: [fraud, cifas, aml, risk, dependencies]
last_reviewed: 2026-01-02
---

# Fraud & Risk Checks Degraded (CIFAS/AML dependency)

## Symptoms

- Risk scores unavailable or returning default values
- AML checks timing out (> 5s response times)
- Elevated fallback/fail-open usage in risk engine logs
- Spike in manual review queue depth

## Checks

1. **Dependency health and network egress**
    ```bash
    # Test CIFAS API connectivity from within the VPC
    curl -s -o /dev/null -w "%{http_code} %{time_total}s" https://api.cifas.org.uk/health
    ```

2. **Rate limit or quota breaches**
    - Check API key usage against contracted rate limits
    - Review 429 responses in CloudWatch

3. **Fail-open/closed policy status**
    - Verify which actions are currently operating in fail-open mode
    - Check if high-risk actions (account creation, large transactions) are still gated

4. **Manual review queue depth**
    - Check SQS queue metrics for the fraud review queue
    - Verify review team is staffed and processing

## Mitigations

- **Enable degraded enrolment** for low-risk cohorts only (existing verified users)
- **Increase manual review queue capacity** — notify review team lead
- **Enable enhanced audit logging** for all actions taken during degraded state
- **Block new enrolments temporarily** if fraud indicators are rising
    - Use the **Pause Enrolments** action

## Escalation

!!! danger "Escalation threshold"
    Escalate immediately if:

    - High-risk actions (account creation with large value) are impacted
    - Fraud indicators (chargebacks, ATO reports) rise above baseline during degradation
    - CIFAS/AML provider confirms extended outage (> 2 hours)
