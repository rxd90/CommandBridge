---
title: Data Subject Access Request (DSAR) Procedure
service: ScotAccount Data
owner: Trust & Safety
category: Security
tags: [dsar, gdpr, data-protection, privacy, compliance, scotaccount]
last_reviewed: 2026-02-16
---

# Data Subject Access Request (DSAR) Procedure

## Background

Under UK GDPR and the Data Protection Act 2018, individuals have the right to request a copy of their personal data. ScotAccount must respond to DSARs within 30 calendar days.

## Scope of Data

ScotAccount holds the following categories of personal data:
- **Account data**: email, phone number, account creation date
- **Authentication events**: login timestamps, IP addresses, device info
- **Identity verification data**: document type submitted, verification result, provider used
- **MySafe attributes**: any verified personal information the user chose to store
- **Audit trail**: actions taken on or by the user's account via CommandBridge

## Procedure

### 1. Verify the Request

- [ ] Confirm the requester's identity (email match, phone verification)
- [ ] Log the DSAR in the compliance tracker with the 30-day deadline
- [ ] Acknowledge receipt within 3 working days

### 2. Gather Data

- **Cognito account data**:
    ```bash
    aws cognito-idp admin-get-user \
      --user-pool-id eu-west-2_quMz1HdKl \
      --username <email>
    ```

- **Authentication events**:
    ```bash
    aws cognito-idp admin-list-user-auth-events \
      --user-pool-id eu-west-2_quMz1HdKl \
      --username <email> \
      --max-results 100
    ```

- **Audit trail**: Use the **Export Audit Log** action in CommandBridge, then filter for the user's email

- **DynamoDB records**: Query any application-specific tables for the user's ID

### 3. Compile and Review

- [ ] Combine all data into a structured report
- [ ] Review for third-party personal data that must be redacted
- [ ] Review for data that is exempt from disclosure (e.g. fraud prevention)
- [ ] Have the report reviewed by the Data Protection Officer

### 4. Deliver

- [ ] Send the compiled data to the requester via a secure channel
- [ ] Log the completion in the compliance tracker
- [ ] Retain a record of the DSAR and response for 3 years

## Escalation

!!! info "Escalation"
    Escalate to the Data Protection Officer if the request is complex, involves third-party data, or cannot be completed within the 30-day deadline.
