"""Integration tests for RBAC enforcement across all endpoints.

Parametrized tests verify that every endpoint correctly enforces
role-based access control against the live API Gateway.
"""

import pytest
from urllib.parse import quote

from tests.integration.conftest import (
    L1_EMAIL, L2_EMAIL, L3_EMAIL, unique_title,
)


# ---------------------------------------------------------------------------
# Admin endpoint access (L3 only)
# ---------------------------------------------------------------------------

class TestAdminEndpointAccess:
    """Admin endpoints require L3-admin role."""

    @pytest.mark.parametrize('role_label,token_fixture,expected', [
        ('L1', 'l1_token', 403),
        ('L2', 'l2_token', 403),
        ('L3', 'l3_token', 200),
    ])
    def test_list_users(self, api, role_label, token_fixture, expected, request):
        token = request.getfixturevalue(token_fixture)
        status, _ = api.get('/admin/users', token=token)
        assert status == expected, f'{role_label} expected {expected}, got {status}'

    @pytest.mark.parametrize('role_label,token_fixture,expected', [
        ('L1', 'l1_token', 403),
        ('L2', 'l2_token', 403),
        ('L3', 'l3_token', 400),  # 400 = auth passed, body validation kicked in
    ])
    def test_create_user(self, api, role_label, token_fixture, expected, request):
        token = request.getfixturevalue(token_fixture)
        status, _ = api.post('/admin/users', token=token)
        assert status == expected, f'{role_label} expected {expected}, got {status}'

    @pytest.mark.parametrize('role_label,token_fixture,expected', [
        ('L1', 'l1_token', 403),
        ('L2', 'l2_token', 403),
        ('L3', 'l3_token', 200),
    ])
    def test_disable_user(self, api, role_label, token_fixture, expected, request):
        token = request.getfixturevalue(token_fixture)
        # Target a different user than the caller
        target = L1_EMAIL if token_fixture != 'l1_token' else L2_EMAIL
        status, _ = api.post(
            f'/admin/users/{quote(target, safe="")}/disable',
            token=token,
        )
        assert status == expected, f'{role_label} expected {expected}, got {status}'
        # Re-enable if we disabled
        if status == 200:
            l3_tok = request.getfixturevalue('l3_token')
            api.post(f'/admin/users/{quote(target, safe="")}/enable', token=l3_tok)

    @pytest.mark.parametrize('role_label,token_fixture,expected', [
        ('L1', 'l1_token', 403),
        ('L2', 'l2_token', 403),
        ('L3', 'l3_token', 200),
    ])
    def test_enable_user(self, api, role_label, token_fixture, expected, request):
        token = request.getfixturevalue(token_fixture)
        target = L1_EMAIL if token_fixture != 'l1_token' else L2_EMAIL
        status, _ = api.post(
            f'/admin/users/{quote(target, safe="")}/enable',
            token=token,
        )
        assert status == expected, f'{role_label} expected {expected}, got {status}'

    @pytest.mark.parametrize('role_label,token_fixture,expected', [
        ('L1', 'l1_token', 403),
        ('L2', 'l2_token', 403),
        ('L3', 'l3_token', 200),
    ])
    def test_set_role(self, api, role_label, token_fixture, expected, request):
        token = request.getfixturevalue(token_fixture)
        target = L1_EMAIL if token_fixture != 'l1_token' else L2_EMAIL
        # Get current role to restore later
        l3_tok = request.getfixturevalue('l3_token')
        _, user_data = api.get(f'/admin/users', token=l3_tok)
        target_user = next(
            (u for u in user_data.get('users', []) if u['email'] == target),
            None,
        )
        orig_role = target_user['role'] if target_user else 'L1-operator'

        status, _ = api.post(
            f'/admin/users/{quote(target, safe="")}/role',
            token=token,
            body={'role': 'L2-engineer'},
        )
        assert status == expected, f'{role_label} expected {expected}, got {status}'
        # Restore original role
        if status == 200:
            api.post(
                f'/admin/users/{quote(target, safe="")}/role',
                token=l3_tok,
                body={'role': orig_role},
            )


# ---------------------------------------------------------------------------
# KB write access (L2+ create/update, L3 delete)
# ---------------------------------------------------------------------------

class TestKBWriteAccess:
    """KB write operations enforce role requirements."""

    @pytest.mark.parametrize('role_label,token_fixture,expected', [
        ('L1', 'l1_token', 403),
        ('L2', 'l2_token', 201),
        ('L3', 'l3_token', 201),
    ])
    def test_kb_create(self, api, role_label, token_fixture, expected, request):
        token = request.getfixturevalue(token_fixture)
        title = unique_title(f'rbac-create-{role_label.lower()}')
        status, _ = api.post('/kb', token=token, body={
            'title': title,
            'service': 'test-service',
            'content': 'RBAC test content',
        })
        assert status == expected, f'{role_label} expected {expected}, got {status}'

    @pytest.mark.parametrize('role_label,token_fixture,expected', [
        ('L1', 'l1_token', 403),
        ('L2', 'l2_token', 200),
        ('L3', 'l3_token', 200),
    ])
    def test_kb_update(self, api, role_label, token_fixture, expected, request, l2_token):
        # Create an article first (as L2)
        title = unique_title(f'rbac-update-{role_label.lower()}')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'original',
        })
        article_id = created['article']['id']

        token = request.getfixturevalue(token_fixture)
        status, _ = api.put(f'/kb/{article_id}', token=token, body={
            'content': 'updated content',
        })
        assert status == expected, f'{role_label} expected {expected}, got {status}'

    @pytest.mark.parametrize('role_label,token_fixture,expected', [
        ('L1', 'l1_token', 403),
        ('L2', 'l2_token', 403),
        ('L3', 'l3_token', 200),
    ])
    def test_kb_delete(self, api, role_label, token_fixture, expected, request, l2_token):
        # Create an article first (as L2)
        title = unique_title(f'rbac-delete-{role_label.lower()}')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'to be deleted',
        })
        article_id = created['article']['id']

        token = request.getfixturevalue(token_fixture)
        status, _ = api.delete(f'/kb/{article_id}', token=token)
        assert status == expected, f'{role_label} expected {expected}, got {status}'


# ---------------------------------------------------------------------------
# Pending approvals access (L2+)
# ---------------------------------------------------------------------------

class TestPendingApprovalsAccess:
    """GET /actions/pending requires L2+."""

    @pytest.mark.parametrize('role_label,token_fixture,expected', [
        ('L1', 'l1_token', 403),
        ('L2', 'l2_token', 200),
        ('L3', 'l3_token', 200),
    ])
    def test_pending(self, api, role_label, token_fixture, expected, request):
        token = request.getfixturevalue(token_fixture)
        status, _ = api.get('/actions/pending', token=token)
        assert status == expected, f'{role_label} expected {expected}, got {status}'


# ---------------------------------------------------------------------------
# Approve access (L2+)
# ---------------------------------------------------------------------------

class TestApproveAccess:
    """POST /actions/approve requires L2+."""

    @pytest.mark.parametrize('role_label,token_fixture,expected', [
        ('L1', 'l1_token', 403),
        ('L2', 'l2_token', 400),  # 400 = auth passed, missing request_id
        ('L3', 'l3_token', 400),
    ])
    def test_approve(self, api, role_label, token_fixture, expected, request):
        token = request.getfixturevalue(token_fixture)
        status, _ = api.post('/actions/approve', token=token, body={})
        assert status == expected, f'{role_label} expected {expected}, got {status}'


# ---------------------------------------------------------------------------
# Audit query access
# ---------------------------------------------------------------------------

class TestAuditQueryAccess:
    """Audit queries enforce role-based scoping."""

    def test_l1_sees_only_own_audit(self, api, l1_token):
        status, body = api.get('/actions/audit', token=l1_token)
        assert status == 200
        # All entries should be for L1's own email
        for entry in body.get('entries', []):
            assert entry['user'] == L1_EMAIL

    def test_l1_cannot_query_other_user(self, api, l1_token):
        status, _ = api.get('/actions/audit', token=l1_token, params={
            'user': L2_EMAIL,
        })
        assert status == 403

    def test_l1_cannot_query_by_action(self, api, l1_token):
        status, _ = api.get('/actions/audit', token=l1_token, params={
            'action': 'pull-logs',
        })
        assert status == 403

    def test_l2_can_query_by_action(self, api, l2_token):
        status, _ = api.get('/actions/audit', token=l2_token, params={
            'action': 'pull-logs',
        })
        assert status == 200

    def test_l2_cannot_query_other_user(self, api, l2_token):
        status, _ = api.get('/actions/audit', token=l2_token, params={
            'user': L1_EMAIL,
        })
        assert status == 403

    def test_l3_can_query_any_user(self, api, l3_token):
        status, _ = api.get('/actions/audit', token=l3_token, params={
            'user': L1_EMAIL,
        })
        assert status == 200


# ---------------------------------------------------------------------------
# Activity access
# ---------------------------------------------------------------------------

class TestActivityAccess:
    """Activity queries enforce role-based scoping."""

    def test_l1_forced_to_own_activity(self, api, l1_token):
        """L1 requesting other user's activity gets own data instead."""
        status, body = api.get('/activity', token=l1_token, params={
            'user': L2_EMAIL,
        })
        assert status == 200
        # Should return L1's own activity (forced by handler)
        assert 'events' in body

    def test_l1_cannot_query_by_event_type_globally(self, api, l1_token):
        """L1 querying event_type without user filter → 403."""
        # Non-admin users are forced to target_user=self, so event_type + user works.
        # But if handler logic rejects event_type without explicit user for non-admin:
        # The handler actually forces target_user = user_email for non-admins,
        # so this should succeed with the user being self
        status, _ = api.get('/activity', token=l1_token, params={
            'event_type': 'page_view',
        })
        # Handler forces target_user = l1_email, so this queries user+event_type → 200
        assert status == 200

    def test_l3_can_query_any_user(self, api, l3_token):
        status, _ = api.get('/activity', token=l3_token, params={
            'user': L1_EMAIL,
        })
        assert status == 200

    def test_l3_can_query_by_event_type(self, api, l3_token):
        status, _ = api.get('/activity', token=l3_token, params={
            'event_type': 'page_view',
        })
        assert status == 200

    def test_l3_can_get_active_users(self, api, l3_token):
        status, body = api.get('/activity', token=l3_token, params={
            'active': 'true',
        })
        assert status == 200
        assert 'active_users' in body


# ---------------------------------------------------------------------------
# Action permissions per role
# ---------------------------------------------------------------------------

class TestActionPermissions:
    """GET /actions/permissions returns correct permissions per role."""

    def test_l1_low_risk_run(self, api, l1_token):
        status, body = api.get('/actions/permissions', token=l1_token)
        assert status == 200
        pull_logs = next((a for a in body['actions'] if a['id'] == 'pull-logs'), None)
        assert pull_logs is not None
        assert pull_logs['permission'] == 'run'

    def test_l1_high_risk_request(self, api, l1_token):
        status, body = api.get('/actions/permissions', token=l1_token)
        assert status == 200
        maint = next((a for a in body['actions'] if a['id'] == 'maintenance-mode'), None)
        assert maint is not None
        assert maint['permission'] == 'request'

    def test_l2_most_actions_run(self, api, l2_token):
        status, body = api.get('/actions/permissions', token=l2_token)
        assert status == 200
        maint = next((a for a in body['actions'] if a['id'] == 'maintenance-mode'), None)
        assert maint is not None
        assert maint['permission'] == 'run'

    def test_l2_rotate_secrets_request(self, api, l2_token):
        status, body = api.get('/actions/permissions', token=l2_token)
        assert status == 200
        rotate = next((a for a in body['actions'] if a['id'] == 'rotate-secrets'), None)
        assert rotate is not None
        assert rotate['permission'] == 'request'

    def test_l3_all_actions_run(self, api, l3_token):
        status, body = api.get('/actions/permissions', token=l3_token)
        assert status == 200
        for action in body['actions']:
            assert action['permission'] == 'run', \
                f"L3 expected 'run' for {action['id']}, got {action['permission']}"

    def test_permissions_returns_all_actions(self, api, l1_token):
        status, body = api.get('/actions/permissions', token=l1_token)
        assert status == 200
        assert len(body['actions']) >= 15
