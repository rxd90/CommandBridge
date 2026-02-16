"""Scale an ECS service to a desired task count."""

import boto3


def execute(body: dict) -> dict:
    """Update the desired count of an ECS service."""
    service = body["target"]
    cluster = body.get("cluster", body.get("environment", "production"))
    desired_count = int(body["desired_count"])

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
