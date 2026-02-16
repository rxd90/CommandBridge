"""Drain traffic by deregistering targets from an ALB target group."""

import boto3


def execute(body: dict) -> dict:
    """Deregister targets from an ALB target group to drain traffic."""
    target_group_arn = body["target"]
    instance_ids = body.get("instance_ids", [])
    port = int(body.get("port", 80))

    targets = [{"Id": iid, "Port": port} for iid in instance_ids]

    elbv2 = boto3.client("elbv2")
    elbv2.deregister_targets(
        TargetGroupArn=target_group_arn,
        Targets=targets,
    )

    waiter = elbv2.get_waiter("target_deregistered")
    waiter.wait(
        TargetGroupArn=target_group_arn,
        Targets=targets,
        WaiterConfig={"Delay": 10, "MaxAttempts": 30},
    )

    return {
        "status": "success",
        "message": f"Deregistered {len(instance_ids)} targets from {target_group_arn}",
        "deregistered_ids": instance_ids,
    }
