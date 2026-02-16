---
title: Session Revocation
service: Cognito User Pool
owner: Identity Platform
category: Security
tags: [session, revoke, cognito, compromised, tokens, scotaccount]
last_reviewed: 2026-02-16
---

# Session Revocation: force sign-out compromised users

## Symptoms

- User reports unauthorised account activity or credential theft
- Anomalous login patterns detected (e.g. simultaneous sessions from different geolocations)
- Security team flags a user account for investigation
- Suspicious token reuse after password reset

## Checks

1. **Verify the user exists and is active**
    ```bash
    aws cognito-idp admin-get-user \
      --user-pool-id eu-west-2_quMz1HdKl \
      --username <email>
    ```

2. **Check recent auth events for the user**
    ```bash
    aws cognito-idp admin-list-user-auth-events \
      --user-pool-id eu-west-2_quMz1HdKl \
      --username <email> \
      --max-results 10
    ```
    Look for logins from unexpected IP ranges or user agents.

3. **Review CloudTrail for Cognito API calls**
    ```bash
    aws cloudtrail lookup-events \
      --lookup-attributes AttributeKey=Username,AttributeValue=<email> \
      --max-results 20
    ```

## Mitigations

- **Revoke all sessions** using the **Revoke User Sessions** action in CommandBridge
    - This calls `AdminUserGlobalSignOut`, invalidating all refresh tokens
    - Active access tokens remain valid until expiry (max 1 hour)
- **Force password reset** if credentials are confirmed compromised
    ```bash
    aws cognito-idp admin-reset-user-password \
      --user-pool-id eu-west-2_quMz1HdKl \
      --username <email>
    ```
- **Disable the account** using the **Disable User Account** action if immediate lockout is needed
- **Review and rotate** any service-to-service credentials the user may have accessed

## Escalation

!!! warning "Escalation threshold"
    Escalate to Security on-call immediately if more than 3 accounts show signs of compromise within a 1-hour window, as this may indicate a credential stuffing attack or identity provider breach.
