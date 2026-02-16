import { config } from '../config';
import { getAccessToken } from './auth';
import type { ExecuteResult, KBListResponse, KBArticleResponse, KBVersionSummary } from '../types';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getAccessToken();
  const res = await fetch(`${config.apiBaseUrl}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `Request failed (${res.status})`);
  }
  return data;
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
