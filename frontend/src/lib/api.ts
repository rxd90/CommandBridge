import { config } from '../config';
import { getAccessToken, getCurrentUser } from './auth';
import type { ExecuteResult, KBListResponse, KBArticleResponse, KBVersionSummary, AuditListResponse, AdminUser, CreateUserResponse, ActivityListResponse, ActiveUser } from '../types';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getAccessToken();
  if (!token) {
    throw new Error('Not authenticated');
  }
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);

  let res: Response;
  try {
    res = await fetch(`${config.apiBaseUrl}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Request timed out');
    }
    throw err;
  }
  clearTimeout(timeoutId);

  let data: Record<string, unknown>;
  try {
    data = await res.json();
  } catch {
    throw new Error(`Request failed (${res.status})`);
  }
  if (res.status === 401) {
    // Token expired or invalid - clear session and redirect to login
    sessionStorage.removeItem('cb_session');
    window.location.href = '/login';
    throw new Error('Session expired. Redirecting to login.');
  }
  if (!res.ok) {
    throw new Error((data.message as string) || `Request failed (${res.status})`);
  }
  return data as T;
}

export interface MeResponse {
  email: string;
  name: string;
  role: string;
  team: string;
  active: boolean;
}

export async function fetchMe(): Promise<MeResponse> {
  if (config.localDev) {
    const user = getCurrentUser();
    return {
      email: user?.email || '',
      name: user?.name || '',
      role: user?.role || '',
      team: '',
      active: true,
    };
  }
  return request<MeResponse>('/me');
}

export async function executeAction(
  actionId: string,
  ticket: string,
  reason: string,
): Promise<ExecuteResult> {
  if (config.localDev) {
    return {
      message: `Action ${actionId} executed (local dev mode). Ticket: ${ticket}`,
      status: 'simulated',
    };
  }

  return request<ExecuteResult>('/actions/execute', {
    method: 'POST',
    body: JSON.stringify({ action: actionId, ticket, reason }),
  });
}

export async function requestAction(
  actionId: string,
  ticket: string,
  reason: string,
): Promise<ExecuteResult> {
  if (config.localDev) {
    return {
      message: `Request for ${actionId} submitted (local dev mode). Ticket: ${ticket}`,
      status: 'pending_approval',
    };
  }

  return request<ExecuteResult>('/actions/request', {
    method: 'POST',
    body: JSON.stringify({ action: actionId, ticket, reason }),
  });
}

// ── KB API ──────────────────────────────────────────────────────────

const LOCAL_KB_ARTICLES = [
  { id: 'login-failures', version: 1, title: 'Login Failures', slug: 'login-failures', service: 'ScotAccount Auth (OIDC)', owner: 'Identity Platform', category: 'Backend', tags: ['login', 'oidc', 'auth'], last_reviewed: '2026-01-08', created_at: '2026-01-08T00:00:00Z', created_by: 'seed', updated_at: '2026-01-08T00:00:00Z', updated_by: 'seed' },
  { id: 'mfa-issues', version: 1, title: 'MFA Issues', slug: 'mfa-issues', service: 'MFA / SMS / Push', owner: 'Trust & Safety', category: 'Backend', tags: ['mfa', 'sms', 'otp'], last_reviewed: '2026-01-05', created_at: '2026-01-05T00:00:00Z', created_by: 'seed', updated_at: '2026-01-05T00:00:00Z', updated_by: 'seed' },
  { id: 'idv-failures', version: 1, title: 'IDV Failures', slug: 'idv-failures', service: 'Document Verification', owner: 'Enrolment', category: 'Backend', tags: ['idv', 'documents'], last_reviewed: '2026-01-06', created_at: '2026-01-06T00:00:00Z', created_by: 'seed', updated_at: '2026-01-06T00:00:00Z', updated_by: 'seed' },
  { id: 'api-gateway-5xx', version: 1, title: 'API Gateway 5xx', slug: 'api-gateway-5xx', service: 'API Gateway', owner: 'Platform Ops', category: 'Infrastructure', tags: ['api', '5xx', 'gateway'], last_reviewed: '2026-01-10', created_at: '2026-01-10T00:00:00Z', created_by: 'seed', updated_at: '2026-01-10T00:00:00Z', updated_by: 'seed' },
  { id: 'waf-ip-blocking-guide', version: 1, title: 'WAF IP Blocking Guide', slug: 'waf-ip-blocking-guide', service: 'WAF', owner: 'Security', category: 'Security', tags: ['waf', 'ip', 'security'], last_reviewed: '2026-02-14', created_at: '2026-02-14T00:00:00Z', created_by: 'seed', updated_at: '2026-02-14T00:00:00Z', updated_by: 'seed' },
  { id: 'commandbridge-user-guide', version: 1, title: 'CommandBridge User Guide', slug: 'commandbridge-user-guide', service: 'CommandBridge', owner: 'Platform Ops', category: 'Frontend', tags: ['commandbridge', 'guide', 'portal'], last_reviewed: '2026-02-14', created_at: '2026-02-14T00:00:00Z', created_by: 'seed', updated_at: '2026-02-14T00:00:00Z', updated_by: 'seed' },
  { id: 'session-revocation', version: 1, title: 'Session Revocation', slug: 'session-revocation', service: 'Cognito User Pool', owner: 'Identity Platform', category: 'Security', tags: ['session', 'revoke', 'cognito', 'compromised'], last_reviewed: '2026-02-16', created_at: '2026-02-16T00:00:00Z', created_by: 'seed', updated_at: '2026-02-16T00:00:00Z', updated_by: 'seed' },
  { id: 'token-cache-refresh', version: 1, title: 'Token Cache Refresh', slug: 'token-cache-refresh', service: 'OIDC / JWKS Cache', owner: 'Identity Platform', category: 'Backend', tags: ['oidc', 'jwks', 'token', 'cache'], last_reviewed: '2026-02-16', created_at: '2026-02-16T00:00:00Z', created_by: 'seed', updated_at: '2026-02-16T00:00:00Z', updated_by: 'seed' },
  { id: 'idv-provider-failover', version: 1, title: 'IDV Provider Failover', slug: 'idv-provider-failover', service: 'Document Verification Service', owner: 'Enrolment', category: 'Backend', tags: ['idv', 'failover', 'provider'], last_reviewed: '2026-02-16', created_at: '2026-02-16T00:00:00Z', created_by: 'seed', updated_at: '2026-02-16T00:00:00Z', updated_by: 'seed' },
  { id: 'audit-export-procedure', version: 1, title: 'Audit Export Procedure', slug: 'audit-export-procedure', service: 'DynamoDB Audit Table', owner: 'Platform Ops', category: 'Security', tags: ['audit', 'export', 'compliance', 's3'], last_reviewed: '2026-02-16', created_at: '2026-02-16T00:00:00Z', created_by: 'seed', updated_at: '2026-02-16T00:00:00Z', updated_by: 'seed' },
  { id: 'account-suspension', version: 1, title: 'Account Suspension', slug: 'account-suspension', service: 'Cognito User Pool', owner: 'Trust & Safety', category: 'Security', tags: ['cognito', 'disable', 'suspend', 'user'], last_reviewed: '2026-02-16', created_at: '2026-02-16T00:00:00Z', created_by: 'seed', updated_at: '2026-02-16T00:00:00Z', updated_by: 'seed' },
  { id: 'cognito-rate-limits', version: 1, title: 'Cognito Rate Limits', slug: 'cognito-rate-limits', service: 'Cognito User Pool', owner: 'Identity Platform', category: 'Backend', tags: ['cognito', 'rate-limit', 'throttling'], last_reviewed: '2026-02-16', created_at: '2026-02-16T00:00:00Z', created_by: 'seed', updated_at: '2026-02-16T00:00:00Z', updated_by: 'seed' },
  { id: 'scotaccount-onboarding-checklist', version: 1, title: 'ScotAccount Service Onboarding Checklist', slug: 'scotaccount-onboarding-checklist', service: 'ScotAccount Integration', owner: 'Platform Ops', category: 'Backend', tags: ['onboarding', 'integration', 'oidc', 'relying-party'], last_reviewed: '2026-02-16', created_at: '2026-02-16T00:00:00Z', created_by: 'seed', updated_at: '2026-02-16T00:00:00Z', updated_by: 'seed' },
  { id: '2fa-sms-delivery', version: 1, title: '2FA SMS Delivery Issues', slug: '2fa-sms-delivery', service: 'MFA / SMS / Push', owner: 'Trust & Safety', category: 'Backend', tags: ['mfa', 'sms', '2fa', 'otp', 'delivery'], last_reviewed: '2026-02-16', created_at: '2026-02-16T00:00:00Z', created_by: 'seed', updated_at: '2026-02-16T00:00:00Z', updated_by: 'seed' },
  { id: 'data-subject-access-request', version: 1, title: 'Data Subject Access Request (DSAR) Procedure', slug: 'data-subject-access-request', service: 'ScotAccount Data', owner: 'Trust & Safety', category: 'Security', tags: ['dsar', 'gdpr', 'data-protection', 'privacy'], last_reviewed: '2026-02-16', created_at: '2026-02-16T00:00:00Z', created_by: 'seed', updated_at: '2026-02-16T00:00:00Z', updated_by: 'seed' },
  { id: 'session-cache', version: 1, title: 'Session Cache', slug: 'session-cache', service: 'Redis / ElastiCache', owner: 'Identity Platform', category: 'Backend', tags: ['sessions', 'redis', 'caching', 'login-loops', 'evictions'], last_reviewed: '2026-01-10', created_at: '2026-01-10T00:00:00Z', created_by: 'seed', updated_at: '2026-01-10T00:00:00Z', updated_by: 'seed' },
  { id: 'eks-instability', version: 1, title: 'EKS Instability', slug: 'eks-instability', service: 'Kubernetes / EKS', owner: 'Platform Engineering', category: 'Infrastructure', tags: ['eks', 'kubernetes', 'scaling', 'stability', 'pods'], last_reviewed: '2026-01-03', created_at: '2026-01-03T00:00:00Z', created_by: 'seed', updated_at: '2026-01-03T00:00:00Z', updated_by: 'seed' },
  { id: 'enrolment-spikes', version: 1, title: 'Enrolment Spikes', slug: 'enrolment-spikes', service: 'Enrolment API', owner: 'Enrolment', category: 'Backend', tags: ['enrolment', 'queues', 'scaling', 'throttling', 'backlog'], last_reviewed: '2026-01-09', created_at: '2026-01-09T00:00:00Z', created_by: 'seed', updated_at: '2026-01-09T00:00:00Z', updated_by: 'seed' },
  { id: 'fraud-risk-checks', version: 1, title: 'Fraud & Risk Checks', slug: 'fraud-risk-checks', service: 'CIFAS / AML', owner: 'Risk Ops', category: 'Security', tags: ['fraud', 'cifas', 'aml', 'risk', 'dependencies'], last_reviewed: '2026-01-02', created_at: '2026-01-02T00:00:00Z', created_by: 'seed', updated_at: '2026-01-02T00:00:00Z', updated_by: 'seed' },
  { id: 'rds-connection-storms', version: 1, title: 'RDS Connection Storms', slug: 'rds-connection-storms', service: 'RDS / Aurora', owner: 'Data Services', category: 'Infrastructure', tags: ['rds', 'database', 'connections', 'timeouts', 'pools', 'aurora'], last_reviewed: '2026-01-07', created_at: '2026-01-07T00:00:00Z', created_by: 'seed', updated_at: '2026-01-07T00:00:00Z', updated_by: 'seed' },
];

export async function listKBArticles(params?: {
  search?: string;
  service?: string;
  category?: string;
  cursor?: string;
  limit?: number;
}): Promise<KBListResponse> {
  if (config.localDev) {
    let articles = [...LOCAL_KB_ARTICLES];
    if (params?.category) {
      articles = articles.filter(a => a.category === params.category);
    }
    if (params?.search) {
      const q = params.search.toLowerCase();
      articles = articles.filter(a => a.title.toLowerCase().includes(q) || a.service.toLowerCase().includes(q));
    }
    return { articles, cursor: null };
  }

  const qs = new URLSearchParams();
  if (params?.search) qs.set('search', params.search);
  if (params?.service) qs.set('service', params.service);
  if (params?.category) qs.set('category', params.category);
  if (params?.cursor) qs.set('cursor', params.cursor);
  if (params?.limit) qs.set('limit', String(params.limit));
  const query = qs.toString();
  return request<KBListResponse>(`/kb${query ? `?${query}` : ''}`);
}

export async function getKBArticle(id: string): Promise<KBArticleResponse> {
  if (config.localDev) {
    const article = LOCAL_KB_ARTICLES.find(a => a.id === id);
    return {
      article: {
        ...(article || LOCAL_KB_ARTICLES[0]),
        id: article?.id || id,
        content: `# ${article?.title || id}\n\nThis is a local dev stub for the knowledge base article.\n\n## Symptoms\n\n- Example symptom 1\n- Example symptom 2\n\n## Checks\n\n1. Check service health\n2. Review recent deployments\n\n## Mitigations\n\n- Restart affected pods\n- Roll back recent changes`,
      },
    };
  }

  return request<KBArticleResponse>(`/kb/${id}`);
}

export async function getKBVersions(id: string): Promise<{ versions: KBVersionSummary[] }> {
  if (config.localDev) {
    return { versions: [{ id, version: 1, title: 'Article', updated_at: '2026-01-08T00:00:00Z', updated_by: 'seed', is_latest: 'true' }] };
  }

  return request<{ versions: KBVersionSummary[] }>(`/kb/${id}/versions`);
}

export async function getKBVersion(id: string, version: number): Promise<KBArticleResponse> {
  if (config.localDev) {
    return getKBArticle(id);
  }

  return request<KBArticleResponse>(`/kb/${id}/versions/${version}`);
}

export async function createKBArticle(data: {
  title: string;
  service: string;
  owner: string;
  category?: string;
  tags: string[];
  content: string;
}): Promise<KBArticleResponse> {
  if (config.localDev) {
    return {
      article: {
        id: data.title.toLowerCase().replace(/\s+/g, '-'),
        version: 1,
        title: data.title,
        slug: data.title.toLowerCase().replace(/\s+/g, '-'),
        service: data.service,
        owner: data.owner,
        category: data.category || '',
        tags: data.tags,
        last_reviewed: new Date().toISOString().slice(0, 10),
        content: data.content,
        created_at: new Date().toISOString(),
        created_by: 'local-dev',
        updated_at: new Date().toISOString(),
        updated_by: 'local-dev',
      },
    };
  }

  return request<KBArticleResponse>('/kb', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateKBArticle(id: string, data: {
  title?: string;
  service?: string;
  owner?: string;
  category?: string;
  tags?: string[];
  content?: string;
}): Promise<KBArticleResponse> {
  if (config.localDev) {
    return getKBArticle(id);
  }

  return request<KBArticleResponse>(`/kb/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteKBArticle(id: string): Promise<{ message: string }> {
  if (config.localDev) {
    return { message: `Article ${id} deleted (local dev mode)` };
  }

  return request<{ message: string }>(`/kb/${id}`, {
    method: 'DELETE',
  });
}

// ── Audit API ────────────────────────────────────────────────────

export async function listAuditEntries(params?: {
  user?: string;
  action?: string;
  limit?: number;
  cursor?: string;
}): Promise<AuditListResponse> {
  if (config.localDev) {
    return { entries: [], cursor: null };
  }

  const qs = new URLSearchParams();
  if (params?.user) qs.set('user', params.user);
  if (params?.action) qs.set('action', params.action);
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.cursor) qs.set('cursor', params.cursor);
  const query = qs.toString();
  return request<AuditListResponse>(`/actions/audit${query ? `?${query}` : ''}`);
}

// ── Admin API ─────────────────────────────────────────────────────

export async function listAdminUsers(): Promise<{ users: AdminUser[] }> {
  if (config.localDev) {
    const res = await fetch('/rbac/users.json');
    const data = await res.json();
    const users: AdminUser[] = data.users.map((u: Record<string, unknown>) => ({
      email: u.email as string,
      name: u.name as string,
      role: u.role as string,
      team: u.team as string,
      active: u.active !== false,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    }));
    return { users };
  }

  return request<{ users: AdminUser[] }>('/admin/users');
}

export async function disableAdminUser(email: string): Promise<{ message: string }> {
  if (config.localDev) {
    return { message: `User ${email} disabled (local dev mode)` };
  }

  return request<{ message: string }>(`/admin/users/${encodeURIComponent(email)}/disable`, {
    method: 'POST',
  });
}

export async function enableAdminUser(email: string): Promise<{ message: string }> {
  if (config.localDev) {
    return { message: `User ${email} enabled (local dev mode)` };
  }

  return request<{ message: string }>(`/admin/users/${encodeURIComponent(email)}/enable`, {
    method: 'POST',
  });
}

export async function createAdminUser(data: {
  email: string;
  name: string;
  role: string;
  team: string;
}): Promise<CreateUserResponse> {
  if (config.localDev) {
    return {
      message: `User ${data.email} created (local dev mode)`,
      temporary_password: 'TempPass123!',
    };
  }

  return request<CreateUserResponse>('/admin/users', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function setAdminUserRole(email: string, role: string): Promise<{ message: string }> {
  if (config.localDev) {
    return { message: `User ${email} role changed to ${role} (local dev mode)` };
  }

  return request<{ message: string }>(`/admin/users/${encodeURIComponent(email)}/role`, {
    method: 'POST',
    body: JSON.stringify({ role }),
  });
}

// ── Activity API ─────────────────────────────────────────────────

export async function listActivity(params?: {
  user?: string;
  event_type?: string;
  start?: number;
  end?: number;
  limit?: number;
  cursor?: string;
}): Promise<ActivityListResponse> {
  if (config.localDev) {
    return { events: [], cursor: null };
  }

  const qs = new URLSearchParams();
  if (params?.user) qs.set('user', params.user);
  if (params?.event_type) qs.set('event_type', params.event_type);
  if (params?.start) qs.set('start', String(params.start));
  if (params?.end) qs.set('end', String(params.end));
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.cursor) qs.set('cursor', params.cursor);
  const query = qs.toString();
  return request<ActivityListResponse>(`/activity${query ? `?${query}` : ''}`);
}

export async function getActiveUsers(sinceMinutes = 15): Promise<{ active_users: ActiveUser[] }> {
  if (config.localDev) {
    return { active_users: [] };
  }

  return request<{ active_users: ActiveUser[] }>(`/activity?active=true&since_minutes=${sinceMinutes}`);
}
