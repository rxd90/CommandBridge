"""Integration tests for input validation across all endpoints.

Verifies that the live API correctly rejects malformed requests
with appropriate 400 status codes.
"""

import pytest

from tests.integration.conftest import L1_EMAIL, L2_EMAIL, L3_EMAIL, unique_title


# ---------------------------------------------------------------------------
# /actions/execute validation
# ---------------------------------------------------------------------------

class TestExecuteValidation:
    """POST /actions/execute rejects bad inputs."""

    def test_missing_action_returns_400(self, api, l1_token):
        status, body = api.post('/actions/execute', token=l1_token, body={
            'ticket': 'INC-2026-001', 'reason': 'test',
        })
        assert status == 400
        assert 'required' in body['message'].lower()

    def test_missing_ticket_returns_400(self, api, l1_token):
        status, body = api.post('/actions/execute', token=l1_token, body={
            'action': 'pull-logs', 'reason': 'test',
        })
        assert status == 400
        assert 'required' in body['message'].lower()

    def test_missing_reason_returns_400(self, api, l1_token):
        status, body = api.post('/actions/execute', token=l1_token, body={
            'action': 'pull-logs', 'ticket': 'INC-2026-001',
        })
        assert status == 400
        assert 'required' in body['message'].lower()

    def test_invalid_ticket_format_returns_400(self, api, l1_token):
        status, body = api.post('/actions/execute', token=l1_token, body={
            'action': 'pull-logs', 'ticket': 'BADFORMAT', 'reason': 'test',
        })
        assert status == 400
        assert 'ticket' in body['message'].lower()

    def test_ticket_inc_format_accepted(self, api, l1_token, test_log_group):
        """INC-prefixed tickets pass validation (may fail at executor level)."""
        status, _ = api.post('/actions/execute', token=l1_token, body={
            'action': 'pull-logs', 'ticket': 'INC-2026-001',
            'reason': 'test', 'target': 'commandbridge-integration',
        })
        # 200 or 500 (executor may fail) — but NOT 400 for ticket format
        assert status != 400

    def test_ticket_chg_format_accepted(self, api, l1_token, test_log_group):
        """CHG-prefixed tickets pass validation."""
        status, _ = api.post('/actions/execute', token=l1_token, body={
            'action': 'pull-logs', 'ticket': 'CHG-2026-001',
            'reason': 'test', 'target': 'commandbridge-integration',
        })
        assert status != 400

    def test_empty_body_returns_400(self, api, l1_token):
        status, body = api.post('/actions/execute', token=l1_token)
        assert status == 400

    def test_invalid_json_body_returns_400(self, api, l1_token):
        status, _ = api.post('/actions/execute', token=l1_token,
                             raw_body='not valid json{{{')
        assert status == 400


# ---------------------------------------------------------------------------
# /actions/request validation
# ---------------------------------------------------------------------------

class TestRequestValidation:
    """POST /actions/request rejects bad inputs."""

    def test_missing_fields_returns_400(self, api, l1_token):
        status, body = api.post('/actions/request', token=l1_token, body={
            'action': 'maintenance-mode',
        })
        assert status == 400
        assert 'required' in body['message'].lower()

    def test_invalid_ticket_returns_400(self, api, l1_token):
        status, body = api.post('/actions/request', token=l1_token, body={
            'action': 'maintenance-mode', 'ticket': 'NOPE', 'reason': 'test',
        })
        assert status == 400
        assert 'ticket' in body['message'].lower()


# ---------------------------------------------------------------------------
# /actions/approve validation
# ---------------------------------------------------------------------------

class TestApproveValidation:
    """POST /actions/approve rejects bad inputs."""

    def test_missing_request_id_returns_400(self, api, l2_token):
        status, body = api.post('/actions/approve', token=l2_token, body={})
        assert status == 400
        assert 'request_id' in body['message'].lower()

    def test_invalid_request_id_returns_404(self, api, l2_token):
        import uuid
        status, _ = api.post('/actions/approve', token=l2_token, body={
            'request_id': str(uuid.uuid4()),
        })
        assert status == 404


# ---------------------------------------------------------------------------
# KB validation
# ---------------------------------------------------------------------------

class TestKBValidation:
    """KB create/update rejects bad inputs."""

    def test_create_no_body_returns_400(self, api, l2_token):
        status, _ = api.post('/kb', token=l2_token)
        assert status == 400

    def test_create_empty_title_returns_400(self, api, l2_token):
        status, body = api.post('/kb', token=l2_token, body={
            'title': '', 'content': 'some content',
        })
        assert status == 400
        assert 'title' in body['message'].lower()

    def test_update_no_body_returns_400(self, api, l2_token):
        status, _ = api.put('/kb/nonexistent-article', token=l2_token)
        assert status == 400


# ---------------------------------------------------------------------------
# Admin validation
# ---------------------------------------------------------------------------

class TestAdminValidation:
    """Admin user creation/role change rejects bad inputs."""

    def test_create_user_empty_email_returns_400(self, api, l3_token):
        status, _ = api.post('/admin/users', token=l3_token, body={
            'email': '', 'name': 'Test', 'role': 'L1-operator', 'team': 'Test',
        })
        assert status == 400

    def test_create_user_email_no_domain_returns_400(self, api, l3_token):
        status, _ = api.post('/admin/users', token=l3_token, body={
            'email': 'user@', 'name': 'Test', 'role': 'L1-operator', 'team': 'Test',
        })
        assert status == 400

    def test_set_role_no_body_returns_400(self, api, l3_token):
        from urllib.parse import quote
        status, _ = api.post(
            f'/admin/users/{quote(L1_EMAIL, safe="")}/role',
            token=l3_token,
        )
        assert status == 400

    def test_set_role_missing_role_returns_400(self, api, l3_token):
        from urllib.parse import quote
        status, body = api.post(
            f'/admin/users/{quote(L1_EMAIL, safe="")}/role',
            token=l3_token,
            body={},
        )
        assert status == 400
        assert 'role' in body['message'].lower()


# ---------------------------------------------------------------------------
# Activity validation
# ---------------------------------------------------------------------------

class TestActivityValidation:
    """Activity ingestion rejects bad inputs."""

    def test_ingest_non_array_events_returns_400(self, api, l1_token):
        status, _ = api.post('/activity', token=l1_token, body={
            'events': 'not an array',
        })
        assert status == 400

    def test_ingest_no_valid_event_types_returns_400(self, api, l1_token):
        status, _ = api.post('/activity', token=l1_token, body={
            'events': [{'event_type': ''}],
        })
        assert status == 400

    def test_query_invalid_start_returns_400(self, api, l1_token):
        status, _ = api.get('/activity', token=l1_token, params={
            'start': 'not-a-number',
        })
        assert status == 400
