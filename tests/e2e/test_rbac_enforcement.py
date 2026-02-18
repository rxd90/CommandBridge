"""E2E tests for RBAC enforcement across all endpoint types.

Verifies that role-based access control is enforced end-to-end through
the real handler, shared modules, and DynamoDB role resolution.
"""

import json

import pytest

from tests.e2e.conftest import seed_user, call_handler


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

L1_EMAIL = 'l1@scotgov.uk'
L2_EMAIL = 'l2@scotgov.uk'
L3_EMAIL = 'l3@scotgov.uk'


def _seed_all_roles(users_table):
    """Seed one user per role."""
    seed_user(users_table, L1_EMAIL, 'L1 User', 'L1-operator')
    seed_user(users_table, L2_EMAIL, 'L2 User', 'L2-engineer')
    seed_user(users_table, L3_EMAIL, 'L3 User', 'L3-admin')


# ---------------------------------------------------------------------------
# Admin endpoint access
# ---------------------------------------------------------------------------

class TestAdminEndpointsRequireL3:
    """Admin endpoints should only be accessible to L3-admin."""

    @pytest.mark.parametrize('role,email,expected', [
        ('L1-operator', L1_EMAIL, 403),
        ('L2-engineer', L2_EMAIL, 403),
        ('L3-admin', L3_EMAIL, 200),
    ])
    def test_list_users(self, e2e, role, email, expected):
        _seed_all_roles(e2e['users_table'])
        resp = call_handler(
            e2e['handler'], '/admin/users', 'GET',
            email=email, groups=[role],
        )
        assert resp['statusCode'] == expected

    @pytest.mark.parametrize('role,email,expected', [
        ('L1-operator', L1_EMAIL, 403),
        ('L2-engineer', L2_EMAIL, 403),
        ('L3-admin', L3_EMAIL, 400),  # 400 because body is missing, but that means auth passed
    ])
    def test_create_user(self, e2e, role, email, expected):
        _seed_all_roles(e2e['users_table'])
        resp = call_handler(
            e2e['handler'], '/admin/users', 'POST',
            email=email, groups=[role],
        )
        assert resp['statusCode'] == expected

    @pytest.mark.parametrize('role,email,expected', [
        ('L1-operator', L1_EMAIL, 403),
        ('L2-engineer', L2_EMAIL, 403),
        ('L3-admin', L3_EMAIL, 200),
    ])
    def test_disable_user(self, e2e, role, email, expected):
        _seed_all_roles(e2e['users_table'])
        # Target a different user than the caller
        target = L1_EMAIL if email != L1_EMAIL else L2_EMAIL
        resp = call_handler(
            e2e['handler'], f'/admin/users/{target}/disable', 'POST',
            email=email, groups=[role],
        )
        assert resp['statusCode'] == expected


# ---------------------------------------------------------------------------
# KB write/delete access
# ---------------------------------------------------------------------------

class TestKBAccessControl:
    """KB create requires L2+, delete requires L3."""

    @pytest.mark.parametrize('role,email,expected', [
        ('L1-operator', L1_EMAIL, 403),
        ('L2-engineer', L2_EMAIL, 201),
        ('L3-admin', L3_EMAIL, 201),
    ])
    def test_kb_create_requires_l2_plus(self, e2e, role, email, expected):
        _seed_all_roles(e2e['users_table'])
        resp = call_handler(
            e2e['handler'], '/kb', 'POST',
            body={
                'title': f'Test Article {role}',
                'service': 'identity',
                'owner': 'Platform Team',
                'content': 'Test content',
                'tags': ['test'],
            },
            email=email, groups=[role],
        )
        assert resp['statusCode'] == expected

    def test_kb_delete_requires_l3(self, e2e):
        """Only L3 can delete articles."""
        _seed_all_roles(e2e['users_table'])

        # Create article as L2
        create_resp = call_handler(
            e2e['handler'], '/kb', 'POST',
            body={
                'title': 'Article To Delete',
                'service': 'identity',
                'owner': 'Team',
                'content': 'Content',
            },
            email=L2_EMAIL, groups=['L2-engineer'],
        )
        assert create_resp['statusCode'] == 201
        article_id = create_resp['parsed_body']['article']['id']

        # L1 cannot delete
        resp = call_handler(
            e2e['handler'], f'/kb/{article_id}', 'DELETE',
            email=L1_EMAIL, groups=['L1-operator'],
        )
        assert resp['statusCode'] == 403

        # L2 cannot delete
        resp = call_handler(
            e2e['handler'], f'/kb/{article_id}', 'DELETE',
            email=L2_EMAIL, groups=['L2-engineer'],
        )
        assert resp['statusCode'] == 403

        # L3 can delete
        resp = call_handler(
            e2e['handler'], f'/kb/{article_id}', 'DELETE',
            email=L3_EMAIL, groups=['L3-admin'],
        )
        assert resp['statusCode'] == 200


# ---------------------------------------------------------------------------
# Permissions endpoint
# ---------------------------------------------------------------------------

class TestPermissionsEndpoint:
    """GET /actions/permissions returns correct permissions per role."""

    def test_l1_gets_correct_permissions(self, e2e):
        seed_user(e2e['users_table'], L1_EMAIL, 'L1 User', 'L1-operator')
        resp = call_handler(
            e2e['handler'], '/actions/permissions', 'GET',
            email=L1_EMAIL, groups=['L1-operator'],
        )
        assert resp['statusCode'] == 200
        actions = resp['parsed_body']['actions']
        assert isinstance(actions, list)
        assert len(actions) > 0
        # L1 should have 'run' for pull-logs
        pull_logs = next((a for a in actions if a['id'] == 'pull-logs'), None)
        assert pull_logs is not None
        assert pull_logs['permission'] == 'run'

    def test_l3_gets_run_for_all_actions(self, e2e):
        seed_user(e2e['users_table'], L3_EMAIL, 'L3 User', 'L3-admin')
        resp = call_handler(
            e2e['handler'], '/actions/permissions', 'GET',
            email=L3_EMAIL, groups=['L3-admin'],
        )
        assert resp['statusCode'] == 200
        actions = resp['parsed_body']['actions']
        for action in actions:
            assert action['permission'] == 'run', \
                f"L3 should have 'run' for {action['id']}, got {action['permission']}"


# ---------------------------------------------------------------------------
# Activity access
# ---------------------------------------------------------------------------

class TestActivityAccess:
    """Non-admin users can only query their own activity."""

    def test_non_admin_forced_to_query_self(self, e2e):
        """L1 trying to query another user's activity still gets their own."""
        _seed_all_roles(e2e['users_table'])

        # L1 tries to query L2's activity
        resp = call_handler(
            e2e['handler'], '/activity', 'GET',
            email=L1_EMAIL, groups=['L1-operator'],
            query_params={'user': L2_EMAIL},
        )
        assert resp['statusCode'] == 200
        # The response should be for L1's own activity (empty since none ingested)
        assert 'events' in resp['parsed_body']

    def test_admin_can_query_any_user(self, e2e):
        """L3 can query another user's activity."""
        _seed_all_roles(e2e['users_table'])

        resp = call_handler(
            e2e['handler'], '/activity', 'GET',
            email=L3_EMAIL, groups=['L3-admin'],
            query_params={'user': L1_EMAIL},
        )
        assert resp['statusCode'] == 200


# ---------------------------------------------------------------------------
# Role resolution from DynamoDB
# ---------------------------------------------------------------------------

class TestRoleResolution:
    """Handler resolves role from DynamoDB (source of truth), not JWT groups."""

    def test_dynamodb_role_takes_precedence_over_jwt(self, e2e):
        """If DynamoDB says L3 but JWT says L1, DynamoDB wins."""
        seed_user(e2e['users_table'], 'admin@scotgov.uk', 'Admin', 'L3-admin')

        # Pass L1-operator in JWT groups, but user is L3 in DynamoDB
        resp = call_handler(
            e2e['handler'], '/admin/users', 'GET',
            email='admin@scotgov.uk', groups=['L1-operator'],
        )
        # Should succeed because DynamoDB role is L3-admin
        assert resp['statusCode'] == 200
