"""Audit logging for CommandBridge actions.

Writes and queries action execution records in DynamoDB for compliance and traceability.
"""

import boto3
import os
import time
import uuid
from datetime import datetime, timezone

from shared.pagination import decimal_to_native, encode_cursor, decode_cursor

_table_name = os.environ.get('AUDIT_TABLE', 'commandbridge-dev-audit')
_dynamodb = boto3.resource('dynamodb')
_table = _dynamodb.Table(_table_name)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _year_month(ts: int) -> str:
    """Return 'YYYY-MM' string for a Unix timestamp."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m')


def _prev_year_month(ym: str) -> str:
    """Return the previous calendar month in 'YYYY-MM' format."""
    y, m = int(ym[:4]), int(ym[5:])
    if m == 1:
        return '{:04d}-{:02d}'.format(y - 1, 12)
    return '{:04d}-{:02d}'.format(y, m - 1)


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
        result: Outcome ('success', 'failed', 'requested', 'denied', 'approved', 'approval_failed').
        approved_by: Who approved (if applicable).
        details: Additional context dict.  For 'requested' results, callers should
                 include {'request_body': <original_body>} so the record can be
                 replayed by an approver via POST /actions/approve.

    Returns:
        The audit record dict (including the generated 'id').
    """
    ts = int(time.time())
    record = {
        'id': str(uuid.uuid4()),
        'timestamp': ts,
        'year_month': _year_month(ts),
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


def get_audit_record_by_id(record_id: str) -> dict | None:
    """Look up a single audit record by its UUID.

    Uses a hash-key-only query since each UUID appears exactly once.
    """
    result = _table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('id').eq(record_id),
        Limit=1,
    )
    items = result.get('Items', [])
    if not items:
        return None
    return decimal_to_native(items[0])


def update_audit_result(record_id: str, timestamp: int, new_result: str, approved_by: str = None) -> None:
    """Update the result (and optionally approved_by) on an existing audit record.

    Args:
        record_id: UUID of the audit record (hash key).
        timestamp: Unix timestamp of the record (range key).
        new_result: New result string ('approved', 'approval_failed', etc.).
        approved_by: Email of the approver.
    """
    update_expr = 'SET #r = :r'
    expr_names = {'#r': 'result'}
    expr_values = {':r': new_result}

    if approved_by:
        update_expr += ', approved_by = :ab'
        expr_values[':ab'] = approved_by

    _table.update_item(
        Key={'id': record_id, 'timestamp': timestamp},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )


def get_pending_approvals(limit: int = DEFAULT_LIMIT) -> list:
    """Return audit records with result='requested', newest first.

    Uses a scan with filter — acceptable since the pending set is small
    (items transition out of 'requested' quickly after approval or rejection).
    """
    limit = min(int(limit), MAX_LIMIT)
    result = _table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('result').eq('requested'),
    )
    items = [decimal_to_native(item) for item in result.get('Items', [])]
    items.sort(key=lambda e: e.get('timestamp', 0), reverse=True)
    return items[:limit]


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
    """List recent audit entries using the time-index GSI, newest first.

    Queries the current calendar month's GSI partition.  If the page is not
    full and no cursor was supplied, a second query covers the previous month
    to give a complete result set near month boundaries.

    This replaces the previous full-table scan approach, which was unordered
    and increasingly expensive as the table grew.
    """
    limit = min(int(limit), MAX_LIMIT)
    now_ts = int(time.time())
    current_ym = _year_month(now_ts)
    prev_ym = _prev_year_month(current_ym)

    exclusive_start = decode_cursor(cursor)

    def _query_month(ym: str, start_key=None, page_limit: int = limit) -> tuple:
        kwargs = {
            'IndexName': 'time-index',
            'KeyConditionExpression': boto3.dynamodb.conditions.Key('year_month').eq(ym),
            'ScanIndexForward': False,
            'Limit': page_limit,
        }
        if start_key:
            kwargs['ExclusiveStartKey'] = start_key
        res = _table.query(**kwargs)
        return (
            [decimal_to_native(item) for item in res.get('Items', [])],
            res.get('LastEvaluatedKey'),
        )

    entries, last_key = _query_month(current_ym, start_key=exclusive_start)

    # Top up from previous month when at the start of the query (no caller cursor)
    if len(entries) < limit and not exclusive_start:
        needed = limit - len(entries)
        prev_entries, last_key = _query_month(prev_ym, page_limit=needed)
        entries.extend(prev_entries)

    return {
        'entries': entries,
        'cursor': encode_cursor(last_key),
    }
