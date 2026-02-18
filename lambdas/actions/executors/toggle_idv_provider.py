"""Toggle the active identity document verification provider."""

import os

import boto3


def execute(body: dict) -> dict:
    """Switch the active IDV provider by updating the SSM parameter
    that controls which verification backend is used."""
    target_provider = body["target"]
    param_name = body.get("param_name", "/scotaccount/idv/active-provider")

    ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "eu-west-2"))
    ssm.put_parameter(
        Name=param_name,
        Value=target_provider,
        Type="String",
        Overwrite=True,
    )

    return {
        "status": "success",
        "message": f"IDV provider switched to {target_provider}",
    }
