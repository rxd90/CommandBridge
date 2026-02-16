"""Trigger secret rotation via AWS Secrets Manager."""

import boto3


def execute(body: dict) -> dict:
    """Trigger immediate rotation of a secret in Secrets Manager."""
    secret_id = body["target"]
    rotation_lambda_arn = body.get("rotation_lambda_arn")
    rotation_days = int(body.get("rotation_days", 30))

    sm = boto3.client("secretsmanager")

    if rotation_lambda_arn:
        sm.rotate_secret(
            SecretId=secret_id,
            RotationLambdaARN=rotation_lambda_arn,
            RotationRules={"AutomaticallyAfterDays": rotation_days},
        )
    else:
        sm.rotate_secret(SecretId=secret_id)

    metadata = sm.describe_secret(SecretId=secret_id)
    last_rotated = metadata.get("LastRotatedDate")

    return {
        "status": "success",
        "message": f"Rotation triggered for secret {secret_id}",
        "secret_name": metadata.get("Name"),
        "last_rotated": str(last_rotated) if last_rotated else None,
        "rotation_enabled": metadata.get("RotationEnabled", False),
    }
