import { createContext, useState, useEffect, type ReactNode } from 'react';
import type { User } from '../types';
import * as auth from '../lib/auth';

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
    setUser(auth.getCurrentUser());
    setLoading(false);
  }, []);

  const refreshUser = () => {
    setUser(auth.getCurrentUser());
  };

  const value: AuthContextValue = {
    user,
    loading,
    login: auth.login,
    logout: auth.logout,
    refreshUser,
    getAccessToken: auth.getAccessToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
