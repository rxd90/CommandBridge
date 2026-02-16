"""Disable a Cognito user account and mark inactive in DynamoDB."""

import boto3
from shared.users import update_user


def execute(body: dict) -> dict:
    """Disable a user in the Cognito user pool to block sign-in.
    Also sets active=false in the DynamoDB users table so role lookup is denied.
    Does not delete user data — the account can be re-enabled later."""
    username = body["target"]
    user_pool_id = body.get("user_pool_id", "eu-west-2_quMz1HdKl")

    cognito = boto3.client("cognito-idp", region_name="eu-west-2")
    cognito.admin_disable_user(
        UserPoolId=user_pool_id,
        Username=username,
    )

    # Sync authz state: mark user inactive in DynamoDB
    update_user(username, {'active': False}, 'executor:disable-user')

    return {
        "status": "success",
        "message": f"User {username} disabled. Sign-in blocked pending investigation.",
    }
