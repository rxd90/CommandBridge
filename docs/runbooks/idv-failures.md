---
title: IDV Failures
service: Document Verification
owner: Enrolment
category: Backend
tags: [idv, documents, passport, driving-licence, enrolment, vendor]
last_reviewed: 2026-01-06
---

# Document Verification Failures: passport/DL rejects spike

## Symptoms

- High reject rates for a specific document type (passport, driving licence) or region
- IDV provider latency exceeding 10s p95
- S3 upload failures or presigned URL errors
- Users abandoning enrolment at the document capture step

## Checks

1. **Failure rates by document type and device/OS**
    ```bash
    # Query CloudWatch Insights for IDV failures
    fields @timestamp, doc_type, device_os, result
    | filter result = "REJECTED"
    | stats count() by doc_type, device_os
    | sort count desc
    ```

2. **IDV provider status and latency**
    - Check provider status dashboard for known degradation
    - Review API response times in CloudWatch metrics

3. **S3 upload path**
    - Verify presigned URL generation is working (check expiry, size limits)
    - Check S3 bucket policy for recent changes

4. **Recent deployment changes**
    - Check if image processing parameters (resolution, format) changed
    - Verify camera capture SDK version on mobile

## Mitigations

- **Switch to backup IDV provider** if configured and primary is degraded
- **Increase retry backoff** for transient provider errors
- **Communicate guidance to support desk** — provide workaround messaging for affected users
- **Temporarily increase S3 presigned URL expiry** if upload timeouts are the root cause

## Escalation

!!! warning "Escalation threshold"
    Escalate if reject rate exceeds **25% for all document types** across core regions for longer than 30 minutes.
