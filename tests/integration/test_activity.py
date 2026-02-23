"""Integration tests for activity tracking (ingest + query).

Validates event ingestion, user scoping, time range queries,
and active users against the live stack.
"""

import time

import pytest

from tests.integration.conftest import L1_EMAIL, L2_EMAIL, L3_EMAIL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ingest_events(api, token, events):
    """Ingest a batch of activity events."""
    return api.post('/activity', token=token, body={'events': events})


def _make_event(event_type='page_view', data=None):
    """Create a single activity event with current timestamp."""
    evt = {
        'event_type': event_type,
        'timestamp': int(time.time() * 1000),
    }
    if data:
        evt['data'] = data
    return evt


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

class TestActivityIngest:
    """POST /activity ingestion behaviour."""

    def test_ingest_single_event(self, api, l1_token):
        status, body = _ingest_events(api, l1_token, [
            _make_event('page_view', {'page': '/actions'}),
        ])
        assert status == 200
        assert body['ingested'] == 1

    def test_ingest_batch(self, api, l1_token):
        events = [_make_event(f'event_{i}') for i in range(5)]
        status, body = _ingest_events(api, l1_token, events)
        assert status == 200
        assert body['ingested'] == 5

    def test_ingest_server_stamps_user(self, api, l1_token, activity_table):
        """Verify the DynamoDB entry has the authenticated user email."""
        ts = int(time.time() * 1000)
        _ingest_events(api, l1_token, [
            {'event_type': 'stamp_test', 'timestamp': ts},
        ])

        # Query DDB directly to verify user field
        from boto3.dynamodb.conditions import Key
        resp = activity_table.query(
            KeyConditionExpression=Key('user').eq(L1_EMAIL)
                & Key('timestamp').eq(ts),
        )
        items = resp.get('Items', [])
        if items:
            assert items[0]['user'] == L1_EMAIL

    def test_ingest_missing_events_returns_400(self, api, l1_token):
        status, _ = api.post('/activity', token=l1_token, body={})
        assert status == 400

    def test_ingest_empty_array_returns_400(self, api, l1_token):
        status, _ = _ingest_events(api, l1_token, [])
        assert status == 400

    def test_ingest_filters_invalid_events(self, api, l1_token):
        """Mix of valid and invalid events — only valid ones ingested."""
        status, body = _ingest_events(api, l1_token, [
            _make_event('valid_event'),
            {'event_type': '', 'timestamp': int(time.time() * 1000)},
            _make_event('another_valid'),
        ])
        assert status == 200
        assert body['ingested'] == 2

    def test_ingest_caps_at_100(self, api, l1_token):
        """Batch larger than 100 is truncated."""
        events = [_make_event(f'bulk_{i}') for i in range(150)]
        status, body = _ingest_events(api, l1_token, events)
        assert status == 200
        assert body['ingested'] == 100


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

class TestActivityQuery:
    """GET /activity query behaviour."""

    def test_query_own_activity(self, api, l1_token):
        _ingest_events(api, l1_token, [_make_event('query_test')])

        status, body = api.get('/activity', token=l1_token)
        assert status == 200
        assert 'events' in body
        assert len(body['events']) > 0

    def test_query_returns_expected_fields(self, api, l1_token):
        _ingest_events(api, l1_token, [
            _make_event('field_test', {'key': 'value'}),
        ])

        status, body = api.get('/activity', token=l1_token)
        assert status == 200
        if body['events']:
            event = body['events'][0]
            assert 'user' in event
            assert 'timestamp' in event
            assert 'event_type' in event

    def test_l1_forced_to_own_activity(self, api, l1_token):
        """L1 requesting another user's activity gets own data."""
        status, body = api.get('/activity', token=l1_token, params={
            'user': L2_EMAIL,
        })
        assert status == 200
        # Events should be for L1, not L2
        for event in body.get('events', []):
            assert event['user'] == L1_EMAIL

    def test_l3_query_other_user(self, api, l1_token, l3_token):
        _ingest_events(api, l1_token, [_make_event('l3_cross_query')])

        status, body = api.get('/activity', token=l3_token, params={
            'user': L1_EMAIL,
        })
        assert status == 200

    def test_filter_by_event_type(self, api, l1_token):
        unique_type = f'filter_type_{int(time.time())}'
        _ingest_events(api, l1_token, [
            _make_event(unique_type),
            _make_event('other_type'),
        ])

        status, body = api.get('/activity', token=l1_token, params={
            'event_type': unique_type,
        })
        assert status == 200
        for event in body.get('events', []):
            assert event['event_type'] == unique_type

    def test_limit_parameter(self, api, l1_token):
        # Ingest several events
        _ingest_events(api, l1_token, [_make_event(f'limit_{i}') for i in range(5)])

        status, body = api.get('/activity', token=l1_token, params={
            'limit': '2',
        })
        assert status == 200
        assert len(body['events']) <= 2


# ---------------------------------------------------------------------------
# Time range queries
# ---------------------------------------------------------------------------

class TestActivityTimeRange:
    """Time range filtering on activity queries."""

    def test_start_time_filter(self, api, l1_token):
        now_ms = int(time.time() * 1000)
        _ingest_events(api, l1_token, [
            {'event_type': 'start_filter', 'timestamp': now_ms},
        ])

        status, body = api.get('/activity', token=l1_token, params={
            'start': str(now_ms - 5000),
        })
        assert status == 200

    def test_end_time_filter(self, api, l1_token):
        now_ms = int(time.time() * 1000)
        _ingest_events(api, l1_token, [
            {'event_type': 'end_filter', 'timestamp': now_ms},
        ])

        status, body = api.get('/activity', token=l1_token, params={
            'end': str(now_ms + 5000),
        })
        assert status == 200

    def test_start_and_end_combined(self, api, l1_token):
        now_ms = int(time.time() * 1000)
        _ingest_events(api, l1_token, [
            {'event_type': 'range_test', 'timestamp': now_ms},
        ])

        status, body = api.get('/activity', token=l1_token, params={
            'start': str(now_ms - 5000),
            'end': str(now_ms + 5000),
        })
        assert status == 200


# ---------------------------------------------------------------------------
# Active users
# ---------------------------------------------------------------------------

class TestActiveUsers:
    """Active users query (L3 only)."""

    def test_l3_get_active_users(self, api, l3_token):
        status, body = api.get('/activity', token=l3_token, params={
            'active': 'true',
        })
        assert status == 200
        assert 'active_users' in body
        assert isinstance(body['active_users'], list)

    def test_active_users_includes_recent_activity(self, api, l1_token, l3_token):
        """After ingesting activity, user appears in active list."""
        _ingest_events(api, l1_token, [_make_event('active_check')])

        status, body = api.get('/activity', token=l3_token, params={
            'active': 'true',
            'since_minutes': '5',
        })
        assert status == 200
        active_emails = [u['user'] for u in body['active_users']]
        assert L1_EMAIL in active_emails
