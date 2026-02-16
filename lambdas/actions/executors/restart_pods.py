"""Restart Kubernetes pods via SSM RunCommand."""

import boto3


def execute(body: dict) -> dict:
    """Run kubectl rollout restart on target instances through SSM."""
    deployment = body["target"]
    namespace = body.get("namespace", "default")
    environment = body.get("environment", "production")
    instance_ids = body.get("instance_ids", [])

    ssm = boto3.client("ssm")
    command = f"kubectl rollout restart deployment/{deployment} -n {namespace}"

    response = ssm.send_command(
        InstanceIds=instance_ids,
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [command]},
        Comment=f"Restart pods: {deployment} in {environment}/{namespace}",
        TimeoutSeconds=120,
    )

    command_id = response["Command"]["CommandId"]

    return {
        "status": "success",
        "message": f"Rollout restart issued for {deployment} in {namespace}",
        "command_id": command_id,
    }
