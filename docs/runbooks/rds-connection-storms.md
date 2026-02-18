---
title: RDS Connection Storms
service: RDS / Aurora
owner: Data Services
category: Infrastructure
tags: [rds, database, connections, timeouts, pools, aurora, failover]
last_reviewed: 2026-01-07
---

# RDS Connection Storms: timeouts, pool exhaustion, failover confusion

## Symptoms

- Application timeouts with normal RDS CPU utilisation
- `too many connections` errors in application logs
- Sudden connection count spike in CloudWatch `DatabaseConnections` metric
- Applications connecting to wrong endpoint (writer vs reader) after failover

## Checks

1. **Current connection count vs max**
    ```bash
    aws cloudwatch get-metric-statistics --namespace AWS/RDS \
      --metric-name DatabaseConnections --dimensions Name=DBInstanceIdentifier,Value=<instance> \
      --start-time <30m-ago> --end-time <now> --period 60 --statistics Maximum
    ```

2. **Pool configuration per service**
    - Verify connection pool `max_size` in each service's config
    - Check for pool leak indicators: connections growing without release

3. **Query plan regressions**
    - Check RDS Performance Insights for slow queries
    - Look for missing indexes on recently added queries

4. **Reader/writer endpoint usage**
    - After a failover, verify applications are connecting to the correct cluster endpoint
    - Check if hardcoded instance endpoints are being used instead of cluster endpoints

## Mitigations

- **Reduce application concurrency** - lower connection pool max size
- **Kill idle connections** if pool is exhausted
    ```sql
    SELECT pg_terminate_backend(pid) FROM pg_stat_activity
    WHERE state = 'idle' AND query_start < NOW() - INTERVAL '10 minutes';
    ```
- **Scale vertically** only after concurrency is controlled (bigger instance = more max connections)
- **Trigger regional failover** if the primary instance is unrecoverable
    - Use the **Failover Region** action (requires L2 approval)

## Escalation

!!! danger "Escalation threshold"
    Escalate if connection storms cause cascading failures in **two or more regions**, or if RDS failover does not resolve the issue within 15 minutes.
