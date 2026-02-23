"""Integration tests for admin user management endpoints.

Creates test users with the 'cb-inttest-admin-' prefix.
All test users are cleaned up after the session.
"""

import time

import pytest
from urllib.parse import quote

from tests.integration.conftest import (
    L1_EMAIL, L2_EMAIL, L3_EMAIL,
    unique_admin_email, _delete_cognito_user, _delete_user,
    USER_POOL_ID,
)


# ---------------------------------------------------------------------------
# Create user
# ---------------------------------------------------------------------------

class TestAdminCreateUser:
    """POST /admin/users creates user in Cognito + DynamoDB."""

    def test_create_user_returns_201(self, api, l3_token):
        email = unique_admin_email()
        status, body = api.post('/admin/users', token=l3_token, body={
            'email': email,
            'name': 'Integration Test User',
            'role': 'L1-operator',
            'team': 'Test Team',
        })
        assert status == 201
        assert email in body['message']

    def test_create_user_exists_in_dynamodb(self, api, l3_token, users_table):
        email = unique_admin_email()
        api.post('/admin/users', token=l3_token, body={
            'email': email,
            'name': 'DDB Check User',
            'role': 'L2-engineer',
            'team': 'Test Team',
        })

        resp = users_table.get_item(Key={'email': email})
        assert 'Item' in resp
        assert resp['Item']['role'] == 'L2-engineer'
        assert resp['Item']['active'] is True

    def test_create_user_exists_in_cognito(self, api, l3_token, cognito_client):
        email = unique_admin_email()
        api.post('/admin/users', token=l3_token, body={
            'email': email,
            'name': 'Cognito Check User',
            'role': 'L1-operator',
            'team': 'Test Team',
        })

        resp = cognito_client.admin_get_user(
            UserPoolId=USER_POOL_ID,
            Username=email,
        )
        # Cognito may return the internal sub UUID as Username when the pool
        # uses email as a username alias. Verify via user attributes instead.
        attrs = {a['Name']: a['Value'] for a in resp['UserAttributes']}
        assert attrs['email'] == email

    def test_create_duplicate_returns_409(self, api, l3_token):
        email = unique_admin_email()
        api.post('/admin/users', token=l3_token, body={
            'email': email,
            'name': 'First Create',
            'role': 'L1-operator',
            'team': 'Test Team',
        })

        status, _ = api.post('/admin/users', token=l3_token, body={
            'email': email,
            'name': 'Second Create',
            'role': 'L1-operator',
            'team': 'Test Team',
        })
        assert status == 409

    def test_create_missing_fields_returns_400(self, api, l3_token):
        status, body = api.post('/admin/users', token=l3_token, body={
            'email': unique_admin_email(),
            # Missing name, role, team
        })
        assert status == 400
        assert 'required' in body['message'].lower()

    def test_create_invalid_email_returns_400(self, api, l3_token):
        status, _ = api.post('/admin/users', token=l3_token, body={
            'email': 'notanemail',
            'name': 'Bad Email',
            'role': 'L1-operator',
            'team': 'Test Team',
        })
        assert status == 400

    def test_create_invalid_role_returns_400(self, api, l3_token):
        status, _ = api.post('/admin/users', token=l3_token, body={
            'email': unique_admin_email(),
            'name': 'Bad Role',
            'role': 'L99-superadmin',
            'team': 'Test Team',
        })
        assert status == 400


# ---------------------------------------------------------------------------
# Disable user
# ---------------------------------------------------------------------------

class TestAdminDisableUser:
    """POST /admin/users/{email}/disable blocks user access."""

    def test_disable_user_returns_200(self, api, l3_token):
        email = unique_admin_email()
        api.post('/admin/users', token=l3_token, body={
            'email': email,
            'name': 'To Disable',
            'role': 'L1-operator',
            'team': 'Test Team',
        })

        status, body = api.post(
            f'/admin/users/{quote(email, safe="")}/disable',
            token=l3_token,
        )
        assert status == 200
        assert 'disabled' in body['message'].lower()

    def test_disabled_user_cannot_access_me(self, api, l1_token, l3_token, users_table):
        """Disable the L1 test user → /me returns 403 → re-enable."""
        users_table.update_item(
            Key={'email': L1_EMAIL},
            UpdateExpression='SET active = :f',
            ExpressionAttributeValues={':f': False},
        )
        try:
            status, _ = api.get('/me', token=l1_token)
            assert status == 403
        finally:
            users_table.update_item(
                Key={'email': L1_EMAIL},
                UpdateExpression='SET active = :t',
                ExpressionAttributeValues={':t': True},
            )

    def test_disable_self_returns_400(self, api, l3_token):
        status, body = api.post(
            f'/admin/users/{quote(L3_EMAIL, safe="")}/disable',
            token=l3_token,
        )
        assert status == 400
        assert 'own' in body['message'].lower() or 'self' in body['message'].lower() \
            or 'your' in body['message'].lower()

    def test_disable_nonexistent_returns_404(self, api, l3_token):
        status, _ = api.post(
            f'/admin/users/{quote("nobody@example.com", safe="")}/disable',
            token=l3_token,
        )
        assert status == 404


# ---------------------------------------------------------------------------
# Enable user
# ---------------------------------------------------------------------------

class TestAdminEnableUser:
    """POST /admin/users/{email}/enable restores user access."""

    def test_enable_user_returns_200(self, api, l3_token):
        email = unique_admin_email()
        api.post('/admin/users', token=l3_token, body={
            'email': email,
            'name': 'To Enable',
            'role': 'L1-operator',
            'team': 'Test Team',
        })
        # Disable first
        api.post(f'/admin/users/{quote(email, safe="")}/disable', token=l3_token)

        # Enable
        status, body = api.post(
            f'/admin/users/{quote(email, safe="")}/enable',
            token=l3_token,
        )
        assert status == 200
        assert 'enabled' in body['message'].lower()

    def test_enabled_user_can_access_me_again(self, api, l1_token, l3_token, users_table):
        """Disable then re-enable L1 → /me returns 200 again."""
        users_table.update_item(
            Key={'email': L1_EMAIL},
            UpdateExpression='SET active = :f',
            ExpressionAttributeValues={':f': False},
        )
        # Verify disabled
        status_disabled, _ = api.get('/me', token=l1_token)
        assert status_disabled == 403

        # Re-enable via API
        api.post(
            f'/admin/users/{quote(L1_EMAIL, safe="")}/enable',
            token=l3_token,
        )

        status_enabled, _ = api.get('/me', token=l1_token)
        assert status_enabled == 200

    def test_enable_nonexistent_returns_404(self, api, l3_token):
        status, _ = api.post(
            f'/admin/users/{quote("nobody@example.com", safe="")}/enable',
            token=l3_token,
        )
        assert status == 404


# ---------------------------------------------------------------------------
# Set role
# ---------------------------------------------------------------------------

class TestAdminSetRole:
    """POST /admin/users/{email}/role changes user role."""

    def test_set_role_returns_200(self, api, l3_token):
        email = unique_admin_email()
        api.post('/admin/users', token=l3_token, body={
            'email': email,
            'name': 'Role Change',
            'role': 'L1-operator',
            'team': 'Test Team',
        })

        status, body = api.post(
            f'/admin/users/{quote(email, safe="")}/role',
            token=l3_token,
            body={'role': 'L2-engineer'},
        )
        assert status == 200
        assert 'L2-engineer' in body['message']

    def test_role_change_reflected_in_dynamodb(self, api, l3_token, users_table):
        email = unique_admin_email()
        api.post('/admin/users', token=l3_token, body={
            'email': email,
            'name': 'DDB Role',
            'role': 'L1-operator',
            'team': 'Test Team',
        })

        api.post(
            f'/admin/users/{quote(email, safe="")}/role',
            token=l3_token,
            body={'role': 'L3-admin'},
        )

        resp = users_table.get_item(Key={'email': email})
        assert resp['Item']['role'] == 'L3-admin'

    def test_role_change_reflected_in_permissions(self, api, l1_token, l3_token):
        """Change L1→L2 → permissions endpoint shows L2 permissions."""
        # Temporarily promote L1 test user to L2
        api.post(
            f'/admin/users/{quote(L1_EMAIL, safe="")}/role',
            token=l3_token,
            body={'role': 'L2-engineer'},
        )
        try:
            status, body = api.get('/actions/permissions', token=l1_token)
            assert status == 200
            # As L2, maintenance-mode should be 'run' (not 'request')
            maint = next(
                (a for a in body['actions'] if a['id'] == 'maintenance-mode'),
                None,
            )
            if maint:
                assert maint['permission'] == 'run'
        finally:
            # Restore
            api.post(
                f'/admin/users/{quote(L1_EMAIL, safe="")}/role',
                token=l3_token,
                body={'role': 'L1-operator'},
            )

    def test_set_own_role_returns_400(self, api, l3_token):
        status, body = api.post(
            f'/admin/users/{quote(L3_EMAIL, safe="")}/role',
            token=l3_token,
            body={'role': 'L1-operator'},
        )
        assert status == 400

    def test_set_invalid_role_returns_400(self, api, l3_token):
        email = unique_admin_email()
        api.post('/admin/users', token=l3_token, body={
            'email': email,
            'name': 'Invalid Role',
            'role': 'L1-operator',
            'team': 'Test Team',
        })

        status, _ = api.post(
            f'/admin/users/{quote(email, safe="")}/role',
            token=l3_token,
            body={'role': 'invalid-role'},
        )
        assert status == 400

    def test_set_role_nonexistent_returns_404(self, api, l3_token):
        status, _ = api.post(
            f'/admin/users/{quote("nobody@example.com", safe="")}/role',
            token=l3_token,
            body={'role': 'L1-operator'},
        )
        assert status == 404
