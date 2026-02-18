"""DynamoDB-backed user management for CommandBridge.

Source of truth for authorization: roles, team, active status.
Cognito handles authentication only (login, tokens, MFA).
"""

import os
import boto3
from datetime import datetime, timezone

_table_name = os.environ.get('USERS_TABLE', 'commandbridge-dev-users')
_dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'eu-west-2'))
_table = _dynamodb.Table(_table_name)

VALID_ROLES = {'L1-operator', 'L2-engineer', 'L3-admin'}


def get_user(email: str) -> dict | None:
    """Get a user record by email."""
    resp = _table.get_item(Key={'email': email})
    item = resp.get('Item')
    if not item:
        return None
    # Convert DynamoDB bool to Python bool
    item['active'] = bool(item.get('active', True))
    return item


def get_user_role(email: str) -> str | None:
    """Get just the role for a user. Returns None if user not found or inactive."""
    user = get_user(email)
    if not user or not user.get('active', True):
        return None
    return user.get('role')


def list_users() -> list[dict]:
    """List all users."""
    resp = _table.scan()
    users = resp.get('Items', [])
    for u in users:
        u['active'] = bool(u.get('active', True))
    return users


def update_user(email: str, fields: dict, updated_by: str) -> dict | None:
    """Update specific fields on a user record.

    Args:
        email: User email (primary key).
        fields: Dict of field names to new values.
        updated_by: Email of admin making the change.

    Returns:
        Updated user record, or None if user not found.
    """
    user = get_user(email)
    if not user:
        return None

    fields['updated_at'] = datetime.now(timezone.utc).isoformat()
    fields['updated_by'] = updated_by

    update_parts = []
    values = {}
    names = {}
    for i, (key, val) in enumerate(fields.items()):
        attr = f'#k{i}'
        placeholder = f':v{i}'
        update_parts.append(f'{attr} = {placeholder}')
        values[placeholder] = val
        names[attr] = key

    _table.update_item(
        Key={'email': email},
        UpdateExpression='SET ' + ', '.join(update_parts),
        ExpressionAttributeValues=values,
        ExpressionAttributeNames=names,
    )

    return get_user(email)


def create_user(email: str, name: str, role: str, team: str, created_by: str) -> dict:
    """Create a new user record."""
    now = datetime.now(timezone.utc).isoformat()
    item = {
        'email': email,
        'name': name,
        'role': role,
        'team': team,
        'active': True,
        'created_at': now,
        'updated_at': now,
        'updated_by': created_by,
    }
    _table.put_item(Item=item)
    return item
