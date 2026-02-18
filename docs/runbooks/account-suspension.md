---
title: Account Suspension
service: Cognito User Pool
owner: Trust & Safety
category: Security
tags: [cognito, disable, suspend, user, account, investigation, scotaccount]
last_reviewed: 2026-02-17
---

# Account Suspension: disable user accounts pending investigation

> **Note:** Replace `$USER_POOL_ID` in commands below with the value from `terraform output cognito_user_pool_id`.

## Symptoms / Triggers

- Fraud team flags an account for suspicious enrolment activity
- Multiple failed MFA attempts suggesting brute-force attack
- User reports identity theft and requests account freeze
- Automated anomaly detection triggers (e.g. impossible travel)

## Checks

1. **Verify the account exists and its current status**
    ```bash
    aws cognito-idp admin-get-user \
      --user-pool-id $USER_POOL_ID \
      --username <email>
    ```
    Check `Enabled` field and `UserStatus`.

2. **Review recent activity**
    ```bash
    aws cognito-idp admin-list-user-auth-events \
      --user-pool-id $USER_POOL_ID \
      --username <email> \
      --max-results 25
    ```

3. **Check if account has active sessions**
    - If yes, consider revoking sessions first using the **Revoke User Sessions** action

## Mitigations

- **Disable the account** using the **Disable User Account** action in CommandBridge
    - This calls `AdminDisableUser` - the user cannot sign in but data is preserved
    - Existing active sessions remain valid until tokens expire (use **Revoke User Sessions** for immediate effect)
- **For full lockout**: run both **Revoke User Sessions** then **Disable User Account**
- **To re-enable** after investigation clears the user:
    ```bash
    aws cognito-idp admin-enable-user \
      --user-pool-id $USER_POOL_ID \
      --username <email>
    ```

## Important Notes

- Disabling does **not** delete the user or their data
- The user's MySafe verified attributes remain intact
- Audit all suspension actions - every disable/enable is logged to the audit trail
- Follow Scottish Government data protection guidelines for account suspension duration

## Escalation

!!! warning "Escalation threshold"
    Escalate to Trust & Safety lead if more than 5 accounts require suspension within 24 hours, or if the suspension is related to a confirmed data breach.
