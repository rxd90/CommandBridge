---
title: 2FA SMS Delivery Issues
service: MFA / SMS / Push
owner: Trust & Safety
category: Backend
tags: [mfa, sms, 2fa, otp, delivery, sns, scotaccount]
last_reviewed: 2026-02-16
---

# 2FA SMS Delivery Issues: diagnosing OTP delivery failures

## Symptoms

- Users reporting they are not receiving SMS verification codes
- Elevated MFA failure rate in CloudWatch dashboards
- SNS delivery failure logs showing `UNREACHABLE` or `BLOCKED` carriers
- Spike in support tickets related to "code not received"

## Checks

1. **Check SNS SMS delivery statistics**
    ```bash
    aws sns get-sms-attributes --attributes-to-get MonthlySpendLimit,DeliveryStatusSuccessRate
    ```

2. **Check SNS delivery logs** (if enabled)
    ```bash
    aws logs filter-log-events \
      --log-group-name sns/eu-west-2/DirectPublishToPhoneNumber/Failure \
      --start-time $(date -d '2 hours ago' +%s000)
    ```
    Look for `UNREACHABLE`, `BLOCKED`, or `CARRIER_UNREACHABLE` statuses.

3. **Verify monthly spend limit is not exhausted**
    - Default SNS SMS spend limit is $1.00/month — this must be increased for production
    - Check `MonthlySpendLimit` vs current month spend

4. **Check if specific carriers are affected**
    - UK mobile carriers (EE, Three, O2, Vodafone) sometimes block shortcode SMS
    - International numbers may be blocked by Cognito's SMS sandbox settings

## Mitigations

- **If spend limit reached**: Request a limit increase via AWS Support (takes 24-48 hours)
- **If specific carriers blocking**: Switch SMS origination type from shortcode to long code or toll-free number via Terraform
- **If widespread delivery failure**: Consider enabling TOTP (authenticator app) as a fallback MFA method
    - This requires a Cognito user pool configuration change via Terraform
- **For individual users**: Support team can manually verify via admin tools and reset MFA preference

## Prevention

- Monitor `SNS > SMSSuccessRate` CloudWatch metric with alarm at <95%
- Maintain spend limit headroom of at least 2x average monthly usage
- Regularly test SMS delivery to UK carrier numbers as part of smoke tests

## Escalation

!!! warning "Escalation threshold"
    Escalate to Identity Platform on-call if SMS delivery success rate drops below 90% for more than 30 minutes, or if a single carrier shows 0% delivery.
