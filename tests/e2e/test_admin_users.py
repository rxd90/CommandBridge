"""E2E tests for admin user management workflows.

Tests the full lifecycle: create -> list -> disable -> enable -> role change,
all through the real handler with DynamoDB + Cognito (via moto).
"""

import json

import pytest

from tests.e2e.conftest import seed_user, call_handler

ADMIN_EMAIL = 'admin@gov.scot'


class TestAdminUserLifecycleE2E:
    """Full admin user management lifecycle."""

    def test_full_user_lifecycle(self, e2e):
        """Create -> List -> Disable -> Enable -> Change role."""
        seed_user(e2e['users_table'], ADMIN_EMAIL, 'Admin User', 'L3-admin')

        # 1. Create user
        resp = call_handler(
            e2e['handler'], '/admin/users', 'POST',
            body={
                'email': 'new.user@gov.scot',
                'name': 'New User',
                'role': 'L1-operator',
                'team': 'Support',
            },
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )
        assert resp['statusCode'] == 201
        assert 'temporary_password' in resp['parsed_body']

        # 2. List users - new user should appear
        resp = call_handler(
            e2e['handler'], '/admin/users', 'GET',
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )
        assert resp['statusCode'] == 200
        users = resp['parsed_body']['users']
        emails = [u['email'] for u in users]
        assert 'new.user@gov.scot' in emails

        # 3. Disable user
        resp = call_handler(
            e2e['handler'], '/admin/users/new.user@gov.scot/disable', 'POST',
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )
        assert resp['statusCode'] == 200

        # Verify user is disabled in DynamoDB
        user_item = e2e['users_table'].get_item(Key={'email': 'new.user@gov.scot'})['Item']
        assert user_item['active'] is False

        # 4. Enable user
        resp = call_handler(
            e2e['handler'], '/admin/users/new.user@gov.scot/enable', 'POST',
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )
        assert resp['statusCode'] == 200

        user_item = e2e['users_table'].get_item(Key={'email': 'new.user@gov.scot'})['Item']
        assert user_item['active'] is True

        # 5. Change role
        resp = call_handler(
            e2e['handler'], '/admin/users/new.user@gov.scot/role', 'POST',
            body={'role': 'L2-engineer'},
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )
        assert resp['statusCode'] == 200

        user_item = e2e['users_table'].get_item(Key={'email': 'new.user@gov.scot'})['Item']
        assert user_item['role'] == 'L2-engineer'

    def test_create_duplicate_user_returns_409(self, e2e):
        seed_user(e2e['users_table'], ADMIN_EMAIL, 'Admin', 'L3-admin')
        seed_user(e2e['users_table'], 'existing@gov.scot', 'Existing', 'L1-operator')

        resp = call_handler(
            e2e['handler'], '/admin/users', 'POST',
            body={
                'email': 'existing@gov.scot',
                'name': 'Duplicate',
                'role': 'L1-operator',
                'team': 'Support',
            },
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )
        assert resp['statusCode'] == 409

    def test_disable_self_returns_400(self, e2e):
        seed_user(e2e['users_table'], ADMIN_EMAIL, 'Admin', 'L3-admin')

        resp = call_handler(
            e2e['handler'], f'/admin/users/{ADMIN_EMAIL}/disable', 'POST',
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )
        assert resp['statusCode'] == 400
        assert 'own account' in resp['parsed_body']['message'].lower()

    def test_change_own_role_returns_400(self, e2e):
        seed_user(e2e['users_table'], ADMIN_EMAIL, 'Admin', 'L3-admin')

        resp = call_handler(
            e2e['handler'], f'/admin/users/{ADMIN_EMAIL}/role', 'POST',
            body={'role': 'L1-operator'},
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )
        assert resp['statusCode'] == 400
        assert 'own role' in resp['parsed_body']['message'].lower()

    def test_invalid_role_returns_400(self, e2e):
        seed_user(e2e['users_table'], ADMIN_EMAIL, 'Admin', 'L3-admin')

        resp = call_handler(
            e2e['handler'], '/admin/users', 'POST',
            body={
                'email': 'test@gov.scot',
                'name': 'Test',
                'role': 'invalid-role',
                'team': 'Support',
            },
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )
        assert resp['statusCode'] == 400
        assert 'Invalid role' in resp['parsed_body']['message']

    def test_invalid_email_returns_400(self, e2e):
        seed_user(e2e['users_table'], ADMIN_EMAIL, 'Admin', 'L3-admin')

        resp = call_handler(
            e2e['handler'], '/admin/users', 'POST',
            body={
                'email': 'not-an-email',
                'name': 'Test',
                'role': 'L1-operator',
                'team': 'Support',
            },
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )
        assert resp['statusCode'] == 400

    def test_disable_nonexistent_user_returns_404(self, e2e):
        seed_user(e2e['users_table'], ADMIN_EMAIL, 'Admin', 'L3-admin')

        resp = call_handler(
            e2e['handler'], '/admin/users/nobody@gov.scot/disable', 'POST',
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )
        assert resp['statusCode'] == 404

    def test_admin_operations_create_audit_entries(self, e2e):
        """Admin create/disable/enable/role-change all write audit entries."""
        seed_user(e2e['users_table'], ADMIN_EMAIL, 'Admin', 'L3-admin')

        # Create
        call_handler(
            e2e['handler'], '/admin/users', 'POST',
            body={
                'email': 'audited@gov.scot',
                'name': 'Audited User',
                'role': 'L1-operator',
                'team': 'Support',
            },
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )

        # Disable
        call_handler(
            e2e['handler'], '/admin/users/audited@gov.scot/disable', 'POST',
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )

        # Enable
        call_handler(
            e2e['handler'], '/admin/users/audited@gov.scot/enable', 'POST',
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )

        # Change role
        call_handler(
            e2e['handler'], '/admin/users/audited@gov.scot/role', 'POST',
            body={'role': 'L2-engineer'},
            email=ADMIN_EMAIL, groups=['L3-admin'],
        )

        items = e2e['audit_table'].scan()['Items']
        actions = sorted([i['action'] for i in items])
        assert actions == [
            'admin-create-user',
            'admin-disable-user',
            'admin-enable-user',
            'admin-set-role',
        ]
