"""Scale an ECS service to a desired task count."""

import re

import boto3

# Min/max bounds for desired task count
_MIN_DESIRED = 0
_MAX_DESIRED = 100

# Allowed service/cluster name pattern
_NAME_RE = re.compile(r'^[\w-]+$')


def execute(body: dict) -> dict:
    """Update the desired count of an ECS service."""
    service = body.get("target", "")
    if not service or not _NAME_RE.match(service):
        return {"status": "error", "message": "Invalid or missing service name. Use alphanumeric characters and hyphens only."}

    cluster = body.get("cluster", body.get("environment", "production"))
    if not _NAME_RE.match(cluster):
        return {"status": "error", "message": "Invalid cluster name."}

    try:
        desired_count = int(body["desired_count"])
    except (KeyError, ValueError, TypeError):
        return {"status": "error", "message": "desired_count is required and must be an integer."}

    if desired_count < _MIN_DESIRED or desired_count > _MAX_DESIRED:
        return {"status": "error", "message": f"desired_count must be between {_MIN_DESIRED} and {_MAX_DESIRED}."}

    ecs = boto3.client("ecs")
    response = ecs.update_service(
        cluster=cluster,
        service=service,
        desiredCount=desired_count,
    )

    svc = response["service"]
    running = svc["runningCount"]
    pending = svc["pendingCount"]

    return {
        "status": "success",
        "message": (
            f"Scaled {service} to {desired_count} tasks "
            f"(running={running}, pending={pending})"
        ),
        "running_count": running,
        "pending_count": pending,
    }
