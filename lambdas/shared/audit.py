"""Audit logging for CommandBridge actions.

Writes and queries action execution records in DynamoDB for compliance and traceability.
"""

import base64
import boto3
import json
import os
import time
import uuid
from decimal import Decimal

_table_name = os.environ.get('AUDIT_TABLE', 'commandbridge-dev-audit')
_dynamodb = boto3.resource('dynamodb')
_table = _dynamodb.Table(_table_name)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def log_action(
    user: str,
    action: str,
    target: str,
    ticket: str,
    result: str,
    approved_by: str = None,
    details: dict = None
) -> dict:
    """Write an audit record to DynamoDB.

    Args:
        user: Email or username of the operator.
        action: Action identifier (e.g. 'purge-cache').
        target: What was targeted (e.g. 'redis-eu-west-1').
        ticket: Incident/change ticket (e.g. 'INC-2026-0212-001').
        result: Outcome ('success', 'failed', 'requested', 'denied').
        approved_by: Who approved (if applicable).
        details: Additional context dict.

    Returns:
        The audit record dict.
    """
    record = {
        'id': str(uuid.uuid4()),
        'timestamp': int(time.time()),
        'user': user,
        'action': action,
        'target': target,
        'ticket': ticket,
        'result': result,
        'approved_by': approved_by or 'self'
    }

    if details:
        record['details'] = details

    _table.put_item(Item=record)
    return record


def _decimal_to_native(obj):
    """Convert DynamoDB Decimal types to int/float for JSON serialization."""
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_native(i) for i in obj]
    return obj


def _encode_cursor(last_key):
    """Encode DynamoDB LastEvaluatedKey as a URL-safe base64 cursor."""
    if not last_key:
        return None
    return base64.urlsafe_b64encode(json.dumps(last_key, default=str).encode()).decode()


def _decode_cursor(cursor):
    """Decode a base64 cursor back to DynamoDB ExclusiveStartKey."""
    if not cursor:
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(cursor).decode())
    except Exception:
        return None


def query_by_user(user: str, limit: int = DEFAULT_LIMIT, cursor: str = None) -> dict:
    """Query audit entries by user email using the user-index GSI."""
    limit = min(int(limit), MAX_LIMIT)
    kwargs = {
        'IndexName': 'user-index',
        'KeyConditionExpression': boto3.dynamodb.conditions.Key('user').eq(user),
        'ScanIndexForward': False,
        'Limit': limit,
    }
    exclusive_start = _decode_cursor(cursor)
    if exclusive_start:
        kwargs['ExclusiveStartKey'] = exclusive_start

    result = _table.query(**kwargs)
    entries = [_decimal_to_native(item) for item in result.get('Items', [])]
    return {
        'entries': entries,
        'cursor': _encode_cursor(result.get('LastEvaluatedKey')),
    }


def query_by_action(action: str, limit: int = DEFAULT_LIMIT, cursor: str = None) -> dict:
    """Query audit entries by action ID using the action-index GSI."""
    limit = min(int(limit), MAX_LIMIT)
    kwargs = {
        'IndexName': 'action-index',
        'KeyConditionExpression': boto3.dynamodb.conditions.Key('action').eq(action),
        'ScanIndexForward': False,
        'Limit': limit,
    }
    exclusive_start = _decode_cursor(cursor)
    if exclusive_start:
        kwargs['ExclusiveStartKey'] = exclusive_start

    result = _table.query(**kwargs)
    entries = [_decimal_to_native(item) for item in result.get('Items', [])]
    return {
        'entries': entries,
        'cursor': _encode_cursor(result.get('LastEvaluatedKey')),
    }


def list_recent(limit: int = DEFAULT_LIMIT, cursor: str = None) -> dict:
    """List recent audit entries (scan, newest first by timestamp)."""
    limit = min(int(limit), MAX_LIMIT)
    kwargs = {
        'Limit': limit,
    }
    exclusive_start = _decode_cursor(cursor)
    if exclusive_start:
        kwargs['ExclusiveStartKey'] = exclusive_start

    result = _table.scan(**kwargs)
    entries = [_decimal_to_native(item) for item in result.get('Items', [])]
    # Sort by timestamp descending (scan doesn't guarantee order)
    entries.sort(key=lambda e: e.get('timestamp', 0), reverse=True)
    return {
        'entries': entries,
        'cursor': _encode_cursor(result.get('LastEvaluatedKey')),
    }
