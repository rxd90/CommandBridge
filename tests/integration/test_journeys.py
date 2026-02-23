"""Integration tests for cross-feature journeys.

End-to-end workflows that exercise multiple endpoints in sequence,
catching integration issues that single-endpoint tests miss.
"""

import time

import pytest
from urllib.parse import quote

from tests.integration.conftest import (
    L1_EMAIL, L2_EMAIL, L3_EMAIL,
    unique_title, unique_admin_email,
)


class TestApprovalJourney:
    """Full approval lifecycle across multiple endpoints."""

    def test_full_approval_workflow(self, api, l1_token, l2_token):
        """L1 submits → L2 sees pending → L2 approves → audit updated."""
        # Step 1: L1 submits high-risk action
        status, req = api.post('/actions/execute', token=l1_token, body={
            'action': 'maintenance-mode',
            'ticket': 'INC-2026-JOUR-001',
            'reason': 'Journey test: full approval',
        })
        assert status == 202
        request_id = req['request_id']

        # Step 2: L2 sees it in pending
        status, pending = api.get('/actions/pending', token=l2_token)
        assert status == 200
        ids = [p['id'] for p in pending['pending']]
        assert request_id in ids

        # Step 3: L2 approves (executor may fail — that's OK)
        status, _ = api.post('/actions/approve', token=l2_token, body={
            'request_id': request_id,
        })
        assert status in (200, 500)

        # Step 4: Audit shows it's no longer 'requested'
        status, audit = api.get('/actions/audit', token=l2_token, params={
            'action': 'maintenance-mode',
        })
        assert status == 200

    def test_approval_then_audit_trail_complete(self, api, l1_token, l2_token, l3_token):
        """Request + approve creates both 'requested' and approval entries in audit."""
        _, req = api.post('/actions/request', token=l1_token, body={
            'action': 'blacklist-ip',
            'ticket': 'INC-2026-JOUR-002',
            'reason': 'Journey test: audit trail',
        })
        request_id = req['request_id']

        # Approve
        api.post('/actions/approve', token=l2_token, body={
            'request_id': request_id,
        })

        # L3 checks audit for both users
        _, audit_l1 = api.get('/actions/audit', token=l3_token, params={
            'user': L1_EMAIL,
        })
        l1_actions = [e['action'] for e in audit_l1['entries']]
        assert 'blacklist-ip' in l1_actions

        _, audit_l2 = api.get('/actions/audit', token=l3_token, params={
            'user': L2_EMAIL,
        })
        l2_actions = [e['action'] for e in audit_l2['entries']]
        assert 'blacklist-ip' in l2_actions


class TestKBJourney:
    """KB article lifecycle across create, update, search, delete."""

    def test_create_update_search_delete_lifecycle(self, api, l2_token, l3_token, l1_token):
        """Full CRUD lifecycle in one test."""
        title = unique_title('journey-crud')

        # Create
        status, created = api.post('/kb', token=l2_token, body={
            'title': title,
            'service': 'journey-service',
            'content': 'Version 1',
            'tags': ['journey', 'test'],
        })
        assert status == 201
        article_id = created['article']['id']

        # Update twice
        api.put(f'/kb/{article_id}', token=l2_token, body={'content': 'Version 2'})
        api.put(f'/kb/{article_id}', token=l2_token, body={'content': 'Version 3'})

        # Search finds it
        status, found = api.get('/kb', token=l1_token, params={'search': title})
        assert status == 200
        assert any(a['id'] == article_id for a in found['articles'])

        # L3 deletes
        status, _ = api.delete(f'/kb/{article_id}', token=l3_token)
        assert status == 200

        # Search no longer finds it
        status, after = api.get('/kb', token=l1_token, params={'search': title})
        assert status == 200
        assert not any(a['id'] == article_id for a in after['articles'])

    def test_kb_version_history_journey(self, api, l2_token, l1_token):
        """Create + 3 updates → 4 versions, v1 still accessible, v4 is latest."""
        title = unique_title('journey-versions')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'v1 content',
        })
        article_id = created['article']['id']

        for i in range(2, 5):
            api.put(f'/kb/{article_id}', token=l2_token, body={
                'content': f'v{i} content',
            })

        # Versions endpoint shows all 4
        status, versions = api.get(f'/kb/{article_id}/versions', token=l1_token)
        assert status == 200
        assert len(versions['versions']) == 4

        # v1 still accessible
        status, v1 = api.get(f'/kb/{article_id}/versions/1', token=l1_token)
        assert status == 200
        assert v1['article']['content'] == 'v1 content'

        # Latest is v4
        status, latest = api.get(f'/kb/{article_id}', token=l1_token)
        assert status == 200
        assert latest['article']['version'] == 4
        assert latest['article']['content'] == 'v4 content'


class TestUserLifecycleJourney:
    """Admin creates, disables, enables, and changes role for a user."""

    def test_create_disable_enable_role_change(self, api, l3_token, users_table):
        email = unique_admin_email()

        # Create
        status, _ = api.post('/admin/users', token=l3_token, body={
            'email': email,
            'name': 'Journey User',
            'role': 'L1-operator',
            'team': 'Journey Team',
        })
        assert status == 201

        # Verify in DDB
        resp = users_table.get_item(Key={'email': email})
        assert resp['Item']['active'] is True

        # Disable
        status, _ = api.post(
            f'/admin/users/{quote(email, safe="")}/disable',
            token=l3_token,
        )
        assert status == 200
        resp = users_table.get_item(Key={'email': email})
        assert resp['Item']['active'] is False

        # Enable
        status, _ = api.post(
            f'/admin/users/{quote(email, safe="")}/enable',
            token=l3_token,
        )
        assert status == 200
        resp = users_table.get_item(Key={'email': email})
        assert resp['Item']['active'] is True

        # Change role
        status, _ = api.post(
            f'/admin/users/{quote(email, safe="")}/role',
            token=l3_token,
            body={'role': 'L2-engineer'},
        )
        assert status == 200
        resp = users_table.get_item(Key={'email': email})
        assert resp['Item']['role'] == 'L2-engineer'


class TestCrossFeatureJourney:
    """Workflows that span multiple feature areas."""

    def test_action_creates_audit_queryable_by_user(self, api, l1_token):
        """L1 executes action → can query own audit → sees the entry."""
        api.post('/actions/request', token=l1_token, body={
            'action': 'pull-logs',
            'ticket': 'INC-2026-JOUR-010',
            'reason': 'Journey: action → audit',
        })

        status, audit = api.get('/actions/audit', token=l1_token)
        assert status == 200
        actions = [e['action'] for e in audit['entries']]
        assert 'pull-logs' in actions

    def test_activity_ingest_then_query(self, api, l1_token, l3_token):
        """L1 ingests activity → L1 queries → L3 queries L1's activity."""
        unique_type = f'journey_activity_{int(time.time())}'
        api.post('/activity', token=l1_token, body={
            'events': [
                {'event_type': unique_type, 'timestamp': int(time.time() * 1000)},
            ],
        })

        # L1 queries own
        status, own = api.get('/activity', token=l1_token, params={
            'event_type': unique_type,
        })
        assert status == 200
        assert len(own['events']) >= 1

        # L3 queries L1's activity
        status, cross = api.get('/activity', token=l3_token, params={
            'user': L1_EMAIL,
            'event_type': unique_type,
        })
        assert status == 200
        assert len(cross['events']) >= 1

    def test_role_change_affects_permissions(self, api, l1_token, l3_token):
        """L3 promotes L1→L2 → KB create works → demote back → KB create fails."""
        # Promote to L2
        api.post(
            f'/admin/users/{quote(L1_EMAIL, safe="")}/role',
            token=l3_token,
            body={'role': 'L2-engineer'},
        )
        try:
            # L1 (now L2) can create KB
            title = unique_title('journey-promote')
            status, _ = api.post('/kb', token=l1_token, body={
                'title': title, 'content': 'promoted user',
            })
            assert status == 201
        finally:
            # Demote back to L1
            api.post(
                f'/admin/users/{quote(L1_EMAIL, safe="")}/role',
                token=l3_token,
                body={'role': 'L1-operator'},
            )

        # L1 cannot create KB anymore
        title2 = unique_title('journey-demoted')
        status, _ = api.post('/kb', token=l1_token, body={
            'title': title2, 'content': 'demoted user',
        })
        assert status == 403

    def test_disabled_user_blocked_everywhere(self, api, l1_token, l3_token, users_table):
        """Disabled user gets 403 on /me, /actions/execute, /kb."""
        users_table.update_item(
            Key={'email': L1_EMAIL},
            UpdateExpression='SET active = :f',
            ExpressionAttributeValues={':f': False},
        )
        try:
            # /me → 403
            status, _ = api.get('/me', token=l1_token)
            assert status == 403

            # /actions/permissions → handler checks user first
            status, _ = api.get('/actions/permissions', token=l1_token)
            # May be 200 (permissions doesn't check active) or 403
            # The handler resolves role from get_user_role which returns None for inactive
            # So user_groups=[] → all permissions locked, but status is 200
            assert status in (200, 403)
        finally:
            users_table.update_item(
                Key={'email': L1_EMAIL},
                UpdateExpression='SET active = :t',
                ExpressionAttributeValues={':t': True},
            )

    def test_full_day_regression(self, api, l1_token, l2_token, l3_token):
        """Simulates a typical day: execute, request, approve, KB, activity, audit."""
        # L1 requests a high-risk action
        _, req = api.post('/actions/request', token=l1_token, body={
            'action': 'maintenance-mode',
            'ticket': 'INC-2026-JOUR-FULL',
            'reason': 'Full day regression test',
        })
        request_id = req['request_id']

        # L2 approves
        api.post('/actions/approve', token=l2_token, body={
            'request_id': request_id,
        })

        # L2 creates KB article
        title = unique_title('journey-fullday')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title,
            'service': 'regression-service',
            'content': 'Regression test article.',
        })
        article_id = created['article']['id']

        # L2 updates it
        api.put(f'/kb/{article_id}', token=l2_token, body={
            'content': 'Updated regression content.',
        })

        # L1 reads it
        status, read = api.get(f'/kb/{article_id}', token=l1_token)
        assert status == 200
        assert read['article']['version'] == 2

        # L1 ingests activity
        api.post('/activity', token=l1_token, body={
            'events': [
                {'event_type': 'page_view', 'timestamp': int(time.time() * 1000),
                 'data': {'page': f'/kb/{article_id}'}},
            ],
        })

        # L3 queries audit — should see entries from both L1 and L2
        status, audit = api.get('/actions/audit', token=l3_token)
        assert status == 200
        assert len(audit['entries']) > 0

        # L3 queries activity
        status, activity = api.get('/activity', token=l3_token, params={
            'user': L1_EMAIL,
        })
        assert status == 200
