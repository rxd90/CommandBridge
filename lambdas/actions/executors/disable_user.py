"""Disable a Cognito user account and mark inactive in DynamoDB."""

import os
import re

import boto3
from shared.users import update_user, get_user

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def execute(body: dict) -> dict:
    """Disable a user in the Cognito user pool to block sign-in.
    Also sets active=false in the DynamoDB users table so role lookup is denied.
    Does not delete user data - the account can be re-enabled later."""
    username = body.get("target", "").strip()
    if not username or not _EMAIL_RE.match(username):
        return {"status": "error", "message": "target must be a valid email address."}

    user_pool_id = os.environ.get("USER_POOL_ID", body.get("user_pool_id", ""))
    if not user_pool_id:
        return {"status": "error", "message": "User pool ID not configured."}

    # Verify user exists in DynamoDB before touching Cognito
    existing = get_user(username)
    if not existing:
        return {"status": "error", "message": f"User {username} not found."}

    cognito = boto3.client("cognito-idp", region_name=os.environ.get("AWS_REGION", "eu-west-2"))
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
