"""RBAC permission matrix tests.

Exhaustively tests every cell of the 15-action x 3-role permission matrix
defined in rbac/actions.json against the enforcement logic in
lambdas/shared/rbac.py.
"""

import pytest

from shared.rbac import check_permission, get_actions_for_role

# ---------------------------------------------------------------------------
# L1-operator: can RUN 7 safe actions
# ---------------------------------------------------------------------------
L1_RUN_ACTIONS = [
    'pull-logs', 'purge-cache', 'restart-pods', 'scale-service', 'drain-traffic',
    'flush-token-cache', 'export-audit-log',
]


@pytest.mark.parametrize('action_id', L1_RUN_ACTIONS)
class TestL1CanRunSafeActions:
    def test_l1_allowed_to_run(self, action_id):
        result = check_permission(['L1-operator'], action_id, 'run')
        assert result['allowed'] is True
        assert result.get('needs_approval') is False


# ---------------------------------------------------------------------------
# L1-operator: needs APPROVAL for 8 high/medium-risk actions
# ---------------------------------------------------------------------------
L1_REQUEST_ACTIONS = [
    'maintenance-mode', 'blacklist-ip', 'failover-region',
    'pause-enrolments', 'rotate-secrets',
    'revoke-sessions', 'toggle-idv-provider', 'disable-user',
]


@pytest.mark.parametrize('action_id', L1_REQUEST_ACTIONS)
class TestL1NeedsApprovalForHighRisk:
    def test_l1_needs_approval(self, action_id):
        result = check_permission(['L1-operator'], action_id, 'run')
        assert result['allowed'] is True
        assert result['needs_approval'] is True


# ---------------------------------------------------------------------------
# L2-engineer: can RUN most things directly
# ---------------------------------------------------------------------------
L2_RUN_ACTIONS = [
    'pull-logs', 'purge-cache', 'restart-pods', 'scale-service',
    'drain-traffic', 'maintenance-mode', 'blacklist-ip',
    'failover-region', 'pause-enrolments',
    'revoke-sessions', 'flush-token-cache', 'toggle-idv-provider',
    'export-audit-log', 'disable-user',
]


@pytest.mark.parametrize('action_id', L2_RUN_ACTIONS)
class TestL2CanRunOperational:
    def test_l2_allowed_to_run(self, action_id):
        result = check_permission(['L2-engineer'], action_id, 'run')
        assert result['allowed'] is True
        assert result.get('needs_approval') is False


# ---------------------------------------------------------------------------
# L2-engineer: needs approval for rotate-secrets
# ---------------------------------------------------------------------------
class TestL2CannotRunRotateSecrets:
    def test_l2_needs_approval_for_rotate_secrets(self):
        result = check_permission(['L2-engineer'], 'rotate-secrets', 'run')
        assert result['allowed'] is True
        assert result['needs_approval'] is True


# ---------------------------------------------------------------------------
# L3-admin: unrestricted on everything
# ---------------------------------------------------------------------------
ALL_ACTIONS = L1_RUN_ACTIONS + L1_REQUEST_ACTIONS


@pytest.mark.parametrize('action_id', ALL_ACTIONS)
class TestL3Unrestricted:
    def test_l3_can_run(self, action_id):
        result = check_permission(['L3-admin'], action_id, 'run')
        assert result['allowed'] is True
        assert result.get('needs_approval') is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestUnknownRoleDenied:
    def test_unknown_role_denied(self):
        result = check_permission(['unknown-role'], 'pull-logs', 'run')
        assert result['allowed'] is False

    def test_empty_groups_denied(self):
        result = check_permission([], 'pull-logs', 'run')
        assert result['allowed'] is False


class TestUnknownAction:
    def test_unknown_action_denied(self):
        result = check_permission(['L3-admin'], 'nonexistent-action', 'run')
        assert result['allowed'] is False
        assert 'Unknown action' in result.get('reason', '')


# ---------------------------------------------------------------------------
# get_actions_for_role — permission label resolution
# ---------------------------------------------------------------------------
class TestGetActionsForRole:
    def test_l1_sees_all_actions(self):
        actions = get_actions_for_role(['L1-operator'])
        assert len(actions) == 15
        ids = {a['id'] for a in actions}
        assert 'pull-logs' in ids
        assert 'rotate-secrets' in ids

    def test_l1_permissions_resolved(self):
        actions = get_actions_for_role(['L1-operator'])
        by_id = {a['id']: a for a in actions}
        assert by_id['pull-logs']['permission'] == 'run'
        assert by_id['purge-cache']['permission'] == 'run'
        assert by_id['maintenance-mode']['permission'] == 'request'
        assert by_id['rotate-secrets']['permission'] == 'request'
        assert by_id['flush-token-cache']['permission'] == 'run'
        assert by_id['export-audit-log']['permission'] == 'run'
        assert by_id['revoke-sessions']['permission'] == 'request'
        assert by_id['toggle-idv-provider']['permission'] == 'request'
        assert by_id['disable-user']['permission'] == 'request'

    def test_l2_permissions_resolved(self):
        actions = get_actions_for_role(['L2-engineer'])
        by_id = {a['id']: a for a in actions}
        assert by_id['pull-logs']['permission'] == 'run'
        assert by_id['maintenance-mode']['permission'] == 'run'
        assert by_id['rotate-secrets']['permission'] == 'request'
        assert by_id['revoke-sessions']['permission'] == 'run'
        assert by_id['flush-token-cache']['permission'] == 'run'
        assert by_id['toggle-idv-provider']['permission'] == 'run'
        assert by_id['export-audit-log']['permission'] == 'run'
        assert by_id['disable-user']['permission'] == 'run'

    def test_l3_all_run(self):
        actions = get_actions_for_role(['L3-admin'])
        assert all(a['permission'] == 'run' for a in actions)

    def test_unknown_role_all_locked(self):
        actions = get_actions_for_role(['nobody'])
        assert all(a['permission'] == 'locked' for a in actions)

    def test_action_fields_present(self):
        actions = get_actions_for_role(['L1-operator'])
        for action in actions:
            assert 'id' in action
            assert 'name' in action
            assert 'description' in action
            assert 'risk' in action
            assert 'categories' in action
            assert 'permission' in action
