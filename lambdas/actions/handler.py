"""CommandBridge Actions Lambda handler.

Single Lambda function routed by API Gateway HTTP API path.
JWT is validated by API Gateway authorizer before this code runs.
"""

import json
import os
import sys
import re

# Add parent dir to path for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.rbac import check_permission, get_actions_for_role
from shared.audit import log_action
from shared import kb


def lambda_handler(event, context):
    """Main handler routed by API Gateway path."""
    path = event.get('rawPath', '')
    method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')

    # Extract user info from JWT claims (passed by API GW authorizer)
    claims = event.get('requestContext', {}).get('authorizer', {}).get('jwt', {}).get('claims', {})
    user_email = claims.get('email', claims.get('cognito:username', 'unknown'))
    user_groups = claims.get('cognito:groups', [])

    # cognito:groups may come as:
    # - a list: ['L3-admin']
    # - a string: 'L3-admin'
    # - a bracket-wrapped string from API GW: '[L3-admin]'
    if isinstance(user_groups, str):
        # API Gateway JWT authorizer may pass groups as "[L3-admin]" string
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
        return _handle_audit(user_email, user_groups)

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

    perm = check_permission(user_groups, action_id, 'run')
    if not perm['allowed']:
        return _response(403, {'message': perm.get('reason', 'Not permitted')})

    log_action(user_email, action_id, body.get('target', ''), ticket, 'requested',
               details={'reason': reason})

    return _response(202, {
        'message': f'Approval request submitted for {action_id}. An L2/L3 operator will review.',
        'status': 'pending_approval'
    })


def _handle_audit(user_email, user_groups):
    """GET /actions/audit — return recent audit entries."""
    # For now return a placeholder; full implementation queries DynamoDB
    return _response(200, {
        'message': 'Audit log endpoint. Full implementation queries DynamoDB.',
        'entries': []
    })


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
    result = kb.list_articles(
        search=params.get('search'),
        service=params.get('service'),
        category=params.get('category'),
        cursor=params.get('cursor'),
        limit=params.get('limit', 25),
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


def _get_executor(action_id):
    """Dynamically import and return the executor function for an action."""
    module_name = action_id.replace('-', '_')
    try:
        mod = __import__(f'actions.executors.{module_name}', fromlist=['execute'])
        return mod.execute
    except ImportError:
        # Return a stub executor for actions not yet implemented
        def stub(body):
            return {'status': 'simulated', 'message': f'{action_id} executor not yet implemented'}
        return stub


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
