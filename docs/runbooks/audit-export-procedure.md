---
title: Audit Export Procedure
service: DynamoDB Audit Table
owner: Platform Ops
category: Security
tags: [audit, export, compliance, s3, dynamodb, investigation]
last_reviewed: 2026-02-16
---

# Audit Export Procedure: export audit trail for compliance or investigation

## When to Use

- Compliance team requests audit records for a specific time period
- Security investigation requires full audit trail for an incident
- Scheduled quarterly compliance export
- Data subject access request (DSAR) requiring action history

## Procedure

1. **Determine the date range** for the export
    - For incident investigation: from first suspicious activity to present
    - For compliance: typically the full quarter

2. **Run the export** using the **Export Audit Log** action in CommandBridge
    - Specify start and end dates in ISO format
    - The action scans the DynamoDB audit table and writes JSON to S3

3. **Verify the export**
    ```bash
    aws s3 ls s3://commandbridge.site/audit-exports/ --recursive
    ```

4. **Download for analysis** (if needed)
    ```bash
    aws s3 cp s3://commandbridge.site/audit-exports/audit-<timestamp>.json ./
    ```

## Audit Record Format

Each record contains:
- `id`: Unique event identifier
- `timestamp`: ISO 8601 timestamp
- `user`: Email of the operator who performed the action
- `action`: Action ID (e.g. `purge-cache`, `revoke-sessions`)
- `target`: What was acted upon
- `ticket`: Reference ticket number
- `result`: `success`, `failed`, `requested`, or `denied`
- `approved_by`: (optional) Approver for high-risk actions
- `details`: (optional) Additional context

## Data Retention

- DynamoDB audit records are retained indefinitely with point-in-time recovery enabled
- S3 exports follow the standard bucket lifecycle policy

## Escalation

!!! info "Note"
    This is a read-only operation. No escalation is typically required unless the export reveals suspicious activity, in which case follow the incident response procedure.
