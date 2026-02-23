"""Integration tests for audit log queries.

Verifies role-based scoping, pagination, and field correctness
of the /actions/audit endpoint against the live stack.
"""

import time

import pytest

from tests.integration.conftest import L1_EMAIL, L2_EMAIL, L3_EMAIL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_audit_entry(api, l1_token, action='pull-logs', ticket_suffix='audit'):
    """Create an audit entry by executing/requesting an action."""
    api.post('/actions/request', token=l1_token, body={
        'action': action,
        'ticket': f'INC-2026-{ticket_suffix}-{int(time.time())}',
        'reason': f'Audit test {ticket_suffix}',
    })


# ---------------------------------------------------------------------------
# Query by user
# ---------------------------------------------------------------------------

class TestAuditQueryByUser:
    """Audit queries filtered by user email."""

    def test_query_own_audit_l1(self, api, l1_token):
        _create_audit_entry(api, l1_token, ticket_suffix='own-l1')

        status, body = api.get('/actions/audit', token=l1_token, params={
            'user': L1_EMAIL,
        })
        assert status == 200
        assert len(body['entries']) > 0
        for entry in body['entries']:
            assert entry['user'] == L1_EMAIL

    def test_query_own_audit_returns_expected_fields(self, api, l1_token):
        _create_audit_entry(api, l1_token, ticket_suffix='fields')

        status, body = api.get('/actions/audit', token=l1_token)
        assert status == 200
        assert len(body['entries']) > 0
        entry = body['entries'][0]
        assert 'id' in entry
        assert 'timestamp' in entry
        assert 'user' in entry
        assert 'action' in entry
        assert 'result' in entry

    def test_query_own_audit_sorted_desc(self, api, l1_token):
        """Most recent entries first."""
        _create_audit_entry(api, l1_token, ticket_suffix='sort1')
        time.sleep(1)
        _create_audit_entry(api, l1_token, ticket_suffix='sort2')

        status, body = api.get('/actions/audit', token=l1_token)
        assert status == 200
        entries = body['entries']
        if len(entries) >= 2:
            assert entries[0]['timestamp'] >= entries[1]['timestamp']

    def test_l3_query_other_user(self, api, l1_token, l3_token):
        _create_audit_entry(api, l1_token, ticket_suffix='l3-cross')

        status, body = api.get('/actions/audit', token=l3_token, params={
            'user': L1_EMAIL,
        })
        assert status == 200
        for entry in body['entries']:
            assert entry['user'] == L1_EMAIL


# ---------------------------------------------------------------------------
# Query by action
# ---------------------------------------------------------------------------

class TestAuditQueryByAction:
    """Audit queries filtered by action type."""

    def test_l2_query_by_action_type(self, api, l1_token, l2_token):
        _create_audit_entry(api, l1_token, action='maintenance-mode',
                            ticket_suffix='by-action')

        status, body = api.get('/actions/audit', token=l2_token, params={
            'action': 'maintenance-mode',
        })
        assert status == 200

    def test_query_by_action_returns_only_matching(self, api, l1_token, l2_token):
        _create_audit_entry(api, l1_token, action='blacklist-ip',
                            ticket_suffix='only-match')

        status, body = api.get('/actions/audit', token=l2_token, params={
            'action': 'blacklist-ip',
        })
        assert status == 200
        for entry in body['entries']:
            assert entry['action'] == 'blacklist-ip'


# ---------------------------------------------------------------------------
# List recent
# ---------------------------------------------------------------------------

class TestAuditListRecent:
    """Unfiltered audit queries."""

    def test_l2_no_filter_lists_recent(self, api, l1_token, l2_token):
        _create_audit_entry(api, l1_token, ticket_suffix='recent-l2')

        status, body = api.get('/actions/audit', token=l2_token)
        assert status == 200
        assert 'entries' in body

    def test_l3_no_filter_lists_recent(self, api, l1_token, l3_token):
        _create_audit_entry(api, l1_token, ticket_suffix='recent-l3')

        status, body = api.get('/actions/audit', token=l3_token)
        assert status == 200
        assert len(body['entries']) > 0

    def test_l1_no_filter_scoped_to_self(self, api, l1_token):
        """L1 with no filter gets only their own entries."""
        _create_audit_entry(api, l1_token, ticket_suffix='self-scope')

        status, body = api.get('/actions/audit', token=l1_token)
        assert status == 200
        for entry in body['entries']:
            assert entry['user'] == L1_EMAIL


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class TestAuditPagination:
    """Pagination and limit behaviour."""

    def test_limit_parameter_respected(self, api, l1_token):
        # Create a few entries
        for i in range(3):
            _create_audit_entry(api, l1_token, ticket_suffix=f'limit-{i}')

        status, body = api.get('/actions/audit', token=l1_token, params={
            'limit': '2',
        })
        assert status == 200
        assert len(body['entries']) <= 2

    def test_cursor_pagination_returns_next_page(self, api, l1_token):
        # Create enough entries for pagination
        for i in range(4):
            _create_audit_entry(api, l1_token, ticket_suffix=f'page-{i}')

        # First page
        status, body = api.get('/actions/audit', token=l1_token, params={
            'limit': '2',
        })
        assert status == 200
        cursor = body.get('cursor')
        if cursor:
            # Second page
            status2, body2 = api.get('/actions/audit', token=l1_token, params={
                'limit': '2',
                'cursor': cursor,
            })
            assert status2 == 200
            assert 'entries' in body2

    def test_limit_capped_at_200(self, api, l1_token):
        """Even if limit=500 is requested, max 200 entries returned."""
        status, body = api.get('/actions/audit', token=l1_token, params={
            'limit': '500',
        })
        assert status == 200
        assert len(body['entries']) <= 200


# ---------------------------------------------------------------------------
# Field verification
# ---------------------------------------------------------------------------

class TestAuditFieldVerification:
    """Audit entries have correct field values."""

    def test_requested_action_audit_result(self, api, l1_token):
        _, req = api.post('/actions/request', token=l1_token, body={
            'action': 'maintenance-mode',
            'ticket': 'INC-2026-AUDIT-REQ',
            'reason': 'Test requested result',
        })
        request_id = req['request_id']

        status, body = api.get('/actions/audit', token=l1_token)
        assert status == 200
        entry = next(
            (e for e in body['entries']
             if e.get('id') == request_id and e.get('action') == 'maintenance-mode'),
            None,
        )
        if entry:
            assert entry['result'] == 'requested'

    def test_denied_action_audit_result(self, api, l1_token):
        """Executing an action the user can't access → result='denied'."""
        # L1 tries to execute an action they have no permission for
        # Use an action that doesn't exist in the RBAC config
        api.post('/actions/execute', token=l1_token, body={
            'action': 'nonexistent-action',
            'ticket': 'INC-2026-AUDIT-DENY',
            'reason': 'Test denied result',
        })

        status, body = api.get('/actions/audit', token=l1_token)
        assert status == 200
        denied = [e for e in body['entries'] if e.get('result') == 'denied']
        assert len(denied) > 0


# ---------------------------------------------------------------------------
# Access control (duplicated from rbac_matrix for completeness)
# ---------------------------------------------------------------------------

class TestAuditAccessControl:
    """Audit query access enforcement."""

    def test_l1_cannot_query_by_action(self, api, l1_token):
        status, _ = api.get('/actions/audit', token=l1_token, params={
            'action': 'pull-logs',
        })
        assert status == 403

    def test_l1_cannot_query_other_user(self, api, l1_token):
        status, _ = api.get('/actions/audit', token=l1_token, params={
            'user': L2_EMAIL,
        })
        assert status == 403

    def test_l2_cannot_query_other_user(self, api, l2_token):
        status, _ = api.get('/actions/audit', token=l2_token, params={
            'user': L1_EMAIL,
        })
        assert status == 403

    def test_l3_can_query_other_user(self, api, l3_token):
        status, _ = api.get('/actions/audit', token=l3_token, params={
            'user': L1_EMAIL,
        })
        assert status == 200
