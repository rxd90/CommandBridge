"""Pull logs from CloudWatch using filter-log-events."""

import re

import boto3

# Allowed log group name pattern (alphanumeric, hyphens, underscores, dots, slashes)
_LOG_GROUP_RE = re.compile(r'^[\w./-]+$')

# Maximum events to return per request
_MAX_LIMIT = 1000


def execute(body: dict) -> dict:
    """Filter and retrieve CloudWatch log events for a given log group and time range."""
    log_group = body.get("target", "")
    if not log_group or not _LOG_GROUP_RE.match(log_group):
        return {"status": "error", "message": "Invalid or missing log group name. Use alphanumeric, hyphens, underscores, dots, and slashes only."}

    environment = body.get("environment", "production")
    if not re.match(r'^[\w-]+$', environment):
        return {"status": "error", "message": "Invalid environment name."}

    start_time = body.get("start_time")
    end_time = body.get("end_time")
    filter_pattern = body.get("filter_pattern", "")

    limit = min(int(body.get("limit", 200)), _MAX_LIMIT)
    if limit < 1:
        limit = 1

    client = boto3.client("logs")
    params = {
        "logGroupName": f"/aws/{environment}/{log_group}",
        "limit": limit,
    }
    if start_time:
        params["startTime"] = int(start_time)
    if end_time:
        params["endTime"] = int(end_time)
    if filter_pattern:
        params["filterPattern"] = filter_pattern

    response = client.filter_log_events(**params)
    events = response.get("events", [])

    return {
        "status": "success",
        "message": f"Retrieved {len(events)} log events from {log_group}",
        "events": events,
    }
