"""User activity tracking for CommandBridge.

Writes and queries user interaction events (page views, clicks, searches)
in DynamoDB. Records auto-expire after 90 days via TTL.
"""

import boto3
import os
import time

from shared.pagination import decimal_to_native, encode_cursor, decode_cursor

_table_name = os.environ.get('ACTIVITY_TABLE', 'commandbridge-dev-activity')
_dynamodb = boto3.resource('dynamodb')
_table = _dynamodb.Table(_table_name)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
TTL_DAYS = 90


def log_activity(user: str, event_type: str, event_data: dict = None) -> dict:
    """Write a single activity event to DynamoDB.

    Args:
        user: Email of the user.
        event_type: Event category (e.g. 'page_view', 'button_click').
        event_data: Additional context dict (page, action, query, etc.).

    Returns:
        The activity record dict.
    """
    now = int(time.time() * 1000)
    record = {
        'user': user,
        'timestamp': now,
        'event_type': event_type,
        'ttl': int(time.time()) + (TTL_DAYS * 86400),
    }
    if event_data:
        record['data'] = event_data

    _table.put_item(Item=record)
    return record


def log_activity_batch(events: list) -> int:
    """Write a batch of activity events to DynamoDB.

    Args:
        events: List of dicts, each with 'user', 'event_type',
                'timestamp' (ms epoch), and optional 'data'.

    Returns:
        Number of events written.
    """
    now_seconds = int(time.time())
    ttl_value = now_seconds + (TTL_DAYS * 86400)

    # Deduplicate keys: if multiple events share the same user+timestamp,
    # offset subsequent ones by 1ms to avoid BatchWriteItem duplicate key errors.
    seen_keys = set()
    with _table.batch_writer() as batch:
        for event in events:
            ts = event['timestamp']
            key = (event['user'], ts)
            while key in seen_keys:
                ts += 1
                key = (event['user'], ts)
            seen_keys.add(key)

            item = {
                'user': event['user'],
                'timestamp': ts,
                'event_type': event['event_type'],
                'ttl': ttl_value,
            }
            if event.get('data'):
                item['data'] = event['data']
            batch.put_item(Item=item)

    return len(events)


def query_user_activity(
    user: str,
    start_time: int = None,
    end_time: int = None,
    event_type: str = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str = None,
) -> dict:
    """Query activity events for a specific user.

    Args:
        user: User email.
        start_time: Start timestamp in milliseconds (inclusive).
        end_time: End timestamp in milliseconds (inclusive).
        event_type: Optional filter by event_type (post-query filter).
        limit: Max results.
        cursor: Pagination cursor.

    Returns:
        Dict with 'events' list and 'cursor' string.
    """
    limit = min(int(limit), MAX_LIMIT)
    Key = boto3.dynamodb.conditions.Key

    key_condition = Key('user').eq(user)
    if start_time and end_time:
        key_condition = key_condition & Key('timestamp').between(start_time, end_time)
    elif start_time:
        key_condition = key_condition & Key('timestamp').gte(start_time)
    elif end_time:
        key_condition = key_condition & Key('timestamp').lte(end_time)

    kwargs = {
        'KeyConditionExpression': key_condition,
        'ScanIndexForward': False,
        'Limit': limit,
    }

    if event_type:
        kwargs['FilterExpression'] = boto3.dynamodb.conditions.Attr('event_type').eq(event_type)

    exclusive_start = decode_cursor(cursor)
    if exclusive_start:
        kwargs['ExclusiveStartKey'] = exclusive_start

    result = _table.query(**kwargs)
    events = [decimal_to_native(item) for item in result.get('Items', [])]
    return {
        'events': events,
        'cursor': encode_cursor(result.get('LastEvaluatedKey')),
    }


def query_by_event_type(
    event_type: str,
    start_time: int = None,
    end_time: int = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str = None,
) -> dict:
    """Query activity events by event_type using the GSI.

    Args:
        event_type: Event type string.
        start_time: Start timestamp in milliseconds (inclusive).
        end_time: End timestamp in milliseconds (inclusive).
        limit: Max results.
        cursor: Pagination cursor.

    Returns:
        Dict with 'events' list and 'cursor' string.
    """
    limit = min(int(limit), MAX_LIMIT)
    Key = boto3.dynamodb.conditions.Key

    key_condition = Key('event_type').eq(event_type)
    if start_time and end_time:
        key_condition = key_condition & Key('timestamp').between(start_time, end_time)
    elif start_time:
        key_condition = key_condition & Key('timestamp').gte(start_time)
    elif end_time:
        key_condition = key_condition & Key('timestamp').lte(end_time)

    kwargs = {
        'IndexName': 'event-type-index',
        'KeyConditionExpression': key_condition,
        'ScanIndexForward': False,
        'Limit': limit,
    }
    exclusive_start = decode_cursor(cursor)
    if exclusive_start:
        kwargs['ExclusiveStartKey'] = exclusive_start

    result = _table.query(**kwargs)
    events = [decimal_to_native(item) for item in result.get('Items', [])]
    return {
        'events': events,
        'cursor': encode_cursor(result.get('LastEvaluatedKey')),
    }


def get_active_users(since_minutes: int = 15) -> list:
    """Get users who have activity within the last N minutes.

    Uses a Scan with filter - acceptable for ~50 users and low volume.

    Returns:
        List of dicts with 'user' and 'last_seen' (timestamp).
    """
    cutoff = int((time.time() - since_minutes * 60) * 1000)
    result = _table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('timestamp').gte(cutoff),
        ProjectionExpression='#u, #ts',
        ExpressionAttributeNames={'#u': 'user', '#ts': 'timestamp'},
    )

    user_map = {}
    for item in result.get('Items', []):
        user = item['user']
        ts = int(item['timestamp'])
        if user not in user_map or ts > user_map[user]:
            user_map[user] = ts

    return [
        {'user': u, 'last_seen': decimal_to_native(ts)}
        for u, ts in sorted(user_map.items(), key=lambda x: x[1], reverse=True)
    ]
