"""Shared fixtures and helpers for CommandBridge tests."""

import json
import os
import shutil
import sys

import pytest

# ---------------------------------------------------------------------------
# Path setup: make lambdas/ importable as top-level packages
# ---------------------------------------------------------------------------
_repo_root = os.path.join(os.path.dirname(__file__), '..')
_lambdas_dir = os.path.join(_repo_root, 'lambdas')
sys.path.insert(0, _lambdas_dir)

# shared.rbac does a module-level open() of ../rbac/actions.json relative to
# its own __file__.  In the Lambda deployment package that path exists because
# deploy-lambdas.yml copies it in.  For tests we replicate the same layout.
_lambdas_rbac = os.path.join(_lambdas_dir, 'rbac')
_repo_actions = os.path.join(_repo_root, 'rbac', 'actions.json')
os.makedirs(_lambdas_rbac, exist_ok=True)
shutil.copy2(_repo_actions, os.path.join(_lambdas_rbac, 'actions.json'))


# ---------------------------------------------------------------------------
# Fixtures — load the real RBAC JSON files
# ---------------------------------------------------------------------------
@pytest.fixture
def rbac_actions():
    """Load the real rbac/actions.json as a dict."""
    with open(os.path.join(_repo_root, 'rbac', 'actions.json')) as f:
        return json.load(f)


@pytest.fixture
def rbac_roles():
    """Load the real rbac/roles.json as a dict."""
    with open(os.path.join(_repo_root, 'rbac', 'roles.json')) as f:
        return json.load(f)


@pytest.fixture
def rbac_users():
    """Load the real rbac/users.json user list."""
    with open(os.path.join(_repo_root, 'rbac', 'users.json')) as f:
        return json.load(f)['users']


@pytest.fixture
def rbac_users_raw():
    """Load the full rbac/users.json (including wrapper object)."""
    with open(os.path.join(_repo_root, 'rbac', 'users.json')) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Helper — build API Gateway HTTP API v2 events
# ---------------------------------------------------------------------------
def make_apigw_event(path, method='GET', body=None, email='test@scotgov.uk', groups=None):
    """Build a minimal API Gateway HTTP API v2 event.

    Matches the shape read by lambdas/actions/handler.py lines 21-27.
    """
    event = {
        'rawPath': path,
        'requestContext': {
            'http': {'method': method},
            'authorizer': {
                'jwt': {
                    'claims': {
                        'email': email,
                        'cognito:groups': groups or [],
                    }
                }
            },
        },
    }
    if body is not None:
        event['body'] = json.dumps(body)
        event['isBase64Encoded'] = False
    return event
