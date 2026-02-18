---
title: WAF IP Blocking Guide
service: WAF
owner: Security
category: Security
tags: [waf, ip, blocking, security, abuse, rate-limiting, how-to]
last_reviewed: 2026-02-14
---

# WAF IP Blocking Guide: when and how to block abusive traffic

## Overview

The **Blacklist IP** action adds IP addresses or CIDR ranges to the WAF IP set, blocking traffic at the AWS edge before it reaches application servers. This is a high-risk action - L1 operators must request approval; L2+ can execute directly.

## When to Block vs When to Rate Limit

| Signal | Action |
|---|---|
| Single IP sending >1000 req/min | **Rate limit** first, block if it persists |
| Known malicious IP from threat feed | **Block** immediately |
| Credential stuffing pattern (many users, one IP) | **Block** the source IP range |
| Distributed attack from many IPs | **Escalate** - IP blocking won't help |
| Legitimate user with a misconfigured client | **Do not block** - contact the user |

## Identifying Abusive IPs

1. **Check WAF sampled requests** in the AWS Console under WAF > Web ACLs
2. **Pull CloudWatch Logs** for the API Gateway and look for high-frequency source IPs:
    ```
    fields @timestamp, httpMethod, sourceIp
    | stats count() as requests by sourceIp
    | sort requests desc
    | limit 20
    ```
3. **Check for known bad IPs** against public threat intelligence (AbuseIPDB, Shodan)

## Step-by-Step

1. **Document the evidence** - note the IP, request volume, pattern, and impact
2. **Navigate to Actions** and select **Blacklist IP**
3. **Enter the IP or CIDR range** (e.g., `203.0.113.0/24`)
4. **Set a duration** - prefer time-limited blocks (24h, 72h) over permanent
5. **Enter your ticket number and reason** with the evidence summary
6. **Submit for approval** (L1) or **execute directly** (L2+)

## Best Practices

- Always block **CIDR ranges** rather than individual IPs when the source is a known bad network
- Use **time-limited blocks** as the default - permanent blocks should be rare and reviewed quarterly
- **Never block AWS IP ranges**, CDN ranges, or government network ranges without L3 approval
- Log the block in the incident channel so other teams are aware

## Removing a Block

To unblock an IP, create a new ticket and have an L2+ engineer remove it from the WAF IP set via the AWS Console. There is currently no "unblock" action in CommandBridge.

## Escalation

!!! warning "Escalation threshold"
    Escalate to Security on-call if you observe a coordinated DDoS pattern, credential stuffing across multiple IPs, or if the attack is bypassing WAF rules.
