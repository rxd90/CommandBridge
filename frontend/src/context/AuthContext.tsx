import { createContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { User } from '../types';
import * as auth from '../lib/auth';
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
    const currentUser = auth.getCurrentUser();
    setUser(currentUser);
    setLoading(false);

    if (currentUser) {
      initActivityTracker();
    }

    return () => stopActivityTracker();
  }, []);

  const refreshUser = () => {
    setUser(auth.getCurrentUser());
  };

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
