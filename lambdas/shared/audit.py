"""Audit logging for CommandBridge actions.

Writes action execution records to DynamoDB for compliance and traceability.
"""

import boto3
import os
import time
import uuid

_table_name = os.environ.get('AUDIT_TABLE', 'commandbridge-dev-audit')
_dynamodb = boto3.resource('dynamodb')
_table = _dynamodb.Table(_table_name)


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
