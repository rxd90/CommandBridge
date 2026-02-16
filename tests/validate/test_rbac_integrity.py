"""Cross-file referential integrity checks for RBAC configuration.

Validates that roles, actions, and users reference each other consistently,
and that every action maps to an executor Python module.
"""

import os

import pytest


class TestRolesReferencedByUsers:
    def test_all_user_roles_exist_in_roles_json(self, rbac_users, rbac_roles):
        for user in rbac_users:
            assert user['role'] in rbac_roles, \
                f"User {user['email']} has role '{user['role']}' not in roles.json"


class TestRolesReferencedByActions:
    def test_all_permission_groups_are_valid_roles(self, rbac_actions, rbac_roles):
        for action_id, action in rbac_actions.items():
            for group in action.get('permissions', {}):
                assert group in rbac_roles, \
                    f"Action '{action_id}' references group '{group}' not in roles.json"


class TestEveryActionHasAllRoles:
    def test_all_roles_covered(self, rbac_actions, rbac_roles):
        for action_id, action in rbac_actions.items():
            perms = action.get('permissions', {})
            for role in rbac_roles:
                assert role in perms, \
                    f"Action '{action_id}' missing permissions for role '{role}'"


class TestActionIdsMapToExecutors:
    def test_action_ids_map_to_executor_files(self, rbac_actions):
        executors_dir = os.path.join(
            os.path.dirname(__file__), '..', '..', 'lambdas', 'actions', 'executors',
        )
        for action_id in rbac_actions:
            module_name = action_id.replace('-', '_')
            expected_file = os.path.join(executors_dir, f'{module_name}.py')
            assert os.path.exists(expected_file), \
                f"Action '{action_id}' has no executor at {expected_file}"


class TestNoDuplicateUserEmails:
    def test_unique_emails(self, rbac_users):
        emails = [u['email'] for u in rbac_users]
        assert len(emails) == len(set(emails)), 'Duplicate emails in users.json'


class TestNoDuplicateUserIds:
    def test_unique_ids(self, rbac_users):
        ids = [u['id'] for u in rbac_users]
        assert len(ids) == len(set(ids)), 'Duplicate IDs in users.json'


class TestActiveFieldConsistency:
    def test_active_is_boolean(self, rbac_users):
        for user in rbac_users:
            assert isinstance(user['active'], bool), \
                f"User {user['email']} has non-boolean 'active' field"
