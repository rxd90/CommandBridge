"""Drain traffic by deregistering targets from an ALB target group."""

import re

import boto3

_ARN_RE = re.compile(r'^arn:aws:elasticloadbalancing:[\w-]+:\d+:targetgroup/[\w-]+/[\da-f]+$')
_INSTANCE_ID_RE = re.compile(r'^i-[\da-f]+$')


def execute(body: dict) -> dict:
    """Deregister targets from an ALB target group to drain traffic."""
    target_group_arn = body.get("target", "")
    if not target_group_arn or not _ARN_RE.match(target_group_arn):
        return {"status": "error", "message": "target must be a valid ALB target group ARN."}

    instance_ids = body.get("instance_ids", [])
    if not isinstance(instance_ids, list) or len(instance_ids) == 0:
        return {"status": "error", "message": "instance_ids must be a non-empty list."}

    for iid in instance_ids:
        if not isinstance(iid, str) or not _INSTANCE_ID_RE.match(iid):
            return {"status": "error", "message": f"Invalid instance ID: {iid}. Must match i-<hex>."}

    try:
        port = int(body.get("port", 80))
    except (ValueError, TypeError):
        return {"status": "error", "message": "port must be a valid integer."}
    if port < 1 or port > 65535:
        return {"status": "error", "message": "port must be between 1 and 65535."}

    targets = [{"Id": iid, "Port": port} for iid in instance_ids]

    elbv2 = boto3.client("elbv2")
    elbv2.deregister_targets(
        TargetGroupArn=target_group_arn,
        Targets=targets,
    )

    # Don't wait for full deregistration — Lambda has a 30s timeout.
    # Just confirm the deregister call succeeded.
    try:
        waiter = elbv2.get_waiter("target_deregistered")
        waiter.wait(
            TargetGroupArn=target_group_arn,
            Targets=targets,
            WaiterConfig={"Delay": 2, "MaxAttempts": 5},
        )
        drain_status = "drained"
    except Exception:
        drain_status = "draining"

    return {
        "status": "success",
        "message": f"Deregistered {len(instance_ids)} targets from {target_group_arn} ({drain_status})",
        "deregistered_ids": instance_ids,
        "drain_status": drain_status,
    }
