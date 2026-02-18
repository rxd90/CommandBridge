"""Audit logging for CommandBridge actions.

Writes and queries action execution records in DynamoDB for compliance and traceability.
"""

import boto3
import os
import time
import uuid

from shared.pagination import decimal_to_native, encode_cursor, decode_cursor

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
        'approved_by': approved_by or ''
    }

    if details:
        record['details'] = details

    _table.put_item(Item=record)
    return record


def query_by_user(user: str, limit: int = DEFAULT_LIMIT, cursor: str = None) -> dict:
    """Query audit entries by user email using the user-index GSI."""
    limit = min(int(limit), MAX_LIMIT)
    kwargs = {
        'IndexName': 'user-index',
        'KeyConditionExpression': boto3.dynamodb.conditions.Key('user').eq(user),
        'ScanIndexForward': False,
        'Limit': limit,
    }
    exclusive_start = decode_cursor(cursor)
    if exclusive_start:
        kwargs['ExclusiveStartKey'] = exclusive_start

    result = _table.query(**kwargs)
    entries = [decimal_to_native(item) for item in result.get('Items', [])]
    return {
        'entries': entries,
        'cursor': encode_cursor(result.get('LastEvaluatedKey')),
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
    exclusive_start = decode_cursor(cursor)
    if exclusive_start:
        kwargs['ExclusiveStartKey'] = exclusive_start

    result = _table.query(**kwargs)
    entries = [decimal_to_native(item) for item in result.get('Items', [])]
    return {
        'entries': entries,
        'cursor': encode_cursor(result.get('LastEvaluatedKey')),
    }


def list_recent(limit: int = DEFAULT_LIMIT, cursor: str = None) -> dict:
    """List recent audit entries (scan, newest first by timestamp)."""
    limit = min(int(limit), MAX_LIMIT)
    kwargs = {
        'Limit': limit,
    }
    exclusive_start = decode_cursor(cursor)
    if exclusive_start:
        kwargs['ExclusiveStartKey'] = exclusive_start

    result = _table.scan(**kwargs)
    entries = [decimal_to_native(item) for item in result.get('Items', [])]
    # Sort by timestamp descending (scan doesn't guarantee order)
    entries.sort(key=lambda e: e.get('timestamp', 0), reverse=True)
    return {
        'entries': entries,
        'cursor': encode_cursor(result.get('LastEvaluatedKey')),
    }
