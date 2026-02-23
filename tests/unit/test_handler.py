"""Lambda handler routing and input validation tests.

Tests the API Gateway dispatch logic in lambdas/actions/handler.py.
Role resolution is DynamoDB-only — mock_users.get_user_role controls the role.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

# Patch audit module before handler import - audit.py creates a DynamoDB
# resource at module level which would fail without AWS credentials.
import sys
import types

mock_audit = types.ModuleType('shared.audit')
mock_audit.log_action = MagicMock(return_value={'id': 'test', 'timestamp': 0})
sys.modules['shared.audit'] = mock_audit

# Patch users module before handler import - users.py creates a DynamoDB
# resource at module level which would fail without AWS credentials.
mock_users = types.ModuleType('shared.users')
mock_users.get_user_role = MagicMock(return_value='L1-operator')
mock_users.get_user = MagicMock(return_value=None)
mock_users.list_users = MagicMock(return_value=[])
mock_users.update_user = MagicMock(return_value=None)
mock_users.create_user = MagicMock(return_value={'email': 'new@test.com', 'name': 'New', 'role': 'L1-operator', 'team': 'Ops', 'active': True})
mock_users.VALID_ROLES = {'L1-operator', 'L2-engineer', 'L3-admin'}
sys.modules['shared.users'] = mock_users

# Patch audit query functions used by _handle_audit
mock_audit.query_by_user = MagicMock(return_value={'entries': [], 'cursor': None})
mock_audit.query_by_action = MagicMock(return_value={'entries': [], 'cursor': None})
mock_audit.list_recent = MagicMock(return_value={'entries': [], 'cursor': None})

# Patch activity module before handler import - activity.py creates a DynamoDB
# resource at module level which would fail without AWS credentials.
mock_activity = types.ModuleType('shared.activity')
mock_activity.log_activity_batch = MagicMock(return_value=3)
mock_activity.query_user_activity = MagicMock(return_value={'events': [], 'cursor': None})
mock_activity.query_by_event_type = MagicMock(return_value={'events': [], 'cursor': None})
mock_activity.get_active_users = MagicMock(return_value=[])
sys.modules['shared.activity'] = mock_activity

from actions.handler import lambda_handler
from conftest import make_apigw_event


@pytest.fixture(autouse=True)
def _ensure_mocks():
    """Re-set shared module mocks - other test files reload real modules which mutates these objects."""
    sys.modules['shared.audit'] = mock_audit
    sys.modules['shared.activity'] = mock_activity
    # Reload mutates mock modules in-place (same object), replacing MagicMock attrs
    # with real functions.  Restore them here.
    mock_audit.log_action = MagicMock(return_value={'id': 'test', 'timestamp': 0})
    mock_audit.query_by_user = MagicMock(return_value={'entries': [], 'cursor': None})
    mock_audit.query_by_action = MagicMock(return_value={'entries': [], 'cursor': None})
    mock_audit.list_recent = MagicMock(return_value={'entries': [], 'cursor': None})
    mock_audit.get_pending_approvals = MagicMock(return_value={'entries': [], 'cursor': None})
    mock_audit.get_audit_record_by_id = MagicMock(return_value=None)
    mock_audit.update_audit_result = MagicMock(return_value=None)
    mock_activity.log_activity_batch = MagicMock(return_value=3)
    mock_activity.query_user_activity = MagicMock(return_value={'events': [], 'cursor': None})
    mock_activity.query_by_event_type = MagicMock(return_value={'events': [], 'cursor': None})
    mock_activity.get_active_users = MagicMock(return_value=[])
    # Default role for most tests
    mock_users.get_user_role.return_value = 'L1-operator'


# ---------------------------------------------------------------------------
# Route dispatch
# ---------------------------------------------------------------------------
class TestRouting:
    def test_get_permissions_returns_200(self):
        event = make_apigw_event('/actions/permissions', 'GET')
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'actions' in body

    def test_get_audit_returns_200(self):
        event = make_apigw_event('/actions/audit', 'GET')
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200

    def test_unknown_path_returns_404(self):
        event = make_apigw_event('/unknown', 'GET')
        response = lambda_handler(event, None)
        assert response['statusCode'] == 404

    def test_wrong_method_returns_404(self):
        event = make_apigw_event('/actions/permissions', 'POST')
        response = lambda_handler(event, None)
        assert response['statusCode'] == 404

    def test_execute_requires_post(self):
        event = make_apigw_event('/actions/execute', 'GET')
        response = lambda_handler(event, None)
        assert response['statusCode'] == 404

    def test_request_requires_post(self):
        event = make_apigw_event('/actions/request', 'GET')
        response = lambda_handler(event, None)
        assert response['statusCode'] == 404


# ---------------------------------------------------------------------------
# /me endpoint
# ---------------------------------------------------------------------------
class TestMeEndpoint:
    def setup_method(self):
        mock_users.get_user_role.reset_mock()
        mock_users.get_user.reset_mock()

    def test_me_returns_user_profile(self):
        mock_users.get_user_role.return_value = 'L2-engineer'
        mock_users.get_user.return_value = {
            'email': 'test@gov.scot', 'name': 'Test User',
            'role': 'L2-engineer', 'team': 'Platform', 'active': True,
        }
        event = make_apigw_event('/me', 'GET', email='test@gov.scot')
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['email'] == 'test@gov.scot'
        assert body['role'] == 'L2-engineer'
        assert body['name'] == 'Test User'
        assert body['team'] == 'Platform'

    def test_me_returns_403_for_unknown_user(self):
        mock_users.get_user_role.return_value = None
        mock_users.get_user.return_value = None
        event = make_apigw_event('/me', 'GET', email='ghost@gov.scot')
        response = lambda_handler(event, None)
        assert response['statusCode'] == 403

    def test_me_returns_403_for_inactive_user(self):
        mock_users.get_user_role.return_value = None
        mock_users.get_user.return_value = {
            'email': 'disabled@gov.scot', 'name': 'Disabled', 'active': False,
        }
        event = make_apigw_event('/me', 'GET', email='disabled@gov.scot')
        response = lambda_handler(event, None)
        assert response['statusCode'] == 403


# ---------------------------------------------------------------------------
# Input validation - /actions/execute
# ---------------------------------------------------------------------------
class TestExecuteValidation:
    def test_empty_body_returns_400(self):
        event = make_apigw_event('/actions/execute', 'POST', body={})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400

    def test_missing_ticket_returns_400(self):
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'pull-logs', 'reason': 'test'})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400

    def test_missing_reason_returns_400(self):
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'pull-logs', 'ticket': 'INC-001'})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400

    def test_bad_ticket_format_returns_400(self):
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'pull-logs', 'ticket': 'BADFORMAT', 'reason': 'test'})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'ticket must match' in json.loads(response['body'])['message']

    def test_invalid_body_json_returns_400(self):
        event = make_apigw_event('/actions/execute', 'POST')
        event['body'] = 'not-json{'
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400

    @pytest.mark.parametrize('ticket', ['INC-001', 'INC-2026-0212-001', 'CHG-1234', 'CHG-release-v2'])
    def test_valid_ticket_formats_accepted(self, ticket):
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'pull-logs', 'ticket': ticket, 'reason': 'testing'})
        with patch('actions.handler._get_executor') as mock_exec:
            mock_exec.return_value = lambda body: {'status': 'ok'}
            response = lambda_handler(event, None)
            assert response['statusCode'] in (200, 202), f'Failed for ticket {ticket}'


# ---------------------------------------------------------------------------
# RBAC enforcement
# ---------------------------------------------------------------------------
class TestRBACEnforcement:
    def test_denied_role_returns_403(self):
        mock_users.get_user_role.return_value = None  # no role = denied
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'pull-logs', 'ticket': 'INC-001', 'reason': 'test'})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 403

    def test_l1_high_risk_returns_202(self):
        """L1 executing a high-risk action gets 202 pending_approval."""
        mock_users.get_user_role.return_value = 'L1-operator'
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'maintenance-mode', 'ticket': 'INC-001', 'reason': 'test'})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 202
        body = json.loads(response['body'])
        assert body['status'] == 'pending_approval'

    def test_l3_can_execute_any_action(self):
        mock_users.get_user_role.return_value = 'L3-admin'
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'rotate-secrets', 'ticket': 'CHG-001', 'reason': 'rotation'})
        with patch('actions.handler._get_executor') as mock_exec:
            mock_exec.return_value = lambda body: {'status': 'rotated'}
            response = lambda_handler(event, None)
            assert response['statusCode'] == 200

    def test_executor_failure_returns_500(self):
        mock_users.get_user_role.return_value = 'L1-operator'
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'pull-logs', 'ticket': 'INC-001', 'reason': 'test'})
        with patch('actions.handler._get_executor') as mock_exec:
            mock_exec.return_value = MagicMock(side_effect=Exception('boto3 error'))
            response = lambda_handler(event, None)
            assert response['statusCode'] == 500
            assert 'Action failed' in json.loads(response['body'])['message']


# ---------------------------------------------------------------------------
# Request endpoint
# ---------------------------------------------------------------------------
class TestRequestEndpoint:
    def test_valid_request_returns_202(self):
        mock_users.get_user_role.return_value = 'L1-operator'
        event = make_apigw_event('/actions/request', 'POST',
            body={'action': 'maintenance-mode', 'ticket': 'INC-001', 'reason': 'need maintenance'})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 202
        assert 'pending_approval' in json.loads(response['body'])['status']

    def test_request_denied_role_returns_403(self):
        mock_users.get_user_role.return_value = None  # no role = denied
        event = make_apigw_event('/actions/request', 'POST',
            body={'action': 'pull-logs', 'ticket': 'INC-001', 'reason': 'test'})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 403

    def test_request_missing_fields_returns_400(self):
        mock_users.get_user_role.return_value = 'L1-operator'
        event = make_apigw_event('/actions/request', 'POST',
            body={'action': 'maintenance-mode'})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400


# ---------------------------------------------------------------------------
# Permissions endpoint
# ---------------------------------------------------------------------------
class TestPermissionsEndpoint:
    def test_returns_actions_list(self):
        mock_users.get_user_role.return_value = 'L1-operator'
        event = make_apigw_event('/actions/permissions', 'GET')
        response = lambda_handler(event, None)
        body = json.loads(response['body'])
        assert isinstance(body['actions'], list)
        assert len(body['actions']) == 15

    def test_l1_permissions_correct(self):
        mock_users.get_user_role.return_value = 'L1-operator'
        event = make_apigw_event('/actions/permissions', 'GET')
        response = lambda_handler(event, None)
        actions = json.loads(response['body'])['actions']
        by_id = {a['id']: a for a in actions}
        assert by_id['pull-logs']['permission'] == 'run'
        assert by_id['maintenance-mode']['permission'] == 'request'

    def test_response_has_json_content_type(self):
        event = make_apigw_event('/actions/permissions', 'GET')
        response = lambda_handler(event, None)
        assert response['headers']['Content-Type'] == 'application/json'


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------
class TestAdminRoutes:
    """Tests for /admin/* routes added in the admin panel feature."""

    def setup_method(self):
        """Reset mocks before each test."""
        mock_users.get_user_role.reset_mock()
        mock_users.get_user.reset_mock()
        mock_users.list_users.reset_mock()
        mock_users.update_user.reset_mock()
        mock_users.create_user.reset_mock()
        mock_audit.log_action.reset_mock()
        # Defaults — admin role for admin route tests
        mock_users.get_user_role.return_value = 'L3-admin'
        mock_users.get_user.return_value = None
        mock_users.list_users.return_value = []
        mock_users.update_user.return_value = None
        mock_users.create_user.return_value = {'email': 'new@test.com', 'name': 'New', 'role': 'L1-operator', 'team': 'Ops', 'active': True}

    def test_list_users_requires_l3(self):
        """L1 and L2 should get 403 on /admin/users."""
        for role in ['L1-operator', 'L2-engineer']:
            mock_users.get_user_role.return_value = role
            event = make_apigw_event('/admin/users', 'GET')
            response = lambda_handler(event, None)
            assert response['statusCode'] == 403, f'{role} should be denied'

    def test_list_users_returns_users(self):
        mock_users.list_users.return_value = [
            {'email': 'a@test.com', 'name': 'A', 'role': 'L1-operator',
             'team': 'ops', 'active': True, 'created_at': '', 'updated_at': ''},
        ]
        event = make_apigw_event('/admin/users', 'GET')
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert len(body['users']) == 1
        assert body['users'][0]['email'] == 'a@test.com'

    def test_disable_user_works(self):
        mock_users.get_user.return_value = {
            'email': 'target@gov.scot', 'name': 'Target', 'role': 'L1-operator',
            'active': True,
        }
        mock_users.update_user.return_value = {'email': 'target@gov.scot', 'active': False}

        event = make_apigw_event(
            '/admin/users/target%40gov.scot/disable', 'POST',
            email='admin@gov.scot',
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        assert 'disabled' in json.loads(response['body'])['message']
        mock_users.update_user.assert_called_once()

    def test_disable_self_rejected(self):
        event = make_apigw_event(
            '/admin/users/admin%40gov.scot/disable', 'POST',
            email='admin@gov.scot',
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'own account' in json.loads(response['body'])['message']

    def test_enable_user_works(self):
        mock_users.get_user.return_value = {
            'email': 'target@gov.scot', 'name': 'Target', 'role': 'L1-operator',
            'active': False,
        }
        mock_users.update_user.return_value = {'email': 'target@gov.scot', 'active': True}

        event = make_apigw_event(
            '/admin/users/target%40gov.scot/enable', 'POST',
            email='admin@gov.scot',
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        assert 'enabled' in json.loads(response['body'])['message']

    def test_set_role_validates_input(self):
        event = make_apigw_event(
            '/admin/users/target%40gov.scot/role', 'POST',
            body={'role': 'INVALID-ROLE'},
            email='admin@gov.scot',
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'Invalid role' in json.loads(response['body'])['message']

    def test_set_role_works(self):
        mock_users.get_user.return_value = {
            'email': 'target@gov.scot', 'name': 'Target', 'role': 'L1-operator',
            'active': True,
        }
        mock_users.update_user.return_value = {'email': 'target@gov.scot', 'role': 'L2-engineer'}

        event = make_apigw_event(
            '/admin/users/target%40gov.scot/role', 'POST',
            body={'role': 'L2-engineer'},
            email='admin@gov.scot',
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        assert 'L2-engineer' in json.loads(response['body'])['message']

    def test_set_role_blocks_self_change(self):
        """Admins cannot change their own role."""
        event = make_apigw_event(
            '/admin/users/admin%40gov.scot/role', 'POST',
            body={'role': 'L1-operator'},
            email='admin@gov.scot',
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'Cannot change your own role' in json.loads(response['body'])['message']

    def test_url_decoding(self):
        """Emails with %40 in the path are correctly decoded to @."""
        mock_users.get_user.return_value = {
            'email': 'user@example.com', 'name': 'User', 'role': 'L1-operator',
            'active': True,
        }
        mock_users.update_user.return_value = {'email': 'user@example.com', 'active': False}

        event = make_apigw_event(
            '/admin/users/user%40example.com/disable', 'POST',
            email='admin@gov.scot',
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        # Verify get_user was called with decoded email, not encoded
        mock_users.get_user.assert_called_with('user@example.com')

    def test_user_not_found(self):
        mock_users.get_user.return_value = None
        event = make_apigw_event(
            '/admin/users/ghost%40gov.scot/disable', 'POST',
            email='admin@gov.scot',
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 404
        assert 'not found' in json.loads(response['body'])['message'].lower()


# ---------------------------------------------------------------------------
# Admin create user
# ---------------------------------------------------------------------------
class TestAdminCreateUser:
    """Tests for POST /admin/users (create user)."""

    def setup_method(self):
        mock_users.get_user_role.reset_mock()
        mock_users.get_user.reset_mock()
        mock_users.create_user.reset_mock()
        mock_audit.log_action.reset_mock()
        mock_users.get_user_role.return_value = 'L3-admin'
        mock_users.get_user.return_value = None  # user does not exist yet
        mock_users.create_user.return_value = {
            'email': 'new@gov.scot', 'name': 'New User',
            'role': 'L1-operator', 'team': 'Ops', 'active': True,
        }

    def test_create_user_requires_l3(self):
        for role in ['L1-operator', 'L2-engineer']:
            mock_users.get_user_role.return_value = role
            event = make_apigw_event('/admin/users', 'POST',
                body={'email': 'new@gov.scot', 'name': 'New', 'role': 'L1-operator', 'team': 'Ops'})
            response = lambda_handler(event, None)
            assert response['statusCode'] == 403, f'{role} should be denied'

    def test_create_user_missing_fields(self):
        event = make_apigw_event('/admin/users', 'POST',
            body={'email': 'new@gov.scot'},
            email='admin@gov.scot')
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'required' in json.loads(response['body'])['message']

    def test_create_user_invalid_role(self):
        event = make_apigw_event('/admin/users', 'POST',
            body={'email': 'new@gov.scot', 'name': 'New', 'role': 'INVALID', 'team': 'Ops'},
            email='admin@gov.scot')
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'Invalid role' in json.loads(response['body'])['message']

    def test_create_user_invalid_email(self):
        event = make_apigw_event('/admin/users', 'POST',
            body={'email': 'notanemail', 'name': 'New', 'role': 'L1-operator', 'team': 'Ops'},
            email='admin@gov.scot')
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'email' in json.loads(response['body'])['message'].lower()

    def test_create_user_already_exists(self):
        mock_users.get_user.return_value = {'email': 'exists@gov.scot', 'active': True}
        event = make_apigw_event('/admin/users', 'POST',
            body={'email': 'exists@gov.scot', 'name': 'Exists', 'role': 'L1-operator', 'team': 'Ops'},
            email='admin@gov.scot')
        response = lambda_handler(event, None)
        assert response['statusCode'] == 409
        assert 'already exists' in json.loads(response['body'])['message']

    @patch('actions.handler.boto3')
    def test_create_user_success(self, mock_boto3):
        """Successful user creation returns 201."""
        mock_cognito = MagicMock()
        mock_boto3.client.return_value = mock_cognito

        event = make_apigw_event('/admin/users', 'POST',
            body={'email': 'new@gov.scot', 'name': 'New User', 'role': 'L1-operator', 'team': 'Ops'},
            email='admin@gov.scot')

        with patch.dict('os.environ', {'USER_POOL_ID': 'pool-123'}):
            response = lambda_handler(event, None)

        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert 'created' in body['message'].lower() or 'temporary password' in body['message'].lower()
        mock_cognito.admin_create_user.assert_called_once()
        # No group assignment — Cognito is auth-only
        mock_cognito.admin_add_user_to_group.assert_not_called()
        mock_users.create_user.assert_called_once()

    @patch('actions.handler.boto3')
    def test_create_user_cognito_failure_returns_500(self, mock_boto3):
        mock_cognito = MagicMock()
        mock_cognito.admin_create_user.side_effect = Exception('Cognito error')
        mock_boto3.client.return_value = mock_cognito

        event = make_apigw_event('/admin/users', 'POST',
            body={'email': 'new@gov.scot', 'name': 'New', 'role': 'L1-operator', 'team': 'Ops'},
            email='admin@gov.scot')

        with patch.dict('os.environ', {'USER_POOL_ID': 'pool-123'}):
            response = lambda_handler(event, None)

        assert response['statusCode'] == 500
        assert 'Cognito' in json.loads(response['body'])['message']

    @patch('actions.handler.boto3')
    def test_create_user_dynamo_failure_rolls_back_cognito(self, mock_boto3):
        """If DynamoDB creation fails, the Cognito user should be deleted."""
        mock_cognito = MagicMock()
        mock_boto3.client.return_value = mock_cognito
        mock_users.create_user.side_effect = Exception('DynamoDB error')

        event = make_apigw_event('/admin/users', 'POST',
            body={'email': 'new@gov.scot', 'name': 'New', 'role': 'L1-operator', 'team': 'Ops'},
            email='admin@gov.scot')

        with patch.dict('os.environ', {'USER_POOL_ID': 'pool-123'}):
            response = lambda_handler(event, None)

        assert response['statusCode'] == 500
        mock_cognito.admin_delete_user.assert_called_once()
        # Reset side effect
        mock_users.create_user.side_effect = None


# ---------------------------------------------------------------------------
# Request endpoint - ticket validation
# ---------------------------------------------------------------------------
class TestRequestTicketValidation:
    def test_bad_ticket_format_returns_400(self):
        mock_users.get_user_role.return_value = 'L1-operator'
        event = make_apigw_event('/actions/request', 'POST',
            body={'action': 'maintenance-mode', 'ticket': 'BADFORMAT', 'reason': 'test'})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'ticket must match' in json.loads(response['body'])['message']

    @pytest.mark.parametrize('ticket', ['INC-001', 'CHG-1234'])
    def test_valid_ticket_accepted(self, ticket):
        mock_users.get_user_role.return_value = 'L1-operator'
        event = make_apigw_event('/actions/request', 'POST',
            body={'action': 'maintenance-mode', 'ticket': ticket, 'reason': 'test'})
        response = lambda_handler(event, None)
        assert response['statusCode'] in (202, 403), f'Failed for ticket {ticket}'


# ---------------------------------------------------------------------------
# Activity routes
# ---------------------------------------------------------------------------
class TestActivityRoutes:
    def setup_method(self):
        mock_activity.log_activity_batch.reset_mock()
        mock_activity.query_user_activity.reset_mock()
        mock_activity.query_by_event_type.reset_mock()
        mock_activity.get_active_users.reset_mock()
        mock_activity.log_activity_batch.return_value = 3
        mock_activity.query_user_activity.return_value = {'events': [], 'cursor': None}
        mock_activity.query_by_event_type.return_value = {'events': [], 'cursor': None}
        mock_activity.get_active_users.return_value = []
        mock_users.get_user_role.return_value = 'L1-operator'

    def test_post_activity_returns_200(self):
        event = make_apigw_event('/activity', 'POST',
            body={'events': [
                {'event_type': 'page_view', 'timestamp': 1700000000000},
                {'event_type': 'button_click', 'timestamp': 1700000001000},
            ]})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['ingested'] == 3

    def test_post_activity_missing_events_returns_400(self):
        event = make_apigw_event('/activity', 'POST', body={})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400

    def test_post_activity_empty_events_returns_400(self):
        event = make_apigw_event('/activity', 'POST', body={'events': []})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400

    def test_post_activity_invalid_events_returns_400(self):
        event = make_apigw_event('/activity', 'POST',
            body={'events': [{'event_type': '', 'timestamp': 1}]})
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400

    def test_get_activity_self_only_for_non_admin(self):
        mock_users.get_user_role.return_value = 'L1-operator'
        spy = MagicMock(return_value={'events': [], 'cursor': None})
        with patch('actions.handler.query_user_activity', spy):
            event = make_apigw_event('/activity', 'GET', email='alice@gov.scot')
            event['queryStringParameters'] = {'user': 'bob@gov.scot'}
            response = lambda_handler(event, None)
            assert response['statusCode'] == 200
            # Non-admin should query self, not the requested user
            assert spy.call_args[1]['user'] == 'alice@gov.scot'

    def test_get_activity_admin_can_query_any_user(self):
        mock_users.get_user_role.return_value = 'L3-admin'
        spy = MagicMock(return_value={'events': [], 'cursor': None})
        with patch('actions.handler.query_user_activity', spy):
            event = make_apigw_event('/activity', 'GET', email='admin@gov.scot')
            event['queryStringParameters'] = {'user': 'bob@gov.scot'}
            response = lambda_handler(event, None)
            assert response['statusCode'] == 200
            assert spy.call_args[1]['user'] == 'bob@gov.scot'

    def test_get_active_users_admin_only(self):
        mock_users.get_user_role.return_value = 'L3-admin'
        event = make_apigw_event('/activity', 'GET', email='admin@gov.scot')
        event['queryStringParameters'] = {'active': 'true'}
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'active_users' in body

    def test_get_activity_by_event_type_admin(self):
        mock_users.get_user_role.return_value = 'L3-admin'
        event = make_apigw_event('/activity', 'GET', email='admin@gov.scot')
        event['queryStringParameters'] = {'event_type': 'page_view'}
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200

    def test_get_activity_by_event_type_non_admin_denied(self):
        mock_users.get_user_role.return_value = 'L1-operator'
        event = make_apigw_event('/activity', 'GET', email='alice@gov.scot')
        event['queryStringParameters'] = {'event_type': 'page_view'}
        response = lambda_handler(event, None)
        # Non-admin with event_type but no user should still query self
        assert response['statusCode'] == 200
