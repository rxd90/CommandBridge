"""CommandBridge Actions Lambda handler.

Single Lambda function routed by API Gateway HTTP API path.
JWT is validated by API Gateway authorizer before this code runs.
"""

import json
import os
import sys
import re
from urllib.parse import unquote

# Add parent dir to path for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.rbac import check_permission, get_actions_for_role
from shared.audit import log_action
from shared import kb
from shared.users import get_user_role, list_users, update_user, get_user, VALID_ROLES


def lambda_handler(event, context):
    """Main handler routed by API Gateway path."""
    path = event.get('rawPath', '')
    method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')

    # Extract user identity from JWT claims (Cognito = auth only)
    # ID tokens have 'email'; access tokens have 'username' (which is the email
    # since the pool uses email as username). Fall back through both.
    claims = event.get('requestContext', {}).get('authorizer', {}).get('jwt', {}).get('claims', {})
    user_email = claims.get('email') or claims.get('username') or claims.get('cognito:username', 'unknown')

    # Resolve role from DynamoDB (source of truth for authorization)
    db_role = get_user_role(user_email)
    if db_role:
        user_groups = [db_role]
    else:
        # Fallback to JWT cognito:groups for graceful migration
        user_groups = claims.get('cognito:groups', [])
        if isinstance(user_groups, str):
            if user_groups.startswith('[') and user_groups.endswith(']'):
                user_groups = [g.strip().strip('"').strip("'")
                              for g in user_groups[1:-1].split(',') if g.strip()]
            else:
                user_groups = [user_groups]

    if path == '/actions/permissions' and method == 'GET':
        return _handle_permissions(user_groups)
    elif path == '/actions/execute' and method == 'POST':
        return _handle_execute(event, user_email, user_groups)
    elif path == '/actions/request' and method == 'POST':
        return _handle_request(event, user_email, user_groups)
    elif path == '/actions/audit' and method == 'GET':
        return _handle_audit(event, user_email, user_groups)

    # KB routes
    elif path == '/kb' and method == 'GET':
        return _handle_kb_list(event)
    elif path == '/kb' and method == 'POST':
        return _handle_kb_create(event, user_email, user_groups)
    elif re.match(r'^/kb/[^/]+/versions/\d+$', path) and method == 'GET':
        parts = path.split('/')
        return _handle_kb_get_version(parts[2], parts[4])
    elif re.match(r'^/kb/[^/]+/versions$', path) and method == 'GET':
        article_id = path.split('/')[2]
        return _handle_kb_get_versions(article_id)
    elif re.match(r'^/kb/[^/]+$', path) and method == 'GET':
        article_id = path.split('/')[2]
        return _handle_kb_get(article_id)
    elif re.match(r'^/kb/[^/]+$', path) and method == 'PUT':
        article_id = path.split('/')[2]
        return _handle_kb_update(event, article_id, user_email, user_groups)
    elif re.match(r'^/kb/[^/]+$', path) and method == 'DELETE':
        article_id = path.split('/')[2]
        return _handle_kb_delete(article_id, user_email, user_groups)

    # Admin routes
    elif path == '/admin/users' and method == 'GET':
        return _handle_admin_list_users(user_email, user_groups)
    elif re.match(r'^/admin/users/[^/]+/disable$', path) and method == 'POST':
        target_email = unquote(path.split('/')[3])
        return _handle_admin_disable_user(target_email, user_email, user_groups)
    elif re.match(r'^/admin/users/[^/]+/enable$', path) and method == 'POST':
        target_email = unquote(path.split('/')[3])
        return _handle_admin_enable_user(target_email, user_email, user_groups)
    elif re.match(r'^/admin/users/[^/]+/role$', path) and method == 'POST':
        target_email = unquote(path.split('/')[3])
        return _handle_admin_set_role(event, target_email, user_email, user_groups)

    else:
        return _response(404, {'message': 'Not found'})


def _handle_permissions(user_groups):
    """GET /actions/permissions — return actions filtered by role."""
    actions = get_actions_for_role(user_groups)
    return _response(200, {'actions': actions})


def _handle_execute(event, user_email, user_groups):
    """POST /actions/execute — execute an action if permitted."""
    body = _parse_body(event)
    if not body:
        return _response(400, {'message': 'Invalid request body'})

    action_id = body.get('action')
    ticket = body.get('ticket', '')
    reason = body.get('reason', '')

    if not action_id or not ticket or not reason:
        return _response(400, {'message': 'action, ticket, and reason are required'})

    # Validate ticket format
    if not re.match(r'^(INC|CHG)-[\w-]+$', ticket):
        return _response(400, {'message': 'ticket must match format INC-XXXX or CHG-XXXX'})

    # Check RBAC
    perm = check_permission(user_groups, action_id, 'run')
    if not perm['allowed']:
        log_action(user_email, action_id, '', ticket, 'denied')
        return _response(403, {'message': perm.get('reason', 'Not permitted')})

    if perm.get('needs_approval'):
        log_action(user_email, action_id, '', ticket, 'requested')
        return _response(202, {
            'message': f'Action {action_id} requires approval. Request submitted.',
            'status': 'pending_approval'
        })

    # Execute the action
    try:
        executor = _get_executor(action_id)
        result = executor(body)
        log_action(user_email, action_id, body.get('target', ''), ticket, 'success')
        return _response(200, {
            'message': f'Action {action_id} executed successfully.',
            'result': result
        })
    except Exception as e:
        log_action(user_email, action_id, body.get('target', ''), ticket, 'failed',
                   details={'error': str(e)})
        return _response(500, {'message': f'Action failed: {str(e)}'})


def _handle_request(event, user_email, user_groups):
    """POST /actions/request — submit an approval request for a high-risk action."""
    body = _parse_body(event)
    if not body:
        return _response(400, {'message': 'Invalid request body'})

    action_id = body.get('action')
    ticket = body.get('ticket', '')
    reason = body.get('reason', '')

    if not action_id or not ticket or not reason:
        return _response(400, {'message': 'action, ticket, and reason are required'})

    # Validate ticket format
    if not re.match(r'^(INC|CHG)-[\w-]+$', ticket):
        return _response(400, {'message': 'ticket must match format INC-XXXX or CHG-XXXX'})

    perm = check_permission(user_groups, action_id, 'run')
    if not perm['allowed']:
        return _response(403, {'message': perm.get('reason', 'Not permitted')})

    log_action(user_email, action_id, body.get('target', ''), ticket, 'requested',
               details={'reason': reason})

    return _response(202, {
        'message': f'Approval request submitted for {action_id}. An L2/L3 operator will review.',
        'status': 'pending_approval'
    })


def _handle_audit(event, user_email, user_groups):
    """GET /actions/audit — return recent audit entries from DynamoDB."""
    from shared.audit import query_by_user, query_by_action, list_recent

    params = event.get('queryStringParameters') or {}
    try:
        limit = min(int(params.get('limit', 50)), 200)
    except (TypeError, ValueError):
        limit = 50
    cursor = params.get('cursor')
    user_filter = params.get('user')
    action_filter = params.get('action')

    if user_filter:
        result = query_by_user(user_filter, limit, cursor)
    elif action_filter:
        result = query_by_action(action_filter, limit, cursor)
    else:
        result = list_recent(limit, cursor)

    return _response(200, result)


# ── KB RBAC helpers ──────────────────────────────────────────────────

def _has_write_access(user_groups):
    """Check if user has L2+ access for KB write operations."""
    return bool(set(user_groups) & {'L2-engineer', 'L3-admin'})


def _has_delete_access(user_groups):
    """Check if user has L3 access for KB delete operations."""
    return 'L3-admin' in user_groups


# ── KB route handlers ────────────────────────────────────────────────

def _handle_kb_list(event):
    """GET /kb — list latest articles with search, service filter, pagination."""
    params = event.get('queryStringParameters') or {}
    try:
        kb_limit = min(int(params.get('limit', 25)), 100)
    except (TypeError, ValueError):
        kb_limit = 25
    result = kb.list_articles(
        search=params.get('search'),
        service=params.get('service'),
        category=params.get('category'),
        cursor=params.get('cursor'),
        limit=kb_limit,
    )
    return _response(200, result)


def _handle_kb_get(article_id):
    """GET /kb/{id} — get a single article (latest version)."""
    article = kb.get_article(article_id)
    if not article:
        return _response(404, {'message': 'Article not found'})
    return _response(200, {'article': article})


def _handle_kb_get_versions(article_id):
    """GET /kb/{id}/versions — list all versions of an article."""
    versions = kb.get_versions(article_id)
    if not versions:
        return _response(404, {'message': 'Article not found'})
    return _response(200, {'versions': versions})


def _handle_kb_get_version(article_id, version):
    """GET /kb/{id}/versions/{ver} — get a specific version."""
    article = kb.get_article(article_id, version=int(version))
    if not article:
        return _response(404, {'message': 'Version not found'})
    return _response(200, {'article': article})


def _handle_kb_create(event, user_email, user_groups):
    """POST /kb — create a new article (L2+ only)."""
    if not _has_write_access(user_groups):
        log_action(user_email, 'kb-denied', '', '', 'denied',
                   details={'attempted': 'create'})
        return _response(403, {'message': 'L2+ access required to create articles'})

    body = _parse_body(event)
    if not body:
        return _response(400, {'message': 'Invalid request body'})

    title = body.get('title', '').strip()
    if not title:
        return _response(400, {'message': 'title is required'})

    article = kb.create_article(
        title=title,
        service=body.get('service', ''),
        owner=body.get('owner', ''),
        tags=body.get('tags', []),
        content=body.get('content', ''),
        user_email=user_email,
        category=body.get('category', ''),
    )

    if not article:
        return _response(409, {'message': 'An article with this slug already exists'})

    log_action(user_email, 'kb-create', article['id'], '', 'success',
               details={'title': title})
    return _response(201, {'article': article})


def _handle_kb_update(event, article_id, user_email, user_groups):
    """PUT /kb/{id} — update an article, creating a new version (L2+ only)."""
    if not _has_write_access(user_groups):
        log_action(user_email, 'kb-denied', article_id, '', 'denied',
                   details={'attempted': 'update'})
        return _response(403, {'message': 'L2+ access required to edit articles'})

    body = _parse_body(event)
    if not body:
        return _response(400, {'message': 'Invalid request body'})

    article = kb.update_article(
        article_id=article_id,
        title=body.get('title'),
        service=body.get('service'),
        owner=body.get('owner'),
        tags=body.get('tags'),
        content=body.get('content'),
        user_email=user_email,
        category=body.get('category'),
    )

    if not article:
        return _response(404, {'message': 'Article not found'})

    log_action(user_email, 'kb-update', article_id, '', 'success',
               details={'title': article['title'], 'version': article['version']})
    return _response(200, {'article': article})


def _handle_kb_delete(article_id, user_email, user_groups):
    """DELETE /kb/{id} — delete all versions of an article (L3 only)."""
    if not _has_delete_access(user_groups):
        log_action(user_email, 'kb-denied', article_id, '', 'denied',
                   details={'attempted': 'delete'})
        return _response(403, {'message': 'L3 access required to delete articles'})

    # Get article title for audit before deleting
    article = kb.get_article(article_id)
    if not article:
        return _response(404, {'message': 'Article not found'})

    deleted = kb.delete_article(article_id)
    if not deleted:
        return _response(404, {'message': 'Article not found'})

    log_action(user_email, 'kb-delete', article_id, '', 'success',
               details={'title': article['title']})
    return _response(200, {'message': f'Article {article_id} deleted'})


# ── Admin route handlers ─────────────────────────────────────────────

def _is_admin(user_groups):
    """Check if user has L3 admin access."""
    return 'L3-admin' in user_groups


def _handle_admin_list_users(user_email, user_groups):
    """GET /admin/users — list all users from DynamoDB."""
    if not _is_admin(user_groups):
        return _response(403, {'message': 'L3 admin access required'})

    users = list_users()
    return _response(200, {'users': users})


def _handle_admin_disable_user(target_email, user_email, user_groups):
    """POST /admin/users/{email}/disable — disable a user."""
    if not _is_admin(user_groups):
        return _response(403, {'message': 'L3 admin access required'})

    if target_email == user_email:
        return _response(400, {'message': 'Cannot disable your own account'})

    user = get_user(target_email)
    if not user:
        return _response(404, {'message': 'User not found'})

    update_user(target_email, {'active': False}, user_email)
    log_action(user_email, 'admin-disable-user', target_email, '', 'success')
    return _response(200, {'message': f'User {target_email} disabled'})


def _handle_admin_enable_user(target_email, user_email, user_groups):
    """POST /admin/users/{email}/enable — enable a user."""
    if not _is_admin(user_groups):
        return _response(403, {'message': 'L3 admin access required'})

    user = get_user(target_email)
    if not user:
        return _response(404, {'message': 'User not found'})

    update_user(target_email, {'active': True}, user_email)
    log_action(user_email, 'admin-enable-user', target_email, '', 'success')
    return _response(200, {'message': f'User {target_email} enabled'})


def _handle_admin_set_role(event, target_email, user_email, user_groups):
    """POST /admin/users/{email}/role — change a user's role."""
    if not _is_admin(user_groups):
        return _response(403, {'message': 'L3 admin access required'})

    body = _parse_body(event)
    if not body or 'role' not in body:
        return _response(400, {'message': 'role is required in request body'})

    new_role = body['role']
    if new_role not in VALID_ROLES:
        return _response(400, {'message': f'Invalid role. Must be one of: {", ".join(sorted(VALID_ROLES))}'})

    user = get_user(target_email)
    if not user:
        return _response(404, {'message': 'User not found'})

    old_role = user.get('role', 'unknown')
    update_user(target_email, {'role': new_role}, user_email)
    log_action(user_email, 'admin-set-role', target_email, '', 'success',
               details={'old_role': old_role, 'new_role': new_role})
    return _response(200, {'message': f'User {target_email} role changed to {new_role}'})


def _get_executor(action_id):
    """Dynamically import and return the executor function for an action."""
    module_name = action_id.replace('-', '_')
    mod = __import__(f'actions.executors.{module_name}', fromlist=['execute'])
    return mod.execute


def _parse_body(event):
    """Parse JSON body from API Gateway event."""
    try:
        body = event.get('body', '{}')
        if event.get('isBase64Encoded'):
            import base64
            body = base64.b64decode(body).decode()
        return json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return None


def _response(status_code, body):
    """Return API Gateway HTTP API response."""
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(body)
    }
