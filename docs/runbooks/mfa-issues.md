---
title: MFA Issues
service: MFA / SMS / Push
owner: Trust & Safety
category: Backend
tags: [mfa, sms, otp, sim-swap, ato, fraud, push]
last_reviewed: 2026-01-05
---

# MFA Issues: OTP delays, SIM swap suspicion, push failures

## Symptoms

- OTP delivery delays exceeding 60 seconds
- Spike in MFA reset requests from unusual IP ranges
- Push notification failures for a specific carrier or device type
- MFA failures concentrated in a single region or carrier
- Reports of account takeover (ATO) following MFA reset

## Checks

1. **MFA provider delivery metrics**
    - Check SMS delivery success rate and latency in provider dashboard
    - Compare delivery rates across carriers (Vodafone, EE, Three, O2)

2. **Burst traffic from single ASN/IP ranges**
    ```bash
    # Check WAF logs for concentrated MFA reset requests
    aws waf-regional get-sampled-requests --web-acl-id <id> --rule-id <mfa-rule> --time-window ...
    ```

3. **MFA reset audit logs**
    - Look for device/IP mismatches: reset requested from one IP, login from another
    - Check for multiple resets on the same account within 24 hours

4. **Carrier status pages**
    - Check BT, Vodafone, EE, Three status pages for known SMS routing issues

## Mitigations

- **Enable step-up verification** for MFA resets — require email confirmation before processing
- **Throttle retry attempts** — max 3 OTP requests per account per 5-minute window
- **Temporarily disable MFA reset** for high-risk cohorts (accounts with recent password changes)
    - Use the **Disable MFA Reset** action (request approval via CommandBridge)
- **Block suspicious IP ranges** at WAF if concentrated abuse is detected
    - Use the **Blacklist IP** action

## Escalation

!!! danger "Escalation threshold"
    Escalate immediately to Trust & Safety if:

    - Confirmed SIM swap correlation (reset + login from different devices within minutes)
    - More than 10 accounts show ATO indicators in a 1-hour window
    - Carrier confirms routing compromise
