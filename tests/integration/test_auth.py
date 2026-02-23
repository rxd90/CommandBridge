"""Integration tests for authentication and /me endpoint.

Validates token handling, profile retrieval, and role resolution
against the live API Gateway + Cognito + DynamoDB stack.
"""

import pytest

from tests.integration.conftest import (
    L1_EMAIL, L2_EMAIL, L3_EMAIL, TEST_PASSWORD,
)


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

class TestAuthentication:
    """API Gateway JWT authorizer rejects bad tokens."""

    def test_valid_token_returns_200_on_me(self, api, l1_token):
        status, body = api.get('/me', token=l1_token)
        assert status == 200
        assert body['email'] == L1_EMAIL

    def test_no_auth_header_returns_401(self, api):
        status, _ = api.get('/me', token=None)
        assert status == 401

    def test_garbage_token_returns_401(self, api):
        status, _ = api.get('/me', token='not-a-real-jwt')
        assert status == 401

    def test_malformed_bearer_returns_401(self, api):
        """Bearer prefix with garbage payload."""
        status, _ = api.get('/me', token='eyJhbGciOiJIUzI1NiJ9.garbage.garbage')
        assert status == 401


# ---------------------------------------------------------------------------
# /me endpoint
# ---------------------------------------------------------------------------

class TestMeEndpoint:
    """GET /me returns correct user profile."""

    def test_me_returns_correct_profile_l1(self, api, l1_token):
        status, body = api.get('/me', token=l1_token)
        assert status == 200
        assert body['email'] == L1_EMAIL
        assert body['role'] == 'L1-operator'
        assert body['active'] is True
        assert 'name' in body
        assert 'team' in body

    def test_me_returns_correct_profile_l2(self, api, l2_token):
        status, body = api.get('/me', token=l2_token)
        assert status == 200
        assert body['email'] == L2_EMAIL
        assert body['role'] == 'L2-engineer'

    def test_me_returns_correct_profile_l3(self, api, l3_token):
        status, body = api.get('/me', token=l3_token)
        assert status == 200
        assert body['email'] == L3_EMAIL
        assert body['role'] == 'L3-admin'

    def test_me_inactive_user_returns_403(self, api, l1_token, users_table):
        """Temporarily disable user in DDB, verify 403, then re-enable."""
        users_table.update_item(
            Key={'email': L1_EMAIL},
            UpdateExpression='SET active = :f',
            ExpressionAttributeValues={':f': False},
        )
        try:
            status, _ = api.get('/me', token=l1_token)
            assert status == 403
        finally:
            # Re-enable so other tests aren't affected
            users_table.update_item(
                Key={'email': L1_EMAIL},
                UpdateExpression='SET active = :t',
                ExpressionAttributeValues={':t': True},
            )


# ---------------------------------------------------------------------------
# Role resolution
# ---------------------------------------------------------------------------

class TestRoleResolution:
    """Handler resolves role from DynamoDB, not JWT claims."""

    def test_role_comes_from_dynamodb(self, api, l1_token):
        """Token identifies user by email; role comes from DDB lookup."""
        status, body = api.get('/me', token=l1_token)
        assert status == 200
        assert body['role'] == 'L1-operator'

    def test_user_not_in_dynamodb_returns_403(
        self, api, cognito_client, users_table
    ):
        """Valid Cognito token but no DynamoDB record → 403."""
        from tests.integration.conftest import (
            _create_cognito_user, _get_id_token, _delete_cognito_user,
        )
        orphan_email = 'cb-test-orphan@test.commandbridge.dev'
        try:
            _create_cognito_user(cognito_client, orphan_email, TEST_PASSWORD)
            token = _get_id_token(cognito_client, orphan_email, TEST_PASSWORD)
            status, _ = api.get('/me', token=token)
            assert status == 403
        finally:
            _delete_cognito_user(cognito_client, orphan_email)

    def test_role_change_reflected_immediately(self, api, l1_token, users_table):
        """Change role in DDB → next request sees new role."""
        # Temporarily promote L1 to L3
        users_table.update_item(
            Key={'email': L1_EMAIL},
            UpdateExpression='SET #r = :new_role',
            ExpressionAttributeNames={'#r': 'role'},
            ExpressionAttributeValues={':new_role': 'L3-admin'},
        )
        try:
            status, body = api.get('/me', token=l1_token)
            assert status == 200
            assert body['role'] == 'L3-admin'
        finally:
            # Restore original role
            users_table.update_item(
                Key={'email': L1_EMAIL},
                UpdateExpression='SET #r = :orig',
                ExpressionAttributeNames={'#r': 'role'},
                ExpressionAttributeValues={':orig': 'L1-operator'},
            )

    def test_empty_role_gets_no_permissions(self, api, l1_token, users_table):
        """User with role='' in DDB → permissions list empty or all locked."""
        users_table.update_item(
            Key={'email': L1_EMAIL},
            UpdateExpression='SET #r = :empty',
            ExpressionAttributeNames={'#r': 'role'},
            ExpressionAttributeValues={':empty': ''},
        )
        try:
            status, body = api.get('/actions/permissions', token=l1_token)
            assert status == 200
            # All actions should be 'locked' since empty role matches nothing
            for action in body['actions']:
                assert action['permission'] == 'locked', \
                    f"Expected 'locked' for {action['id']}, got {action['permission']}"
        finally:
            users_table.update_item(
                Key={'email': L1_EMAIL},
                UpdateExpression='SET #r = :orig',
                ExpressionAttributeNames={'#r': 'role'},
                ExpressionAttributeValues={':orig': 'L1-operator'},
            )
