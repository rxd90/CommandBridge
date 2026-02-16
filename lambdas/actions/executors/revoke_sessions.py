"""Revoke all active sessions for a Cognito user."""

import boto3


def execute(body: dict) -> dict:
    """Force sign-out a user by revoking all tokens and global sign-out."""
    username = body["target"]
    user_pool_id = body.get("user_pool_id", "eu-west-2_quMz1HdKl")

    cognito = boto3.client("cognito-idp", region_name="eu-west-2")
    cognito.admin_user_global_sign_out(
        UserPoolId=user_pool_id,
        Username=username,
    )

    return {
        "status": "success",
        "message": f"All sessions revoked for user {username}",
    }
