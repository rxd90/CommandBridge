"""Restart Kubernetes pods via SSM RunCommand."""

import re
import boto3

# Kubernetes resource name: alphanumeric and hyphens, 1–253 chars
_K8S_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9\-]{0,251}[a-z0-9]$|^[a-z0-9]$')

# EC2 instance ID
_INSTANCE_ID_RE = re.compile(r'^i-[0-9a-f]{17}$')

_MAX_INSTANCES = 20


def execute(body: dict) -> dict:
    """Run kubectl rollout restart on target instances through SSM."""
    deployment = body.get("target", "").strip()
    if not deployment or not _K8S_NAME_RE.match(deployment):
        return {"status": "error", "message": "Invalid deployment name. Use lowercase alphanumeric and hyphens only."}

    namespace = body.get("namespace", "default").strip()
    if not namespace or not _K8S_NAME_RE.match(namespace):
        return {"status": "error", "message": "Invalid namespace. Use lowercase alphanumeric and hyphens only."}

    environment = body.get("environment", "production").strip()
    if not re.match(r'^[a-z0-9][a-z0-9\-]{0,62}$', environment):
        return {"status": "error", "message": "Invalid environment name."}

    instance_ids = body.get("instance_ids", [])
    if not isinstance(instance_ids, list) or len(instance_ids) == 0:
        return {"status": "error", "message": "instance_ids must be a non-empty list."}
    if len(instance_ids) > _MAX_INSTANCES:
        return {"status": "error", "message": f"Too many instance_ids (max {_MAX_INSTANCES})."}
    for iid in instance_ids:
        if not isinstance(iid, str) or not _INSTANCE_ID_RE.match(iid):
            return {"status": "error", "message": f"Invalid instance ID format: {iid!r}. Must match i-<17 hex chars>."}

    ssm = boto3.client("ssm")

    # Build command from validated components — no shell interpolation of user input
    command = "kubectl rollout restart deployment/{} -n {}".format(deployment, namespace)

    response = ssm.send_command(
        InstanceIds=instance_ids,
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [command]},
        Comment="Restart pods: {}/{} ({})".format(deployment, namespace, environment),
        TimeoutSeconds=120,
    )

    command_id = response["Command"]["CommandId"]

    return {
        "status": "success",
        "message": "Rollout restart issued for {} in {}".format(deployment, namespace),
        "command_id": command_id,
    }
