"""E2E tests for activity tracking workflows.

Tests ingestion and querying of user activity events through
the real handler with DynamoDB.
"""

import time

import pytest

from tests.e2e.conftest import seed_user, call_handler

L1_EMAIL = 'l1@scotgov.uk'
L3_EMAIL = 'l3@scotgov.uk'


class TestActivityTrackingE2E:
    """Activity ingest + query workflows."""

    def test_ingest_and_query_activity(self, e2e):
        """POST /activity then GET /activity returns events."""
        seed_user(e2e['users_table'], L1_EMAIL, 'L1 User', 'L1-operator')

        now = int(time.time() * 1000)
        events = [
            {'event_type': 'page_view', 'timestamp': now, 'data': {'page': '/actions'}},
            {'event_type': 'button_click', 'timestamp': now + 1, 'data': {'button': 'execute'}},
        ]

        # Ingest
        resp = call_handler(
            e2e['handler'], '/activity', 'POST',
            body={'events': events},
            email=L1_EMAIL, groups=['L1-operator'],
        )
        assert resp['statusCode'] == 200
        assert resp['parsed_body']['ingested'] == 2

        # Query
        resp = call_handler(
            e2e['handler'], '/activity', 'GET',
            email=L1_EMAIL, groups=['L1-operator'],
        )
        assert resp['statusCode'] == 200
        returned_events = resp['parsed_body']['events']
        assert len(returned_events) == 2
        event_types = {e['event_type'] for e in returned_events}
        assert event_types == {'page_view', 'button_click'}

    def test_non_admin_queries_own_activity_only(self, e2e):
        """L1 user trying to query another user still gets own data."""
        seed_user(e2e['users_table'], L1_EMAIL, 'L1 User', 'L1-operator')
        seed_user(e2e['users_table'], L3_EMAIL, 'L3 User', 'L3-admin')

        now = int(time.time() * 1000)

        # L1 ingests events
        call_handler(
            e2e['handler'], '/activity', 'POST',
            body={'events': [
                {'event_type': 'page_view', 'timestamp': now, 'data': {'page': '/'}},
            ]},
            email=L1_EMAIL, groups=['L1-operator'],
        )

        # L3 ingests events
        call_handler(
            e2e['handler'], '/activity', 'POST',
            body={'events': [
                {'event_type': 'admin_action', 'timestamp': now + 1, 'data': {'action': 'disable'}},
            ]},
            email=L3_EMAIL, groups=['L3-admin'],
        )

        # L1 tries to query L3's activity
        resp = call_handler(
            e2e['handler'], '/activity', 'GET',
            email=L1_EMAIL, groups=['L1-operator'],
            query_params={'user': L3_EMAIL},
        )
        assert resp['statusCode'] == 200
        # Should only see L1's own events (non-admin forced to self)
        for event in resp['parsed_body']['events']:
            assert event['user'] == L1_EMAIL

    def test_admin_can_query_any_user(self, e2e):
        """L3 admin can query any user's activity."""
        seed_user(e2e['users_table'], L1_EMAIL, 'L1 User', 'L1-operator')
        seed_user(e2e['users_table'], L3_EMAIL, 'L3 User', 'L3-admin')

        now = int(time.time() * 1000)
        call_handler(
            e2e['handler'], '/activity', 'POST',
            body={'events': [
                {'event_type': 'page_view', 'timestamp': now, 'data': {'page': '/actions'}},
            ]},
            email=L1_EMAIL, groups=['L1-operator'],
        )

        # L3 queries L1's activity
        resp = call_handler(
            e2e['handler'], '/activity', 'GET',
            email=L3_EMAIL, groups=['L3-admin'],
            query_params={'user': L1_EMAIL},
        )
        assert resp['statusCode'] == 200
        events = resp['parsed_body']['events']
        assert len(events) == 1
        assert events[0]['user'] == L1_EMAIL

    def test_active_users_admin_only(self, e2e):
        """GET /activity?active=true returns active users (L3 only)."""
        seed_user(e2e['users_table'], L1_EMAIL, 'L1 User', 'L1-operator')
        seed_user(e2e['users_table'], L3_EMAIL, 'L3 User', 'L3-admin')

        now = int(time.time() * 1000)
        call_handler(
            e2e['handler'], '/activity', 'POST',
            body={'events': [
                {'event_type': 'page_view', 'timestamp': now},
            ]},
            email=L1_EMAIL, groups=['L1-operator'],
        )

        # L3 queries active users
        resp = call_handler(
            e2e['handler'], '/activity', 'GET',
            email=L3_EMAIL, groups=['L3-admin'],
            query_params={'active': 'true', 'since_minutes': '60'},
        )
        assert resp['statusCode'] == 200
        active = resp['parsed_body']['active_users']
        active_emails = [u['user'] for u in active]
        assert L1_EMAIL in active_emails

    def test_batch_cap_at_100_events(self, e2e):
        """Sending >100 events only ingests the first 100."""
        seed_user(e2e['users_table'], L1_EMAIL, 'L1 User', 'L1-operator')

        now = int(time.time() * 1000)
        events = [
            {'event_type': 'page_view', 'timestamp': now + i}
            for i in range(150)
        ]

        resp = call_handler(
            e2e['handler'], '/activity', 'POST',
            body={'events': events},
            email=L1_EMAIL, groups=['L1-operator'],
        )
        assert resp['statusCode'] == 200
        assert resp['parsed_body']['ingested'] == 100

    def test_empty_event_type_filtered(self, e2e):
        """Events with empty event_type are filtered out."""
        seed_user(e2e['users_table'], L1_EMAIL, 'L1 User', 'L1-operator')

        now = int(time.time() * 1000)
        events = [
            {'event_type': 'page_view', 'timestamp': now},
            {'event_type': '', 'timestamp': now + 1},
            {'event_type': '  ', 'timestamp': now + 2},
        ]

        resp = call_handler(
            e2e['handler'], '/activity', 'POST',
            body={'events': events},
            email=L1_EMAIL, groups=['L1-operator'],
        )
        assert resp['statusCode'] == 200
        assert resp['parsed_body']['ingested'] == 1

    def test_missing_events_array_returns_400(self, e2e):
        """POST /activity without events array returns 400."""
        seed_user(e2e['users_table'], L1_EMAIL, 'L1 User', 'L1-operator')

        resp = call_handler(
            e2e['handler'], '/activity', 'POST',
            body={'data': 'wrong'},
            email=L1_EMAIL, groups=['L1-operator'],
        )
        assert resp['statusCode'] == 400
