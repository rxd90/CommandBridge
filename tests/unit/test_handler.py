"""Lambda handler routing and input validation tests.

Tests the API Gateway dispatch logic in lambdas/actions/handler.py.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

# Patch audit module before handler import — audit.py creates a DynamoDB
# resource at module level which would fail without AWS credentials.
import sys
import types

mock_audit = types.ModuleType('shared.audit')
mock_audit.log_action = MagicMock(return_value={'id': 'test', 'timestamp': 0})
sys.modules['shared.audit'] = mock_audit

# Patch users module before handler import — users.py creates a DynamoDB
# resource at module level which would fail without AWS credentials.
mock_users = types.ModuleType('shared.users')
mock_users.get_user_role = MagicMock(return_value=None)  # fallback to JWT groups
mock_users.get_user = MagicMock(return_value=None)
mock_users.list_users = MagicMock(return_value=[])
mock_users.update_user = MagicMock(return_value=None)
mock_users.VALID_ROLES = {'L1-operator', 'L2-engineer', 'L3-admin'}
sys.modules['shared.users'] = mock_users

# Patch audit query functions used by _handle_audit
mock_audit.query_by_user = MagicMock(return_value={'entries': [], 'cursor': None})
mock_audit.query_by_action = MagicMock(return_value={'entries': [], 'cursor': None})
mock_audit.list_recent = MagicMock(return_value={'entries': [], 'cursor': None})

from actions.handler import lambda_handler
from conftest import make_apigw_event


@pytest.fixture(autouse=True)
def _ensure_audit_mock():
    """Re-set shared.audit mock — test_audit.py reloads the real module."""
    sys.modules['shared.audit'] = mock_audit


# ---------------------------------------------------------------------------
# Route dispatch
# ---------------------------------------------------------------------------
class TestRouting:
    def test_get_permissions_returns_200(self):
        event = make_apigw_event('/actions/permissions', 'GET', groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'actions' in body

    def test_get_audit_returns_200(self):
        event = make_apigw_event('/actions/audit', 'GET', groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200

    def test_unknown_path_returns_404(self):
        event = make_apigw_event('/unknown', 'GET', groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 404

    def test_wrong_method_returns_404(self):
        event = make_apigw_event('/actions/permissions', 'POST', groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 404

    def test_execute_requires_post(self):
        event = make_apigw_event('/actions/execute', 'GET', groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 404

    def test_request_requires_post(self):
        event = make_apigw_event('/actions/request', 'GET', groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 404


# ---------------------------------------------------------------------------
# Input validation — /actions/execute
# ---------------------------------------------------------------------------
class TestExecuteValidation:
    def test_empty_body_returns_400(self):
        event = make_apigw_event('/actions/execute', 'POST', body={}, groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400

    def test_missing_ticket_returns_400(self):
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'pull-logs', 'reason': 'test'},
            groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400

    def test_missing_reason_returns_400(self):
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'pull-logs', 'ticket': 'INC-001'},
            groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400

    def test_bad_ticket_format_returns_400(self):
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'pull-logs', 'ticket': 'BADFORMAT', 'reason': 'test'},
            groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'ticket must match' in json.loads(response['body'])['message']

    def test_invalid_body_json_returns_400(self):
        event = make_apigw_event('/actions/execute', 'POST', groups=['L1-operator'])
        event['body'] = 'not-json{'
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400

    @pytest.mark.parametrize('ticket', ['INC-001', 'INC-2026-0212-001', 'CHG-1234', 'CHG-release-v2'])
    def test_valid_ticket_formats_accepted(self, ticket):
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'pull-logs', 'ticket': ticket, 'reason': 'testing'},
            groups=['L1-operator'])
        with patch('actions.handler._get_executor') as mock_exec:
            mock_exec.return_value = lambda body: {'status': 'ok'}
            response = lambda_handler(event, None)
            assert response['statusCode'] in (200, 202), f'Failed for ticket {ticket}'


# ---------------------------------------------------------------------------
# RBAC enforcement
# ---------------------------------------------------------------------------
class TestRBACEnforcement:
    def test_denied_role_returns_403(self):
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'pull-logs', 'ticket': 'INC-001', 'reason': 'test'},
            groups=['unknown-role'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 403

    def test_l1_high_risk_returns_202(self):
        """L1 executing a high-risk action gets 202 pending_approval."""
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'maintenance-mode', 'ticket': 'INC-001', 'reason': 'test'},
            groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 202
        body = json.loads(response['body'])
        assert body['status'] == 'pending_approval'

    def test_l3_can_execute_any_action(self):
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'rotate-secrets', 'ticket': 'CHG-001', 'reason': 'rotation'},
            groups=['L3-admin'])
        with patch('actions.handler._get_executor') as mock_exec:
            mock_exec.return_value = lambda body: {'status': 'rotated'}
            response = lambda_handler(event, None)
            assert response['statusCode'] == 200

    def test_executor_failure_returns_500(self):
        event = make_apigw_event('/actions/execute', 'POST',
            body={'action': 'pull-logs', 'ticket': 'INC-001', 'reason': 'test'},
            groups=['L1-operator'])
        with patch('actions.handler._get_executor') as mock_exec:
            mock_exec.return_value = MagicMock(side_effect=Exception('boto3 error'))
            response = lambda_handler(event, None)
            assert response['statusCode'] == 500
            assert 'boto3 error' in json.loads(response['body'])['message']


# ---------------------------------------------------------------------------
# Request endpoint
# ---------------------------------------------------------------------------
class TestRequestEndpoint:
    def test_valid_request_returns_202(self):
        event = make_apigw_event('/actions/request', 'POST',
            body={'action': 'maintenance-mode', 'ticket': 'INC-001', 'reason': 'need maintenance'},
            groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 202
        assert 'pending_approval' in json.loads(response['body'])['status']

    def test_request_denied_role_returns_403(self):
        event = make_apigw_event('/actions/request', 'POST',
            body={'action': 'pull-logs', 'ticket': 'INC-001', 'reason': 'test'},
            groups=['unknown-role'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 403

    def test_request_missing_fields_returns_400(self):
        event = make_apigw_event('/actions/request', 'POST',
            body={'action': 'maintenance-mode'},
            groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400


# ---------------------------------------------------------------------------
# cognito:groups normalization
# ---------------------------------------------------------------------------
class TestGroupsNormalization:
    def test_single_group_string_works(self):
        """cognito:groups can be a string (single group) — handler normalizes."""
        event = make_apigw_event('/actions/permissions', 'GET')
        event['requestContext']['authorizer']['jwt']['claims']['cognito:groups'] = 'L1-operator'
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        actions = json.loads(response['body'])['actions']
        assert len(actions) == 15

    def test_list_groups_works(self):
        event = make_apigw_event('/actions/permissions', 'GET', groups=['L2-engineer'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200


# ---------------------------------------------------------------------------
# Permissions endpoint
# ---------------------------------------------------------------------------
class TestPermissionsEndpoint:
    def test_returns_actions_list(self):
        event = make_apigw_event('/actions/permissions', 'GET', groups=['L1-operator'])
        response = lambda_handler(event, None)
        body = json.loads(response['body'])
        assert isinstance(body['actions'], list)
        assert len(body['actions']) == 15

    def test_l1_permissions_correct(self):
        event = make_apigw_event('/actions/permissions', 'GET', groups=['L1-operator'])
        response = lambda_handler(event, None)
        actions = json.loads(response['body'])['actions']
        by_id = {a['id']: a for a in actions}
        assert by_id['pull-logs']['permission'] == 'run'
        assert by_id['maintenance-mode']['permission'] == 'request'

    def test_response_has_json_content_type(self):
        event = make_apigw_event('/actions/permissions', 'GET', groups=['L1-operator'])
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
        mock_audit.log_action.reset_mock()
        # Defaults
        mock_users.get_user_role.return_value = None
        mock_users.get_user.return_value = None
        mock_users.list_users.return_value = []
        mock_users.update_user.return_value = None

    def test_list_users_requires_l3(self):
        """L1 and L2 should get 403 on /admin/users."""
        for role in ['L1-operator', 'L2-engineer']:
            event = make_apigw_event('/admin/users', 'GET', groups=[role])
            response = lambda_handler(event, None)
            assert response['statusCode'] == 403, f'{role} should be denied'

    def test_list_users_returns_users(self):
        mock_users.list_users.return_value = [
            {'email': 'a@test.com', 'name': 'A', 'role': 'L1-operator',
             'team': 'ops', 'active': True, 'created_at': '', 'updated_at': ''},
        ]
        event = make_apigw_event('/admin/users', 'GET', groups=['L3-admin'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert len(body['users']) == 1
        assert body['users'][0]['email'] == 'a@test.com'

    def test_disable_user_works(self):
        mock_users.get_user.return_value = {
            'email': 'target@scotgov.uk', 'name': 'Target', 'role': 'L1-operator',
            'active': True,
        }
        mock_users.update_user.return_value = {'email': 'target@scotgov.uk', 'active': False}

        event = make_apigw_event(
            '/admin/users/target%40scotgov.uk/disable', 'POST',
            email='admin@scotgov.uk', groups=['L3-admin'],
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        assert 'disabled' in json.loads(response['body'])['message']
        mock_users.update_user.assert_called_once()

    def test_disable_self_rejected(self):
        event = make_apigw_event(
            '/admin/users/admin%40scotgov.uk/disable', 'POST',
            email='admin@scotgov.uk', groups=['L3-admin'],
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'own account' in json.loads(response['body'])['message']

    def test_enable_user_works(self):
        mock_users.get_user.return_value = {
            'email': 'target@scotgov.uk', 'name': 'Target', 'role': 'L1-operator',
            'active': False,
        }
        mock_users.update_user.return_value = {'email': 'target@scotgov.uk', 'active': True}

        event = make_apigw_event(
            '/admin/users/target%40scotgov.uk/enable', 'POST',
            email='admin@scotgov.uk', groups=['L3-admin'],
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        assert 'enabled' in json.loads(response['body'])['message']

    def test_set_role_validates_input(self):
        event = make_apigw_event(
            '/admin/users/target%40scotgov.uk/role', 'POST',
            body={'role': 'INVALID-ROLE'},
            email='admin@scotgov.uk', groups=['L3-admin'],
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'Invalid role' in json.loads(response['body'])['message']

    def test_set_role_works(self):
        mock_users.get_user.return_value = {
            'email': 'target@scotgov.uk', 'name': 'Target', 'role': 'L1-operator',
            'active': True,
        }
        mock_users.update_user.return_value = {'email': 'target@scotgov.uk', 'role': 'L2-engineer'}

        event = make_apigw_event(
            '/admin/users/target%40scotgov.uk/role', 'POST',
            body={'role': 'L2-engineer'},
            email='admin@scotgov.uk', groups=['L3-admin'],
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        assert 'L2-engineer' in json.loads(response['body'])['message']

    def test_url_decoding(self):
        """Emails with %40 in the path are correctly decoded to @."""
        mock_users.get_user.return_value = {
            'email': 'user@example.com', 'name': 'User', 'role': 'L1-operator',
            'active': True,
        }
        mock_users.update_user.return_value = {'email': 'user@example.com', 'active': False}

        event = make_apigw_event(
            '/admin/users/user%40example.com/disable', 'POST',
            email='admin@scotgov.uk', groups=['L3-admin'],
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200
        # Verify get_user was called with decoded email, not encoded
        mock_users.get_user.assert_called_with('user@example.com')

    def test_user_not_found(self):
        mock_users.get_user.return_value = None
        event = make_apigw_event(
            '/admin/users/ghost%40scotgov.uk/disable', 'POST',
            email='admin@scotgov.uk', groups=['L3-admin'],
        )
        response = lambda_handler(event, None)
        assert response['statusCode'] == 404
        assert 'not found' in json.loads(response['body'])['message'].lower()


# ---------------------------------------------------------------------------
# Request endpoint — ticket validation
# ---------------------------------------------------------------------------
class TestRequestTicketValidation:
    def test_bad_ticket_format_returns_400(self):
        event = make_apigw_event('/actions/request', 'POST',
            body={'action': 'maintenance-mode', 'ticket': 'BADFORMAT', 'reason': 'test'},
            groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] == 400
        assert 'ticket must match' in json.loads(response['body'])['message']

    @pytest.mark.parametrize('ticket', ['INC-001', 'CHG-1234'])
    def test_valid_ticket_accepted(self, ticket):
        event = make_apigw_event('/actions/request', 'POST',
            body={'action': 'maintenance-mode', 'ticket': ticket, 'reason': 'test'},
            groups=['L1-operator'])
        response = lambda_handler(event, None)
        assert response['statusCode'] in (202, 403), f'Failed for ticket {ticket}'
