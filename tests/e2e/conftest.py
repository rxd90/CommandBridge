"""Shared fixtures for CommandBridge E2E tests.

Unlike unit tests that mock shared modules (audit, users, kb, activity),
E2E tests run the REAL handler with all real shared modules against
moto-backed DynamoDB and Cognito.
"""

import importlib
import json
import os
import sys

import boto3
import pytest
from moto import mock_aws

# ---------------------------------------------------------------------------
# Path setup (same as tests/conftest.py)
# ---------------------------------------------------------------------------
_repo_root = os.path.join(os.path.dirname(__file__), '..', '..')
_lambdas_dir = os.path.join(_repo_root, 'lambdas')
if _lambdas_dir not in sys.path:
    sys.path.insert(0, _lambdas_dir)

# Ensure tests/ is on path so `from conftest import ...` works
_tests_dir = os.path.join(_repo_root, 'tests')
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

from conftest import make_apigw_event  # noqa: E402

REGION = 'eu-west-2'


# ---------------------------------------------------------------------------
# DynamoDB table creators (schemas match infra/modules/storage/main.tf)
# ---------------------------------------------------------------------------

def _create_audit_table(dynamodb, name):
    return dynamodb.create_table(
        TableName=name,
        KeySchema=[
            {'AttributeName': 'id', 'KeyType': 'HASH'},
            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'id', 'AttributeType': 'S'},
            {'AttributeName': 'timestamp', 'AttributeType': 'N'},
            {'AttributeName': 'user', 'AttributeType': 'S'},
            {'AttributeName': 'action', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'user-index',
                'KeySchema': [
                    {'AttributeName': 'user', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
            },
            {
                'IndexName': 'action-index',
                'KeySchema': [
                    {'AttributeName': 'action', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
            },
        ],
        BillingMode='PAY_PER_REQUEST',
    )


def _create_kb_table(dynamodb, name):
    return dynamodb.create_table(
        TableName=name,
        KeySchema=[
            {'AttributeName': 'id', 'KeyType': 'HASH'},
            {'AttributeName': 'version', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'id', 'AttributeType': 'S'},
            {'AttributeName': 'version', 'AttributeType': 'N'},
            {'AttributeName': 'is_latest', 'AttributeType': 'S'},
            {'AttributeName': 'updated_at', 'AttributeType': 'S'},
            {'AttributeName': 'service', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'latest-index',
                'KeySchema': [
                    {'AttributeName': 'is_latest', 'KeyType': 'HASH'},
                    {'AttributeName': 'updated_at', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
            },
            {
                'IndexName': 'service-index',
                'KeySchema': [
                    {'AttributeName': 'service', 'KeyType': 'HASH'},
                    {'AttributeName': 'updated_at', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
            },
        ],
        BillingMode='PAY_PER_REQUEST',
    )


def _create_users_table(dynamodb, name):
    return dynamodb.create_table(
        TableName=name,
        KeySchema=[
            {'AttributeName': 'email', 'KeyType': 'HASH'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'email', 'AttributeType': 'S'},
        ],
        BillingMode='PAY_PER_REQUEST',
    )


def _create_activity_table(dynamodb, name):
    return dynamodb.create_table(
        TableName=name,
        KeySchema=[
            {'AttributeName': 'user', 'KeyType': 'HASH'},
            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'user', 'AttributeType': 'S'},
            {'AttributeName': 'timestamp', 'AttributeType': 'N'},
            {'AttributeName': 'event_type', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'event-type-index',
                'KeySchema': [
                    {'AttributeName': 'event_type', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
            },
        ],
        BillingMode='PAY_PER_REQUEST',
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def seed_user(users_table, email, name, role, team='Test Team'):
    """Insert a user record into the DynamoDB users table."""
    users_table.put_item(Item={
        'email': email,
        'name': name,
        'role': role,
        'team': team,
        'active': True,
        'created_at': '2026-01-01T00:00:00Z',
        'updated_at': '2026-01-01T00:00:00Z',
        'updated_by': 'seed',
    })


def call_handler(handler, path, method='GET', body=None,
                 email='test@gov.scot', groups=None, query_params=None):
    """Build an API Gateway event and invoke the handler, returning parsed response."""
    event = make_apigw_event(path, method, body, email, groups)
    if query_params:
        event['queryStringParameters'] = query_params
    result = handler(event, None)
    result['parsed_body'] = json.loads(result['body'])
    return result


# ---------------------------------------------------------------------------
# Main E2E fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def e2e(monkeypatch):
    """Full moto environment with all four DynamoDB tables + Cognito.

    Yields a dict with:
        handler  - the real lambda_handler function
        audit_table, kb_table, users_table, activity_table - DynamoDB Table objects
        user_pool_id - moto Cognito user pool ID
        cognito  - boto3 cognito-idp client
    """
    with mock_aws():
        # Set environment variables BEFORE importing/reloading modules
        monkeypatch.setenv('AUDIT_TABLE', 'cb-e2e-audit')
        monkeypatch.setenv('KB_TABLE', 'cb-e2e-kb')
        monkeypatch.setenv('USERS_TABLE', 'cb-e2e-users')
        monkeypatch.setenv('ACTIVITY_TABLE', 'cb-e2e-activity')
        monkeypatch.setenv('AWS_REGION', REGION)
        monkeypatch.setenv('AWS_DEFAULT_REGION', REGION)

        dynamodb = boto3.resource('dynamodb', region_name=REGION)

        # Create all four tables
        audit_table = _create_audit_table(dynamodb, 'cb-e2e-audit')
        kb_table = _create_kb_table(dynamodb, 'cb-e2e-kb')
        users_table = _create_users_table(dynamodb, 'cb-e2e-users')
        activity_table = _create_activity_table(dynamodb, 'cb-e2e-activity')

        # Create Cognito user pool + groups
        cognito = boto3.client('cognito-idp', region_name=REGION)
        pool_resp = cognito.create_user_pool(PoolName='cb-e2e-pool')
        user_pool_id = pool_resp['UserPool']['Id']
        monkeypatch.setenv('USER_POOL_ID', user_pool_id)

        # Purge ALL shared.* and actions.* modules from sys.modules.
        # Unit tests inject mock ModuleType objects (e.g. sys.modules['shared.audit'] = mock)
        # which corrupts the 'shared' namespace package. A selective reload isn't enough —
        # we must remove everything and re-import fresh inside the moto context.
        for mod_name in list(sys.modules):
            if mod_name == 'shared' or mod_name.startswith('shared.') \
               or mod_name == 'actions' or mod_name.startswith('actions.'):
                del sys.modules[mod_name]

        # Now import the real modules fresh (they'll bind to moto resources)
        import shared.pagination  # noqa: E402
        import shared.audit  # noqa: E402
        import shared.kb  # noqa: E402
        import shared.users  # noqa: E402
        import shared.activity  # noqa: E402
        import actions.handler  # noqa: E402

        handler = actions.handler.lambda_handler

        yield {
            'handler': handler,
            'audit_table': audit_table,
            'kb_table': kb_table,
            'users_table': users_table,
            'activity_table': activity_table,
            'user_pool_id': user_pool_id,
            'cognito': cognito,
        }
