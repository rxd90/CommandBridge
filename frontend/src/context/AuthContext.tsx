import { createContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { User } from '../types';
import * as auth from '../lib/auth';
import { fetchMe } from '../lib/api';
import { initActivityTracker, stopActivityTracker, trackEvent } from '../lib/activity';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: () => Promise<void>;
  logout: () => void;
  refreshUser: () => void;
  getAccessToken: () => string | null;
}

export const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
  refreshUser: () => {},
  getAccessToken: () => null,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function init() {
      const currentUser = auth.getCurrentUser();
      if (!currentUser) {
        setUser(null);
        setLoading(false);
        return;
      }

      try {
        const me = await fetchMe();
        setUser({
          email: currentUser.email,
          name: me.name || currentUser.name,
          role: me.role,
        });
      } catch (err) {
        // If /me fails, set user with empty role (denied by RBAC checks)
        console.warn('[AuthContext] /me failed – role unavailable:', err instanceof Error ? err.message : err);
        setUser({
          email: currentUser.email,
          name: currentUser.name,
          role: '',
        });
      }

      setLoading(false);
      initActivityTracker();
    }

    init();
    return () => stopActivityTracker();
  }, []);

  const refreshUser = useCallback(async () => {
    const currentUser = auth.getCurrentUser();
    if (!currentUser) {
      setUser(null);
      return;
    }
    try {
      const me = await fetchMe();
      setUser({
        email: currentUser.email,
        name: me.name || currentUser.name,
        role: me.role,
      });
    } catch (err) {
      console.warn('[AuthContext] /me refresh failed:', err instanceof Error ? err.message : err);
      setUser({
        email: currentUser.email,
        name: currentUser.name,
        role: '',
      });
    }
  }, []);

  const handleLogout = useCallback(() => {
    trackEvent('logout');
    stopActivityTracker();
    auth.logout();
  }, []);

  const value: AuthContextValue = {
    user,
    loading,
    login: auth.login,
    logout: handleLogout,
    refreshUser,
    getAccessToken: auth.getAccessToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
