export interface User {
  email: string;
  name: string;
  groups: string[];
}

export interface LocalDevUser {
  id: string;
  name: string;
  email: string;
  role: string;
  team: string;
  active: boolean;
}

export interface Action {
  id: string;
  name: string;
  description: string;
  risk: 'low' | 'medium' | 'high';
  target: string;
  runbook?: string;
  categories?: KBCategory[];
  permission: 'run' | 'request' | 'locked';
}

export interface ActionPermissions {
  actions: Action[];
}

export interface ExecuteResult {
  message: string;
  status?: string;
  result?: Record<string, unknown>;
}

export type KBCategory = 'Frontend' | 'Backend' | 'Infrastructure' | 'Security';

export interface KBArticle {
  id: string;
  version: number;
  title: string;
  slug: string;
  service: string;
  owner: string;
  category: string;
  tags: string[];
  last_reviewed: string;
  content?: string;
  created_at: string;
  created_by: string;
  updated_at: string;
  updated_by: string;
  is_latest?: string;
}

export interface KBListResponse {
  articles: KBArticle[];
  cursor: string | null;
}

export interface KBArticleResponse {
  article: KBArticle;
}

export interface KBVersionSummary {
  id: string;
  version: number;
  title: string;
  updated_at: string;
  updated_by: string;
  is_latest?: string;
}

export interface AuditEntry {
  id: string;
  timestamp: number;
  user: string;
  action: string;
  target: string;
  ticket: string;
  result: string;
  approved_by?: string;
  details?: Record<string, unknown>;
}

export interface AuditListResponse {
  entries: AuditEntry[];
  cursor: string | null;
}

export interface AdminUser {
  email: string;
  name: string;
  role: string;
  team: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateUserResponse {
  message: string;
  temporary_password: string;
}

export interface ActivityEvent {
  user: string;
  timestamp: number;
  event_type: string;
  data?: Record<string, unknown>;
}

export interface ActivityListResponse {
  events: ActivityEvent[];
  cursor: string | null;
}

export interface ActiveUser {
  user: string;
  last_seen: number;
}
