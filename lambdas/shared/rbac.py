"""Server-side RBAC enforcement for CommandBridge actions.

Reads rbac/actions.json (bundled with Lambda deployment) and validates
user role from DynamoDB users table against action permissions.
"""

import json
import os

_actions_path = os.path.join(os.path.dirname(__file__), '..', 'rbac', 'actions.json')
with open(_actions_path) as f:
    ACTIONS = json.load(f)


def check_permission(user_groups: list, action_id: str, operation: str = 'run') -> dict:
    """Check if any of the user's groups permit the requested operation.

    Args:
        user_groups: List of role names resolved from DynamoDB (e.g. ['L3-admin']).
        action_id: The action identifier (e.g. 'purge-cache').
        operation: One of 'run', 'request', 'approve'.

    Returns:
        dict with 'allowed' (bool), optionally 'needs_approval' (bool) and 'reason' (str).
    """
    action = ACTIONS.get(action_id)
    if not action:
        return {'allowed': False, 'reason': f'Unknown action: {action_id}'}

    for group in user_groups:
        perms = action.get('permissions', {}).get(group)
        if perms is None:
            continue
        if perms == '*':
            return {'allowed': True, 'needs_approval': False}
        if perms.get(operation):
            return {'allowed': True, 'needs_approval': False}
        if operation == 'run' and perms.get('request'):
            return {'allowed': True, 'needs_approval': True}

    return {'allowed': False, 'reason': 'Your role does not have permission for this action'}


def get_actions_for_role(user_groups: list) -> list:
    """Return all actions with resolved permissions for the user's groups.

    Returns a list of action dicts with an added 'permission' field:
    'run', 'request', or 'locked'.
    """
    result = []
    for action_id, action in ACTIONS.items():
        permission = 'locked'
        for group in user_groups:
            perms = action.get('permissions', {}).get(group)
            if perms is None:
                continue
            if perms == '*' or perms.get('run'):
                permission = 'run'
                break
            if perms.get('request'):
                permission = 'request'

        result.append({
            'id': action_id,
            'name': action['name'],
            'description': action['description'],
            'risk': action['risk'],
            'target': action['target'],
            'runbook': action.get('runbook', ''),
            'categories': action.get('categories', []),
            'permission': permission
        })
    return result
