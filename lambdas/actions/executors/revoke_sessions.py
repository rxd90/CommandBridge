"""Revoke all active sessions for a Cognito user."""

import os
import re

import boto3

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def execute(body: dict) -> dict:
    """Force sign-out a user by revoking all tokens and global sign-out."""
    username = body.get("target", "").strip()
    if not username or not _EMAIL_RE.match(username):
        return {"status": "error", "message": "target must be a valid email address."}

    user_pool_id = os.environ.get("USER_POOL_ID", body.get("user_pool_id", ""))
    if not user_pool_id:
        return {"status": "error", "message": "User pool ID not configured."}

    cognito = boto3.client("cognito-idp", region_name=os.environ.get("AWS_REGION", "eu-west-2"))
    cognito.admin_user_global_sign_out(
        UserPoolId=user_pool_id,
        Username=username,
    )

    return {
        "status": "success",
        "message": f"All sessions revoked for user {username}",
    }
