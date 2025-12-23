import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiClient } from '../api/client';
import type { User } from '../api/types';
import { AUTH_DISABLED, TEST_USER } from '../config/auth';
import { clearAccessToken } from '../auth/auth';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // TEMP: If auth is disabled, always use test user
    if (AUTH_DISABLED) {
      setUser(TEST_USER);
      setLoading(false);
      return;
    }

    // Try to restore session on mount
    const token = localStorage.getItem('access_token');
    if (token) {
      apiClient
        .getCurrentUser()
        .then(setUser)
        .catch(() => {
          localStorage.removeItem('access_token');
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    // TEMP: Skip real login when auth is disabled
    if (AUTH_DISABLED) {
      setUser(TEST_USER);
      return;
    }

    try {
      // TODO: Implement login when auth is re-enabled
      // await apiClient.login(email, password);
      const currentUser = await apiClient.getCurrentUser();
      setUser(currentUser);
    } catch (error) {
      // Re-throw to let the calling component handle it
      throw error;
    }
  };

  const signup = async (email: string, password: string) => {
    // TEMP: Skip real signup when auth is disabled
    if (AUTH_DISABLED) {
      setUser(TEST_USER);
      return;
    }

    try {
      // TODO: Implement signup when auth is re-enabled
      // await apiClient.signup(email, password);
      const currentUser = await apiClient.getCurrentUser();
      setUser(currentUser);
    } catch (error) {
      // Re-throw to let the calling component handle it
      throw error;
    }
  };

  const logout = () => {
    // TEMP: When auth is disabled, logout just clears the test user
    if (AUTH_DISABLED) {
      setUser(null);
      return;
    }

    // TODO: Implement logout when auth is re-enabled
    // apiClient.logout();
    clearAccessToken();
    setUser(null);
  };

  const isAuthenticated = user !== null;

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

