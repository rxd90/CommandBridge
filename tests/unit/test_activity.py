"""Activity tracking tests with moto DynamoDB mocking.

Tests lambdas/shared/activity.py - writes user interaction events to DynamoDB.
"""

import importlib
import os
import time

import boto3
import pytest
from moto import mock_aws


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    """Set up moto mock and DynamoDB table for every test."""
    with mock_aws():
        monkeypatch.setenv('ACTIVITY_TABLE', 'commandbridge-test-activity')
        dynamodb = boto3.resource('dynamodb', region_name='eu-west-2')
        table = dynamodb.create_table(
            TableName='commandbridge-test-activity',
            KeySchema=[
                {'AttributeName': 'user', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'},
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'N'},
                {'AttributeName': 'event_type', 'AttributeType': 'S'},
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'event-type-index',
                    'KeySchema': [
                        {'AttributeName': 'event_type', 'KeyType': 'HASH'},
                        {'AttributeName': 'timestamp', 'KeyType': 'RANGE'},
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                },
            ],
            BillingMode='PAY_PER_REQUEST',
        )
        import shared.activity as activity_mod
        importlib.reload(activity_mod)
        yield {'activity': activity_mod, 'table': table}


class TestLogActivity:
    def test_log_single_event(self, aws_env):
        record = aws_env['activity'].log_activity(
            user='alice@scotgov.uk',
            event_type='page_view',
            event_data={'path': '/actions', 'page': 'Actions'},
        )
        assert record['user'] == 'alice@scotgov.uk'
        assert record['event_type'] == 'page_view'
        assert 'timestamp' in record
        assert 'ttl' in record
        assert record['data']['path'] == '/actions'

    def test_ttl_is_90_days_from_now(self, aws_env):
        record = aws_env['activity'].log_activity(
            user='alice@scotgov.uk',
            event_type='page_view',
        )
        expected_ttl = int(time.time()) + (90 * 86400)
        assert abs(record['ttl'] - expected_ttl) < 5

    def test_data_optional(self, aws_env):
        record = aws_env['activity'].log_activity(
            user='alice@scotgov.uk',
            event_type='logout',
        )
        assert 'data' not in record

    def test_timestamp_is_milliseconds(self, aws_env):
        record = aws_env['activity'].log_activity(
            user='alice@scotgov.uk',
            event_type='page_view',
        )
        # Millisecond timestamps are > 1e12
        assert record['timestamp'] > 1_000_000_000_000


class TestLogActivityBatch:
    def test_batch_write(self, aws_env):
        now = int(time.time() * 1000)
        events = [
            {'user': 'alice@scotgov.uk', 'event_type': 'page_view', 'timestamp': now},
            {'user': 'alice@scotgov.uk', 'event_type': 'button_click', 'timestamp': now + 1},
            {'user': 'alice@scotgov.uk', 'event_type': 'search', 'timestamp': now + 2, 'data': {'query': 'login'}},
        ]
        count = aws_env['activity'].log_activity_batch(events)
        assert count == 3

        response = aws_env['table'].scan()
        assert response['Count'] == 3

    def test_batch_includes_ttl(self, aws_env):
        now = int(time.time() * 1000)
        events = [
            {'user': 'bob@scotgov.uk', 'event_type': 'page_view', 'timestamp': now},
        ]
        aws_env['activity'].log_activity_batch(events)
        response = aws_env['table'].scan()
        item = response['Items'][0]
        assert 'ttl' in item

    def test_batch_data_optional(self, aws_env):
        now = int(time.time() * 1000)
        events = [
            {'user': 'alice@scotgov.uk', 'event_type': 'logout', 'timestamp': now},
        ]
        aws_env['activity'].log_activity_batch(events)
        response = aws_env['table'].scan()
        item = response['Items'][0]
        assert 'data' not in item


class TestQueryUserActivity:
    def test_query_returns_events(self, aws_env):
        for i in range(3):
            aws_env['activity'].log_activity(
                user='alice@scotgov.uk',
                event_type='page_view',
            )
            time.sleep(0.001)  # ensure unique timestamps
        result = aws_env['activity'].query_user_activity('alice@scotgov.uk')
        assert len(result['events']) == 3

    def test_query_different_user_returns_empty(self, aws_env):
        aws_env['activity'].log_activity(
            user='alice@scotgov.uk',
            event_type='page_view',
        )
        result = aws_env['activity'].query_user_activity('bob@scotgov.uk')
        assert len(result['events']) == 0

    def test_query_with_limit(self, aws_env):
        for i in range(5):
            aws_env['activity'].log_activity(
                user='alice@scotgov.uk',
                event_type='page_view',
            )
            time.sleep(0.001)
        result = aws_env['activity'].query_user_activity('alice@scotgov.uk', limit=2)
        assert len(result['events']) == 2
        assert result['cursor'] is not None

    def test_query_pagination(self, aws_env):
        for i in range(5):
            aws_env['activity'].log_activity(
                user='alice@scotgov.uk',
                event_type='page_view',
            )
            time.sleep(0.001)
        page1 = aws_env['activity'].query_user_activity('alice@scotgov.uk', limit=3)
        assert len(page1['events']) == 3
        page2 = aws_env['activity'].query_user_activity('alice@scotgov.uk', limit=3, cursor=page1['cursor'])
        assert len(page2['events']) == 2


class TestQueryByEventType:
    def test_query_by_event_type(self, aws_env):
        aws_env['activity'].log_activity('alice@scotgov.uk', 'page_view')
        time.sleep(0.001)
        aws_env['activity'].log_activity('alice@scotgov.uk', 'button_click')
        time.sleep(0.001)
        aws_env['activity'].log_activity('bob@scotgov.uk', 'page_view')

        result = aws_env['activity'].query_by_event_type('page_view')
        assert len(result['events']) == 2
        assert all(e['event_type'] == 'page_view' for e in result['events'])


class TestGetActiveUsers:
    def test_returns_active_users(self, aws_env):
        aws_env['activity'].log_activity('alice@scotgov.uk', 'page_view')
        aws_env['activity'].log_activity('bob@scotgov.uk', 'page_view')

        users = aws_env['activity'].get_active_users(since_minutes=5)
        emails = [u['user'] for u in users]
        assert 'alice@scotgov.uk' in emails
        assert 'bob@scotgov.uk' in emails

    def test_deduplicates_users(self, aws_env):
        aws_env['activity'].log_activity('alice@scotgov.uk', 'page_view')
        time.sleep(0.001)
        aws_env['activity'].log_activity('alice@scotgov.uk', 'button_click')

        users = aws_env['activity'].get_active_users(since_minutes=5)
        alice_entries = [u for u in users if u['user'] == 'alice@scotgov.uk']
        assert len(alice_entries) == 1
