"""Pull logs from CloudWatch using filter-log-events."""

import boto3


def execute(body: dict) -> dict:
    """Filter and retrieve CloudWatch log events for a given log group and time range."""
    log_group = body["target"]
    environment = body.get("environment", "production")
    start_time = body.get("start_time")
    end_time = body.get("end_time")
    filter_pattern = body.get("filter_pattern", "")

    client = boto3.client("logs")
    params = {
        "logGroupName": f"/aws/{environment}/{log_group}",
        "limit": body.get("limit", 200),
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
