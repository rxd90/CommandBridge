import type { User, ActionPermissions } from '../types';
import { config } from '../config';
import { getAccessToken, getCurrentUser } from './auth';

const ROLE_LEVELS: Record<string, number> = {
  'L1-operator': 1,
  'L2-engineer': 2,
  'L3-admin': 3,
};

const ROLE_LABELS: Record<string, string> = {
  'L1-operator': 'L1 Operator',
  'L2-engineer': 'L2 Engineer',
  'L3-admin': 'L3 Admin',
};

export function getUserRole(user: User | null): string | null {
  if (!user) return null;
  return user.groups[0] || null;
}

export function getRoleLevel(user: User | null): number {
  const role = getUserRole(user);
  if (!role) return 0;
  return ROLE_LEVELS[role] || 0;
}

export function getRoleLabel(user: User | null): string {
  const role = getUserRole(user);
  if (!role) return 'Unknown';
  return ROLE_LABELS[role] || role;
}

export async function getPermissions(): Promise<ActionPermissions> {
  if (!config.localDev && config.apiBaseUrl) {
    const token = getAccessToken();
    const res = await fetch(`${config.apiBaseUrl}/actions/permissions`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) return res.json();
  }

  return getPermissionsLocal();
}

async function getPermissionsLocal(): Promise<ActionPermissions> {
  const token = getAccessToken();
  if (!token) return { actions: [] };

  const user = getCurrentUser();
  const role = getUserRole(user);
  if (!role) return { actions: [] };

  const res = await fetch('/rbac/actions.json');
  const actions = await res.json();

  const result = [];
  for (const [id, action] of Object.entries(actions)) {
    const a = action as Record<string, unknown>;
    const perms = (a.permissions as Record<string, unknown>)?.[role];
    let permission: 'run' | 'request' | 'locked' = 'locked';

    if (perms === '*') {
      permission = 'run';
    } else if (perms && typeof perms === 'object') {
      const p = perms as Record<string, boolean>;
      if (p.run) permission = 'run';
      else if (p.request) permission = 'request';
    }

    result.push({
      id,
      name: a.name as string,
      description: a.description as string,
      risk: a.risk as 'low' | 'medium' | 'high',
      target: a.target as string,
      runbook: a.runbook as string | undefined,
      permission,
    });
  }

  return { actions: result };
}
