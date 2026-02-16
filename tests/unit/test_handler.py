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

from actions.handler import lambda_handler
from conftest import make_apigw_event


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
        assert len(actions) == 10

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
        assert len(body['actions']) == 10

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
