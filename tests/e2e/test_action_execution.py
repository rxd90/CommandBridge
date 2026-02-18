"""E2E tests for action execution workflows.

Tests the full handler flow: routing -> RBAC -> executor -> audit logging.
All shared modules run un-mocked against moto DynamoDB.
"""

import time

import boto3
import pytest
from moto import mock_aws

from conftest import make_apigw_event
from tests.e2e.conftest import seed_user, call_handler


class TestActionExecutionE2E:
    """Full action execution flow with audit verification."""

    def test_l1_executes_low_risk_action_with_audit(self, e2e):
        """L1 executes pull-logs -> 200 + audit entry with result=success."""
        seed_user(e2e['users_table'], 'l1@scotgov.uk', 'L1 User', 'L1-operator')

        # Create CloudWatch log group so pull-logs executor succeeds
        logs = boto3.client('logs', region_name='eu-west-2')
        logs.create_log_group(logGroupName='/aws/production/identity-service')
        logs.create_log_stream(
            logGroupName='/aws/production/identity-service',
            logStreamName='test-stream',
        )

        resp = call_handler(
            e2e['handler'], '/actions/execute', 'POST',
            body={
                'action': 'pull-logs',
                'ticket': 'INC-2026-001',
                'reason': 'Investigating 5xx errors',
                'target': 'identity-service',
            },
            email='l1@scotgov.uk',
            groups=['L1-operator'],
        )

        assert resp['statusCode'] == 200
        assert resp['parsed_body']['result']['status'] == 'success'

        # Verify audit entry was written
        items = e2e['audit_table'].scan()['Items']
        assert len(items) == 1
        assert items[0]['user'] == 'l1@scotgov.uk'
        assert items[0]['action'] == 'pull-logs'
        assert items[0]['result'] == 'success'
        assert items[0]['ticket'] == 'INC-2026-001'

    def test_l1_high_risk_action_returns_pending_approval(self, e2e):
        """L1 executes a high-risk action -> 202 pending_approval + audit."""
        seed_user(e2e['users_table'], 'l1@scotgov.uk', 'L1 User', 'L1-operator')

        resp = call_handler(
            e2e['handler'], '/actions/execute', 'POST',
            body={
                'action': 'maintenance-mode',
                'ticket': 'INC-2026-002',
                'reason': 'Planned maintenance window',
            },
            email='l1@scotgov.uk',
            groups=['L1-operator'],
        )

        assert resp['statusCode'] == 202
        assert resp['parsed_body']['status'] == 'pending_approval'

        items = e2e['audit_table'].scan()['Items']
        assert len(items) == 1
        assert items[0]['result'] == 'requested'

    def test_l2_executes_operational_action_directly(self, e2e):
        """L2 executes maintenance-mode directly -> 200."""
        seed_user(e2e['users_table'], 'l2@scotgov.uk', 'L2 User', 'L2-engineer')

        # maintenance-mode executor calls SSM/AppConfig - patch it
        from unittest.mock import patch, MagicMock
        mock_exec = MagicMock(return_value={'status': 'success', 'message': 'done'})
        with patch.dict('sys.modules', {'actions.executors.maintenance_mode': MagicMock(execute=mock_exec)}):
            # Need to reload handler to pick up the patched executor
            resp = call_handler(
                e2e['handler'], '/actions/execute', 'POST',
                body={
                    'action': 'maintenance-mode',
                    'ticket': 'CHG-2026-001',
                    'reason': 'Planned maintenance',
                },
                email='l2@scotgov.uk',
                groups=['L2-engineer'],
            )

        assert resp['statusCode'] == 200
        items = e2e['audit_table'].scan()['Items']
        assert len(items) == 1
        assert items[0]['result'] == 'success'

    def test_missing_required_fields_returns_400(self, e2e):
        """Missing action/ticket/reason returns 400."""
        seed_user(e2e['users_table'], 'l1@scotgov.uk', 'L1 User', 'L1-operator')

        # Missing ticket
        resp = call_handler(
            e2e['handler'], '/actions/execute', 'POST',
            body={'action': 'pull-logs', 'reason': 'testing'},
            email='l1@scotgov.uk',
            groups=['L1-operator'],
        )
        assert resp['statusCode'] == 400
        assert 'required' in resp['parsed_body']['message']

    def test_invalid_ticket_format_returns_400(self, e2e):
        """Bad ticket format returns 400."""
        seed_user(e2e['users_table'], 'l1@scotgov.uk', 'L1 User', 'L1-operator')

        resp = call_handler(
            e2e['handler'], '/actions/execute', 'POST',
            body={
                'action': 'pull-logs',
                'ticket': 'BADFORMAT',
                'reason': 'testing',
            },
            email='l1@scotgov.uk',
            groups=['L1-operator'],
        )
        assert resp['statusCode'] == 400
        assert 'ticket' in resp['parsed_body']['message'].lower()

    def test_request_endpoint_creates_pending_audit(self, e2e):
        """POST /actions/request creates audit entry with result=requested."""
        seed_user(e2e['users_table'], 'l1@scotgov.uk', 'L1 User', 'L1-operator')

        resp = call_handler(
            e2e['handler'], '/actions/request', 'POST',
            body={
                'action': 'maintenance-mode',
                'ticket': 'INC-2026-003',
                'reason': 'Need maintenance ASAP',
            },
            email='l1@scotgov.uk',
            groups=['L1-operator'],
        )

        assert resp['statusCode'] == 202
        assert resp['parsed_body']['status'] == 'pending_approval'

        items = e2e['audit_table'].scan()['Items']
        assert len(items) == 1
        assert items[0]['result'] == 'requested'
        assert items[0]['action'] == 'maintenance-mode'
