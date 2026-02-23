"""Shared fixtures for CommandBridge live integration tests.

Tests hit the real deployed API Gateway with real Cognito tokens.
Session-scoped fixtures create temporary test users, obtain tokens,
and clean up all test data on teardown.
"""

import os
import time
import uuid

import boto3
import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration — from env vars with sensible defaults from frontend/.env
# ---------------------------------------------------------------------------

_repo_root = os.path.join(os.path.dirname(__file__), '..', '..')

def _load_frontend_env():
    """Parse frontend/.env for fallback values."""
    env_file = os.path.join(_repo_root, 'frontend', '.env')
    vals = {}
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    vals[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return vals

_fe = _load_frontend_env()

API_URL = os.environ.get('CB_API_URL', _fe.get('VITE_API_BASE_URL', '')).rstrip('/')
USER_POOL_ID = os.environ.get('CB_USER_POOL_ID', _fe.get('VITE_COGNITO_USER_POOL_ID', ''))
CLIENT_ID = os.environ.get('CB_CLIENT_ID', _fe.get('VITE_COGNITO_CLIENT_ID', ''))
REGION = os.environ.get('CB_REGION', _fe.get('VITE_COGNITO_REGION', 'eu-west-2'))
ENVIRONMENT = os.environ.get('CB_ENVIRONMENT', 'dev')

# Table names follow the convention: commandbridge-{env}-{table}
AUDIT_TABLE = f'commandbridge-{ENVIRONMENT}-audit'
KB_TABLE = f'commandbridge-{ENVIRONMENT}-kb'
USERS_TABLE = f'commandbridge-{ENVIRONMENT}-users'
ACTIVITY_TABLE = f'commandbridge-{ENVIRONMENT}-activity'

# Test user emails — unique prefix to avoid collisions
L1_EMAIL = 'cb-test-l1@test.commandbridge.dev'
L2_EMAIL = 'cb-test-l2@test.commandbridge.dev'
L3_EMAIL = 'cb-test-l3@test.commandbridge.dev'

TEST_USER_EMAILS = [L1_EMAIL, L2_EMAIL, L3_EMAIL]

TEST_PASSWORD = 'CbIntTest!2026xZ'

# Prefix for all test-created KB articles
KB_TEST_PREFIX = 'inttest-'

# Prefix for admin-created test users
ADMIN_TEST_PREFIX = 'cb-inttest-admin-'

# CloudWatch log group for pull-logs tests
TEST_LOG_GROUP = '/aws/test/commandbridge-integration'


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------

class ApiClient:
    """HTTP client for CommandBridge API Gateway."""

    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers['Content-Type'] = 'application/json'

    def _headers(self, token):
        h = {}
        if token:
            h['Authorization'] = f'Bearer {token}'
        return h

    def get(self, path, token=None, params=None):
        r = self.session.get(
            f'{self.base_url}{path}',
            headers=self._headers(token),
            params=params,
            timeout=30,
        )
        try:
            body = r.json()
        except Exception:
            body = {'raw': r.text}
        return r.status_code, body

    def post(self, path, token=None, body=None, raw_body=None):
        kwargs = {
            'headers': self._headers(token),
            'timeout': 30,
        }
        if raw_body is not None:
            # Send raw string (for invalid JSON tests)
            kwargs['data'] = raw_body
            kwargs['headers']['Content-Type'] = 'application/json'
        elif body is not None:
            kwargs['json'] = body
        r = self.session.post(f'{self.base_url}{path}', **kwargs)
        try:
            resp_body = r.json()
        except Exception:
            resp_body = {'raw': r.text}
        return r.status_code, resp_body

    def put(self, path, token=None, body=None, raw_body=None):
        kwargs = {
            'headers': self._headers(token),
            'timeout': 30,
        }
        if raw_body is not None:
            kwargs['data'] = raw_body
            kwargs['headers']['Content-Type'] = 'application/json'
        elif body is not None:
            kwargs['json'] = body
        r = self.session.put(f'{self.base_url}{path}', **kwargs)
        try:
            resp_body = r.json()
        except Exception:
            resp_body = {'raw': r.text}
        return r.status_code, resp_body

    def delete(self, path, token=None):
        r = self.session.delete(
            f'{self.base_url}{path}',
            headers=self._headers(token),
            timeout=30,
        )
        try:
            body = r.json()
        except Exception:
            body = {'raw': r.text}
        return r.status_code, body


# ---------------------------------------------------------------------------
# Cognito helpers
# ---------------------------------------------------------------------------

def _create_cognito_user(cognito, email, password):
    """Create a Cognito user with a permanent password."""
    cognito.admin_create_user(
        UserPoolId=USER_POOL_ID,
        Username=email,
        UserAttributes=[
            {'Name': 'email', 'Value': email},
            {'Name': 'email_verified', 'Value': 'true'},
            {'Name': 'name', 'Value': f'Test {email.split("@")[0]}'},
        ],
        TemporaryPassword=password,
        MessageAction='SUPPRESS',
    )
    cognito.admin_set_user_password(
        UserPoolId=USER_POOL_ID,
        Username=email,
        Password=password,
        Permanent=True,
    )


def _get_id_token(cognito, email, password):
    """Authenticate and return the ID token.

    Uses USER_PASSWORD_AUTH (non-SRP) flow — requires ALLOW_USER_PASSWORD_AUTH
    on the Cognito client. This is a public client so no SECRET_HASH needed.
    """
    resp = cognito.initiate_auth(
        ClientId=CLIENT_ID,
        AuthFlow='USER_PASSWORD_AUTH',
        AuthParameters={
            'USERNAME': email,
            'PASSWORD': password,
        },
    )
    return resp['AuthenticationResult']['IdToken']


def _delete_cognito_user(cognito, email):
    """Delete a Cognito user, swallowing errors."""
    try:
        cognito.admin_delete_user(UserPoolId=USER_POOL_ID, Username=email)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# DynamoDB helpers
# ---------------------------------------------------------------------------

def _seed_user(users_table, email, name, role, team='Integration Test'):
    """Insert a user record into DynamoDB."""
    users_table.put_item(Item={
        'email': email,
        'name': name,
        'role': role,
        'team': team,
        'active': True,
        'created_at': '2026-01-01T00:00:00Z',
        'updated_at': '2026-01-01T00:00:00Z',
        'updated_by': 'integration-test',
    })


def _delete_user(users_table, email):
    """Delete a user from DynamoDB, swallowing errors."""
    try:
        users_table.delete_item(Key={'email': email})
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Cleanup helpers
# ---------------------------------------------------------------------------

def cleanup_kb_articles(kb_table, prefix=KB_TEST_PREFIX):
    """Delete all KB articles whose id starts with prefix (all versions)."""
    scan_kwargs = {
        'ProjectionExpression': 'id, version',
    }
    while True:
        resp = kb_table.scan(**scan_kwargs)
        items = resp.get('Items', [])
        with kb_table.batch_writer() as batch:
            for item in items:
                if item['id'].startswith(prefix):
                    batch.delete_item(Key={'id': item['id'], 'version': item['version']})
        if 'LastEvaluatedKey' not in resp:
            break
        scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']


def cleanup_audit_entries(audit_table, user_emails):
    """Delete audit entries created by test user emails."""
    for email in user_emails:
        scan_kwargs = {
            'IndexName': 'user-index',
            'KeyConditionExpression': boto3.dynamodb.conditions.Key('user').eq(email),
            'ProjectionExpression': 'id, #ts',
            'ExpressionAttributeNames': {'#ts': 'timestamp'},
        }
        while True:
            resp = audit_table.query(**scan_kwargs)
            items = resp.get('Items', [])
            with audit_table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={'id': item['id'], 'timestamp': item['timestamp']})
            if 'LastEvaluatedKey' not in resp:
                break
            scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']


def cleanup_activity(activity_table, user_emails):
    """Delete activity entries created by test user emails."""
    for email in user_emails:
        scan_kwargs = {
            'KeyConditionExpression': boto3.dynamodb.conditions.Key('user').eq(email),
            'ProjectionExpression': '#u, #ts',
            'ExpressionAttributeNames': {'#u': 'user', '#ts': 'timestamp'},
        }
        while True:
            resp = activity_table.query(**scan_kwargs)
            items = resp.get('Items', [])
            with activity_table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={'user': item['user'], 'timestamp': item['timestamp']})
            if 'LastEvaluatedKey' not in resp:
                break
            scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']


def cleanup_admin_test_users(cognito, users_table, prefix=ADMIN_TEST_PREFIX):
    """Delete any test users created by admin tests."""
    resp = users_table.scan(ProjectionExpression='email')
    for item in resp.get('Items', []):
        if item['email'].startswith(prefix):
            _delete_cognito_user(cognito, item['email'])
            _delete_user(users_table, item['email'])


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='session')
def cognito_client():
    return boto3.client('cognito-idp', region_name=REGION)


@pytest.fixture(scope='session')
def dynamodb_resource():
    return boto3.resource('dynamodb', region_name=REGION)


@pytest.fixture(scope='session')
def logs_client():
    return boto3.client('logs', region_name=REGION)


@pytest.fixture(scope='session')
def audit_table(dynamodb_resource):
    return dynamodb_resource.Table(AUDIT_TABLE)


@pytest.fixture(scope='session')
def kb_table(dynamodb_resource):
    return dynamodb_resource.Table(KB_TABLE)


@pytest.fixture(scope='session')
def users_table(dynamodb_resource):
    return dynamodb_resource.Table(USERS_TABLE)


@pytest.fixture(scope='session')
def activity_table(dynamodb_resource):
    return dynamodb_resource.Table(ACTIVITY_TABLE)


@pytest.fixture(scope='session')
def api():
    """Session-scoped API client."""
    assert API_URL, 'CB_API_URL or VITE_API_BASE_URL must be set'
    return ApiClient(API_URL)


@pytest.fixture(scope='session')
def test_log_group(logs_client):
    """Create a CloudWatch log group for pull-logs tests."""
    try:
        logs_client.create_log_group(logGroupName=TEST_LOG_GROUP)
    except logs_client.exceptions.ResourceAlreadyExistsException:
        pass
    try:
        logs_client.create_log_stream(
            logGroupName=TEST_LOG_GROUP,
            logStreamName='test-stream',
        )
    except logs_client.exceptions.ResourceAlreadyExistsException:
        pass
    yield TEST_LOG_GROUP
    try:
        logs_client.delete_log_group(logGroupName=TEST_LOG_GROUP)
    except Exception:
        pass


@pytest.fixture(scope='session')
def test_users(cognito_client, users_table):
    """Create 3 test users in Cognito + DynamoDB, return tokens, teardown after session."""
    users = [
        (L1_EMAIL, 'Test L1 Operator', 'L1-operator'),
        (L2_EMAIL, 'Test L2 Engineer', 'L2-engineer'),
        (L3_EMAIL, 'Test L3 Admin', 'L3-admin'),
    ]

    tokens = {}

    for email, name, role in users:
        # Clean up any leftover from a previous failed run
        _delete_cognito_user(cognito_client, email)
        _delete_user(users_table, email)

        _create_cognito_user(cognito_client, email, TEST_PASSWORD)
        _seed_user(users_table, email, name, role)
        tokens[email] = _get_id_token(cognito_client, email, TEST_PASSWORD)

    yield tokens

    # Teardown
    for email, _, _ in users:
        _delete_cognito_user(cognito_client, email)
        _delete_user(users_table, email)


@pytest.fixture(scope='session')
def l1_token(test_users):
    return test_users[L1_EMAIL]


@pytest.fixture(scope='session')
def l2_token(test_users):
    return test_users[L2_EMAIL]


@pytest.fixture(scope='session')
def l3_token(test_users):
    return test_users[L3_EMAIL]


@pytest.fixture(scope='session', autouse=True)
def session_cleanup(kb_table, audit_table, activity_table, users_table, cognito_client):
    """Clean up all test data after the session completes."""
    yield
    # Cleanup runs after all tests
    all_test_emails = list(TEST_USER_EMAILS)
    # Also clean up any admin-created test users
    resp = users_table.scan(ProjectionExpression='email')
    for item in resp.get('Items', []):
        if item['email'].startswith(ADMIN_TEST_PREFIX):
            all_test_emails.append(item['email'])

    cleanup_kb_articles(kb_table)
    cleanup_audit_entries(audit_table, all_test_emails)
    cleanup_activity(activity_table, all_test_emails)
    cleanup_admin_test_users(cognito_client, users_table)


# ---------------------------------------------------------------------------
# Convenience helpers available to tests
# ---------------------------------------------------------------------------

def unique_title(base='inttest'):
    """Generate a unique KB article title with the test prefix."""
    return f'{KB_TEST_PREFIX}{base}-{uuid.uuid4().hex[:8]}'


def unique_admin_email():
    """Generate a unique email for admin user creation tests."""
    return f'{ADMIN_TEST_PREFIX}{uuid.uuid4().hex[:8]}@test.commandbridge.dev'
