"""Audit logging tests with moto DynamoDB mocking.

Tests lambdas/shared/audit.py - writes action records to DynamoDB.
"""

import importlib
import os

import boto3
import pytest
from moto import mock_aws


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    """Set up moto mock and DynamoDB table for every test."""
    with mock_aws():
        monkeypatch.setenv('AUDIT_TABLE', 'commandbridge-test-audit')
        dynamodb = boto3.resource('dynamodb', region_name='eu-west-2')
        table = dynamodb.create_table(
            TableName='commandbridge-test-audit',
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'},
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'N'},
            ],
            BillingMode='PAY_PER_REQUEST',
        )
        # Re-import to pick up mocked boto3/env
        import shared.audit as audit_mod
        importlib.reload(audit_mod)
        yield {'audit': audit_mod, 'table': table}


class TestAuditLogging:
    def test_log_action_writes_record(self, aws_env):
        record = aws_env['audit'].log_action(
            user='alice@gov.scot',
            action='purge-cache',
            target='redis-eu-west-1',
            ticket='INC-2026-0212-001',
            result='success',
        )
        assert record['user'] == 'alice@gov.scot'
        assert record['action'] == 'purge-cache'
        assert record['target'] == 'redis-eu-west-1'
        assert record['ticket'] == 'INC-2026-0212-001'
        assert record['result'] == 'success'
        assert 'id' in record
        assert isinstance(record['timestamp'], int)

    def test_approved_by_defaults_to_empty(self, aws_env):
        record = aws_env['audit'].log_action(
            user='alice@gov.scot',
            action='purge-cache',
            target='',
            ticket='INC-001',
            result='success',
        )
        assert record['approved_by'] == ''

    def test_approved_by_custom_value(self, aws_env):
        record = aws_env['audit'].log_action(
            user='alice@gov.scot',
            action='maintenance-mode',
            target='production',
            ticket='CHG-001',
            result='success',
            approved_by='carol@gov.scot',
        )
        assert record['approved_by'] == 'carol@gov.scot'

    def test_details_stored_when_provided(self, aws_env):
        details = {'error': 'timeout', 'retries': 3}
        record = aws_env['audit'].log_action(
            user='bob@gov.scot',
            action='restart-pods',
            target='auth-service',
            ticket='INC-002',
            result='failed',
            details=details,
        )
        assert record['details'] == details

    def test_details_absent_when_not_provided(self, aws_env):
        record = aws_env['audit'].log_action(
            user='alice@gov.scot',
            action='pull-logs',
            target='idv-service',
            ticket='INC-003',
            result='success',
        )
        assert 'details' not in record

    def test_record_scannable_from_table(self, aws_env):
        aws_env['audit'].log_action(
            user='alice@gov.scot',
            action='purge-cache',
            target='redis',
            ticket='INC-004',
            result='success',
        )
        response = aws_env['table'].scan()
        assert response['Count'] == 1
        item = response['Items'][0]
        assert item['user'] == 'alice@gov.scot'
        assert item['action'] == 'purge-cache'

    def test_denied_result_recorded(self, aws_env):
        record = aws_env['audit'].log_action(
            user='alice@gov.scot',
            action='rotate-secrets',
            target='',
            ticket='INC-005',
            result='denied',
        )
        assert record['result'] == 'denied'

    def test_requested_result_recorded(self, aws_env):
        record = aws_env['audit'].log_action(
            user='alice@gov.scot',
            action='maintenance-mode',
            target='production',
            ticket='INC-006',
            result='requested',
            details={'reason': 'scheduled maintenance'},
        )
        assert record['result'] == 'requested'
        assert record['details']['reason'] == 'scheduled maintenance'
