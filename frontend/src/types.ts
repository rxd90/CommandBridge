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
  category?: KBCategory;
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
