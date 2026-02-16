"""JSON schema validation for RBAC configuration files.

Validates that rbac/roles.json, rbac/actions.json, and rbac/users.json
conform to expected schemas.
"""

import pytest
import jsonschema


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
ROLES_SCHEMA = {
    'type': 'object',
    'minProperties': 1,
    'patternProperties': {
        '^L[1-3]-': {
            'type': 'object',
            'required': ['description', 'level'],
            'properties': {
                'description': {'type': 'string', 'minLength': 1},
                'level': {'type': 'integer', 'minimum': 1, 'maximum': 3},
            },
            'additionalProperties': False,
        }
    },
    'additionalProperties': False,
}

PERMISSION_VALUE_SCHEMA = {
    'oneOf': [
        {'const': '*'},
        {
            'type': 'object',
            'properties': {
                'run': {'type': 'boolean'},
                'request': {'type': 'boolean'},
                'approve': {'type': 'boolean'},
            },
            'additionalProperties': False,
        },
    ]
}

ACTIONS_SCHEMA = {
    'type': 'object',
    'minProperties': 1,
    'patternProperties': {
        '^[a-z][a-z0-9-]+$': {
            'type': 'object',
            'required': ['name', 'description', 'risk', 'target', 'category', 'permissions'],
            'properties': {
                'name': {'type': 'string', 'minLength': 1},
                'description': {'type': 'string', 'minLength': 1},
                'risk': {'enum': ['low', 'medium', 'high']},
                'target': {'type': 'string'},
                'runbook': {'type': 'string'},
                'category': {'type': 'string', 'enum': ['Frontend', 'Backend', 'Infrastructure', 'Security']},
                'permissions': {
                    'type': 'object',
                    'patternProperties': {
                        '^L[1-3]-': PERMISSION_VALUE_SCHEMA,
                    },
                },
            },
        }
    },
    'additionalProperties': False,
}

USERS_SCHEMA = {
    'type': 'object',
    'required': ['users'],
    'properties': {
        'users': {
            'type': 'array',
            'minItems': 1,
            'items': {
                'type': 'object',
                'required': ['id', 'name', 'email', 'role', 'team', 'active'],
                'properties': {
                    'id': {'type': 'string', 'minLength': 1},
                    'name': {'type': 'string', 'minLength': 1},
                    'email': {'type': 'string', 'pattern': '^[^@]+@[^@]+\\.[^@]+$'},
                    'role': {'type': 'string', 'pattern': '^L[1-3]-'},
                    'team': {'type': 'string', 'minLength': 1},
                    'active': {'type': 'boolean'},
                },
                'additionalProperties': False,
            },
        }
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestRolesSchema:
    def test_roles_valid(self, rbac_roles):
        jsonschema.validate(rbac_roles, ROLES_SCHEMA)

    def test_has_three_roles(self, rbac_roles):
        assert len(rbac_roles) == 3

    def test_levels_unique(self, rbac_roles):
        levels = [r['level'] for r in rbac_roles.values()]
        assert len(levels) == len(set(levels))


class TestActionsSchema:
    def test_actions_valid(self, rbac_actions):
        jsonschema.validate(rbac_actions, ACTIONS_SCHEMA)

    def test_has_ten_actions(self, rbac_actions):
        assert len(rbac_actions) == 10

    def test_action_ids_are_lowercase_hyphenated(self, rbac_actions):
        import re
        for action_id in rbac_actions:
            assert re.match(r'^[a-z][a-z0-9-]+$', action_id), \
                f'Action ID {action_id!r} is not lowercase-hyphenated'

    def test_risk_levels_valid(self, rbac_actions):
        for action_id, action in rbac_actions.items():
            assert action['risk'] in ('low', 'medium', 'high'), \
                f'Action {action_id} has invalid risk: {action["risk"]}'


class TestUsersSchema:
    def test_users_valid(self, rbac_users_raw):
        jsonschema.validate(rbac_users_raw, USERS_SCHEMA)

    def test_has_users(self, rbac_users):
        assert len(rbac_users) >= 1

    def test_emails_have_at_sign(self, rbac_users):
        for user in rbac_users:
            assert '@' in user['email']
