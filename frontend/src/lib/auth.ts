import { signOut as amplifySignOut } from 'aws-amplify/auth';
import { config } from '../config';
import type { User, LocalDevUser } from '../types';

const SESSION_KEY = 'cb_session';

// --- Session ---

interface Session {
  access_token?: string;
  id_token?: string;
  refresh_token?: string;
  expires_at?: number;
  // Local dev fields
  email?: string;
  name?: string;
  role?: string;
}

function getSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const session: Session = JSON.parse(raw);
    if (session.expires_at && Date.now() > session.expires_at) {
      sessionStorage.removeItem(SESSION_KEY);
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

export function setSession(data: Session): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
}

function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY);
}

// --- Public API ---

export function isAuthenticated(): boolean {
  return getSession() !== null;
}

export function getCurrentUser(): User | null {
  const session = getSession();
  if (!session) return null;

  if (config.localDev) {
    return {
      email: session.email || '',
      name: session.name || '',
      groups: [session.role || ''],
    };
  }

  try {
    const payload = JSON.parse(atob(session.id_token!.split('.')[1]));
    return {
      email: payload.email || payload['cognito:username'],
      name: payload.name || payload.email,
      groups: payload['cognito:groups'] || [],
    };
  } catch {
    return null;
  }
}

export function getAccessToken(): string | null {
  const session = getSession();
  if (!session) return null;
  if (config.localDev) return 'local-dev-token';
  // Use id_token — it contains email and cognito:groups claims.
  // The access_token only has username/sub, so the backend can't resolve the user.
  return session.id_token || session.access_token || null;
}

export async function login(): Promise<void> {
  window.location.href = '/login';
}

export async function logout(): Promise<void> {
  clearSession();

  if (!config.localDev) {
    try { await amplifySignOut(); } catch { /* ignore */ }
  }

  window.location.href = '/login';
}

export function localDevLogin(user: LocalDevUser): void {
  setSession({
    email: user.email,
    name: user.name,
    role: user.role,
    expires_at: Date.now() + 8 * 60 * 60 * 1000,
  });
  window.location.href = '/';
}
