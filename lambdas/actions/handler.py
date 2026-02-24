"""CommandBridge Actions Lambda handler.

Single Lambda function routed by API Gateway HTTP API path.
JWT is validated by API Gateway authorizer before this code runs.
"""

import json
import os
import secrets
import string
import sys
import re
import time
from urllib.parse import unquote

import boto3

# Add parent dir to path for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.rbac import check_permission, get_actions_for_role
from shared.audit import log_action
from shared import kb
from shared.users import get_user_role, list_users, update_user, get_user, create_user, VALID_ROLES
from shared.activity import log_activity_batch, query_user_activity, query_by_event_type, get_active_users


def lambda_handler(event, context):
    """Main handler routed by API Gateway path."""
    path = event.get('rawPath', '')
    method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')

    # Extract user identity from JWT claims (Cognito = auth only)
    # ID tokens have 'email'; access tokens have 'username' (which is the email
    # since the pool uses email as username). Fall back through both.
    claims = event.get('requestContext', {}).get('authorizer', {}).get('jwt', {}).get('claims', {})
    user_email = (claims.get('email') or claims.get('username') or claims.get('cognito:username', 'unknown')).strip().lower()

    # Resolve role from DynamoDB (sole source of truth for authorization)
    db_role = get_user_role(user_email)
    user_groups = [db_role] if db_role else []

    if path == '/me' and method == 'GET':
        return _handle_me(user_email)
    elif path == '/actions/permissions' and method == 'GET':
        return _handle_permissions(user_groups)
    elif path == '/actions/execute' and method == 'POST':
        return _handle_execute(event, user_email, user_groups)
    elif path == '/actions/request' and method == 'POST':
        return _handle_request(event, user_email, user_groups)
    elif path == '/actions/approve' and method == 'POST':
        return _handle_approve_request(event, user_email, user_groups)
    elif path == '/actions/pending' and method == 'GET':
        return _handle_pending_approvals(user_email, user_groups)
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
    elif path == '/admin/users' and method == 'POST':
        return _handle_admin_create_user(event, user_email, user_groups)
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

    # Activity routes
    elif path == '/activity' and method == 'POST':
        return _handle_activity_ingest(event, user_email)
    elif path == '/activity' and method == 'GET':
        return _handle_activity_query(event, user_email, user_groups)

    else:
        return _response(404, {'message': 'Not found'})


def _handle_me(user_email):
    """GET /me - return the current user's profile from DynamoDB."""
    user = get_user(user_email)
    if not user or not user.get('active', True):
        return _response(403, {'message': 'User not found or inactive'})
    return _response(200, {
        'email': user['email'],
        'name': user.get('name', ''),
        'role': user.get('role', ''),
        'team': user.get('team', ''),
        'active': user.get('active', True),
    })


def _handle_permissions(user_groups):
    """GET /actions/permissions - return actions filtered by role."""
    actions = get_actions_for_role(user_groups)
    return _response(200, {'actions': actions})


def _handle_execute(event, user_email, user_groups):
    """POST /actions/execute - execute an action if permitted."""
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
        record = log_action(user_email, action_id, body.get('target', ''), ticket, 'requested',
                            details={'reason': reason, 'request_body': body})
        return _response(202, {
            'message': f'Action {action_id} requires approval. Request submitted.',
            'status': 'pending_approval',
            'request_id': record['id'],
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
        return _response(500, {'message': 'Action failed. Check audit log for details.'})


def _handle_request(event, user_email, user_groups):
    """POST /actions/request - submit an approval request for a high-risk action."""
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

    record = log_action(user_email, action_id, body.get('target', ''), ticket, 'requested',
                        details={'reason': reason, 'request_body': body})

    return _response(202, {
        'message': f'Approval request submitted for {action_id}. An L2/L3 operator will review.',
        'status': 'pending_approval',
        'request_id': record['id'],
    })


def _handle_audit(event, user_email, user_groups):
    """GET /actions/audit - return audit entries from DynamoDB.

    Access rules:
    - Any authenticated user may query their own history (?user=<own email>).
    - L2+ may query by action type and list recent entries (no filter).
    - L3 only may query another user's history (?user=<other email>).
    L1 users who supply no filter are served their own history automatically.
    """
    from shared.audit import query_by_user, query_by_action, list_recent

    params = event.get('queryStringParameters') or {}
    try:
        limit = min(int(params.get('limit', 50)), 200)
    except (TypeError, ValueError):
        limit = 50
    cursor = params.get('cursor')
    user_filter = params.get('user')
    action_filter = params.get('action')

    # Cross-user query: L3 only
    if user_filter and user_filter != user_email:
        if not _is_admin(user_groups):
            return _response(403, {'message': "L3 admin access required to view another user's audit history"})

    # Action-type query: L2+
    if action_filter and not _has_write_access(user_groups):
        return _response(403, {'message': 'L2+ access required to query by action type'})

    # No filter: L2+ see recent; L1 are scoped to their own history
    if not user_filter and not action_filter:
        if not _has_write_access(user_groups):
            user_filter = user_email

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
    """GET /kb - list latest articles with search, service filter, pagination."""
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
    """GET /kb/{id} - get a single article (latest version)."""
    article = kb.get_article(article_id)
    if not article:
        return _response(404, {'message': 'Article not found'})
    return _response(200, {'article': article})


def _handle_kb_get_versions(article_id):
    """GET /kb/{id}/versions - list all versions of an article."""
    versions = kb.get_versions(article_id)
    if not versions:
        return _response(404, {'message': 'Article not found'})
    return _response(200, {'versions': versions})


def _handle_kb_get_version(article_id, version):
    """GET /kb/{id}/versions/{ver} - get a specific version."""
    article = kb.get_article(article_id, version=int(version))
    if not article:
        return _response(404, {'message': 'Version not found'})
    return _response(200, {'article': article})


def _handle_kb_create(event, user_email, user_groups):
    """POST /kb - create a new article (L2+ only)."""
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
    """PUT /kb/{id} - update an article, creating a new version (L2+ only)."""
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
    """DELETE /kb/{id} - delete all versions of an article (L3 only)."""
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
    """GET /admin/users - list all users from DynamoDB."""
    if not _is_admin(user_groups):
        return _response(403, {'message': 'L3 admin access required'})

    users = list_users()
    return _response(200, {'users': users})


def _handle_admin_disable_user(target_email, user_email, user_groups):
    """POST /admin/users/{email}/disable - disable a user."""
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
    """POST /admin/users/{email}/enable - enable a user."""
    if not _is_admin(user_groups):
        return _response(403, {'message': 'L3 admin access required'})

    user = get_user(target_email)
    if not user:
        return _response(404, {'message': 'User not found'})

    # Re-enable in Cognito so the user can log in again
    user_pool_id = os.environ.get('USER_POOL_ID')
    if user_pool_id:
        cognito = boto3.client('cognito-idp', region_name=os.environ.get('AWS_REGION', 'eu-west-2'))
        try:
            cognito.admin_enable_user(UserPoolId=user_pool_id, Username=target_email)
        except Exception:
            pass  # User may not exist in Cognito yet (DynamoDB-only)

    update_user(target_email, {'active': True}, user_email)
    log_action(user_email, 'admin-enable-user', target_email, '', 'success')
    return _response(200, {'message': f'User {target_email} enabled'})


def _handle_admin_set_role(event, target_email, user_email, user_groups):
    """POST /admin/users/{email}/role - change a user's role."""
    if not _is_admin(user_groups):
        return _response(403, {'message': 'L3 admin access required'})

    if target_email.lower() == user_email.lower():
        return _response(400, {'message': 'Cannot change your own role'})

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


def _handle_admin_create_user(event, user_email, user_groups):
    """POST /admin/users - create a new user in Cognito and DynamoDB."""
    if not _is_admin(user_groups):
        return _response(403, {'message': 'L3 admin access required'})

    body = _parse_body(event)
    if not body:
        return _response(400, {'message': 'Invalid request body'})

    email = (body.get('email') or '').strip().lower()
    name = (body.get('name') or '').strip()
    role = (body.get('role') or '').strip()
    team = (body.get('team') or '').strip()

    if not email or not name or not role or not team:
        return _response(400, {'message': 'email, name, role, and team are required'})

    if role not in VALID_ROLES:
        return _response(400, {'message': f'Invalid role. Must be one of: {", ".join(sorted(VALID_ROLES))}'})

    if '@' not in email or '.' not in email.split('@')[-1]:
        return _response(400, {'message': 'Invalid email format'})

    existing = get_user(email)
    if existing:
        return _response(409, {'message': f'User {email} already exists'})

    user_pool_id = os.environ.get('USER_POOL_ID')
    if not user_pool_id:
        return _response(500, {'message': 'Cognito user pool not configured'})

    temp_password = _generate_temp_password()

    cognito = boto3.client('cognito-idp', region_name=os.environ.get('AWS_REGION', 'eu-west-2'))

    try:
        cognito.admin_create_user(
            UserPoolId=user_pool_id,
            Username=email,
            UserAttributes=[
                {'Name': 'email', 'Value': email},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'name', 'Value': name},
            ],
            TemporaryPassword=temp_password,
            # Send the welcome email so Cognito delivers the temporary password
            # directly to the user.  Do NOT return temp_password in the API response.
        )
    except Exception as e:
        error_name = type(e).__name__
        if 'UsernameExistsException' in error_name:
            return _response(409, {'message': f'User {email} already exists in Cognito'})
        return _response(500, {'message': f'Failed to create Cognito user: {str(e)}'})

    try:
        create_user(email, name, role, team, user_email)
    except Exception as e:
        # Rollback Cognito user on DynamoDB failure
        try:
            cognito.admin_delete_user(UserPoolId=user_pool_id, Username=email)
        except Exception:
            pass
        return _response(500, {'message': f'Failed to create user record: {str(e)}'})

    log_action(user_email, 'admin-create-user', email, '', 'success',
               details={'name': name, 'role': role, 'team': team})

    return _response(201, {
        'message': f'User {email} created. A temporary password has been sent to their email address.',
    })


def _handle_pending_approvals(user_email, user_groups):
    """GET /actions/pending - list pending approval requests (L2+ only)."""
    if not _has_write_access(user_groups):
        return _response(403, {'message': 'L2+ access required to view pending approvals'})

    from shared.audit import get_pending_approvals
    pending = get_pending_approvals()

    # Strip the stored request_body from list view — approvers fetch the full
    # record via the approve endpoint; no need to expose it in the list.
    sanitized = []
    for item in pending:
        entry = {k: v for k, v in item.items() if k != 'details'}
        details_public = {k: v for k, v in item.get('details', {}).items() if k != 'request_body'}
        if details_public:
            entry['details'] = details_public
        sanitized.append(entry)

    return _response(200, {'pending': sanitized})


def _handle_approve_request(event, user_email, user_groups):
    """POST /actions/approve - L2+ approves and executes a pending request."""
    if not _has_write_access(user_groups):
        return _response(403, {'message': 'L2+ access required to approve requests'})

    body = _parse_body(event)
    if not body or not body.get('request_id'):
        return _response(400, {'message': 'request_id is required'})

    from shared.audit import get_audit_record_by_id, update_audit_result

    record = get_audit_record_by_id(body['request_id'])
    if not record:
        return _response(404, {'message': 'Request not found'})

    if record['result'] != 'requested':
        return _response(409, {'message': f"Request is already '{record['result']}'"})

    # Prevent self-approval
    if record['user'].lower() == user_email.lower():
        return _response(403, {'message': 'Cannot approve your own request'})

    # Verify the approver's role covers this action
    perm = check_permission(user_groups, record['action'], 'approve')
    if not perm['allowed']:
        return _response(403, {'message': f"Your role cannot approve '{record['action']}'"})

    # Retrieve the original request body stored at submission time
    request_body = record.get('details', {}).get('request_body')
    if not request_body:
        return _response(400, {'message': 'No request body stored for this record; cannot replay'})

    action_id = record['action']
    ticket = record['ticket']

    try:
        executor = _get_executor(action_id)
        result = executor(request_body)
        update_audit_result(record['id'], record['timestamp'], 'approved', user_email)
        log_action(user_email, action_id, request_body.get('target', ''), ticket, 'success',
                   approved_by=user_email,
                   details={'approved_request_id': record['id']})
        return _response(200, {
            'message': f'Action {action_id} approved and executed.',
            'result': result,
        })
    except Exception as e:
        update_audit_result(record['id'], record['timestamp'], 'approval_failed', user_email)
        log_action(user_email, action_id, request_body.get('target', ''), ticket, 'failed',
                   details={'error': str(e), 'approved_request_id': record['id']})
        return _response(500, {'message': 'Action failed after approval. Check audit log for details.'})


def _generate_temp_password(length=16):
    """Generate a secure temporary password meeting Cognito requirements."""
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice('!@#$%^&*()-_=+'),
    ]
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*()-_=+'
    password.extend(secrets.choice(alphabet) for _ in range(length - len(password)))
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)


# ── Activity route handlers ──────────────────────────────────────────

def _handle_activity_ingest(event, user_email):
    """POST /activity - ingest a batch of frontend activity events."""
    body = _parse_body(event)
    if not body or 'events' not in body:
        return _response(400, {'message': 'events array is required'})

    events = body['events']
    if not isinstance(events, list) or len(events) == 0:
        return _response(400, {'message': 'events must be a non-empty array'})

    # Cap batch size to prevent abuse
    if len(events) > 100:
        events = events[:100]

    # Server-side stamp each event with authenticated user
    sanitized = []
    for evt in events:
        event_type = evt.get('event_type', '').strip() if isinstance(evt.get('event_type'), str) else ''
        if not event_type:
            continue
        sanitized.append({
            'user': user_email,
            'event_type': event_type,
            'timestamp': int(evt.get('timestamp', int(time.time() * 1000))),
            'data': evt.get('data') or {},
        })

    if not sanitized:
        return _response(400, {'message': 'No valid events in batch'})

    count = log_activity_batch(sanitized)
    return _response(200, {'ingested': count})


def _handle_activity_query(event, user_email, user_groups):
    """GET /activity - query activity events (L3 admin: any user; others: self only)."""
    params = event.get('queryStringParameters') or {}

    try:
        limit = min(int(params.get('limit', 50)), 200)
    except (TypeError, ValueError):
        limit = 50

    cursor = params.get('cursor')
    target_user = params.get('user')
    event_type = params.get('event_type')

    # Non-admin users can only view their own activity
    if not _is_admin(user_groups):
        target_user = user_email

    # Special query: active users (admin only)
    if params.get('active') == 'true' and _is_admin(user_groups):
        since = int(params.get('since_minutes', 15))
        users = get_active_users(since_minutes=since)
        return _response(200, {'active_users': users})

    try:
        start_time = int(params['start']) if params.get('start') else None
        end_time = int(params['end']) if params.get('end') else None
    except (ValueError, TypeError):
        return _response(400, {'message': 'start and end must be numeric timestamps'})

    # Query by event type (no user filter) - admin only
    if event_type and not target_user:
        if not _is_admin(user_groups):
            return _response(403, {'message': 'L3 admin access required for cross-user queries'})
        result = query_by_event_type(event_type, start_time, end_time, limit, cursor)
        return _response(200, result)

    # Query by user (default: self)
    if not target_user:
        target_user = user_email

    result = query_user_activity(
        user=target_user,
        start_time=start_time,
        end_time=end_time,
        event_type=event_type,
        limit=limit,
        cursor=cursor,
    )
    return _response(200, result)


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
