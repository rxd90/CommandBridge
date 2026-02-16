---
title: ScotAccount Service Onboarding Checklist
service: ScotAccount Integration
owner: Platform Ops
category: Backend
tags: [onboarding, integration, oidc, relying-party, scotaccount]
last_reviewed: 2026-02-16
---

# ScotAccount Service Onboarding Checklist

## Purpose

This checklist covers the steps required to onboard a new Scottish public service as a relying party on ScotAccount. It ensures consistent integration patterns across all consuming services.

## Pre-requisites

- [ ] Service has been assessed against the Digital Scotland Service Standard
- [ ] Data Protection Impact Assessment (DPIA) completed
- [ ] Service team has nominated a technical lead and an operational contact
- [ ] OAuth2/OIDC integration capability confirmed in the service architecture

## Integration Steps

### 1. Register the Relying Party

- [ ] Create a new Cognito app client via Terraform (`infra/modules/cognito/`)
- [ ] Configure allowed OAuth scopes: `openid`, `email`, `profile`
- [ ] Set callback URLs for the service (staging + production)
- [ ] Set sign-out URLs

### 2. Configure Claims Mapping

- [ ] Map required user attributes (email, phone, name)
- [ ] Configure optional claims based on service needs (e.g. verified address)
- [ ] Validate claim mapping in staging environment

### 3. Identity Verification Level

- [ ] Determine if the service requires IDV (identity document verification)
- [ ] If yes, configure the verification level (basic / enhanced)
- [ ] Test the IDV flow end-to-end in staging

### 4. Operational Readiness

- [ ] Service team has access to CommandBridge at the appropriate RBAC level
- [ ] Relevant runbooks reviewed (Login Failures, MFA Issues, IDV Failures)
- [ ] Alerting configured for authentication error rates
- [ ] Escalation path documented in the escalation matrix

### 5. Go-Live

- [ ] Production OAuth client created and tested
- [ ] DNS and TLS configured for production callback URLs
- [ ] Load testing completed against expected user volumes
- [ ] Comms plan in place for user migration (if applicable)

## Post-Onboarding

- [ ] Monitor authentication success rate for 7 days
- [ ] Review CloudWatch dashboards for anomalies
- [ ] Confirm audit logging captures events for the new service
- [ ] Schedule first quarterly review with the service team
