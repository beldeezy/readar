import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Session } from '@supabase/supabase-js';
import { supabase } from './supabaseClient';
import { apiClient, getApiBaseUrlDebug } from '../api/client';
import { getAccessToken, setAccessToken, clearAccessToken } from './auth';
import type { User } from '../api/types';

const PENDING_ONBOARDING_KEY = 'readar_pending_onboarding';
const HAS_ONBOARDING_KEY = 'readar_has_onboarding';

interface AuthContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  isAuthenticated: boolean;
  onboardingComplete: boolean | null; // null = unknown/checking, true = complete, false = incomplete
  onboardingChecked: boolean;
  hasVerifiedMagicLink: boolean;
  setHasVerifiedMagicLink: (v: boolean) => void;
  logout: () => Promise<void>;
  refreshOnboardingStatus: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [onboardingComplete, setOnboardingComplete] = useState<boolean | null>(null);
  const [onboardingChecked, setOnboardingChecked] = useState(false);
  const [hasVerifiedMagicLink, setHasVerifiedMagicLink] = useState(false);

  // Fetch full user profile from backend including is_admin
  const fetchUserProfile = React.useCallback(async (baseUser: User) => {
    try {
      const token = getAccessToken();
      if (!token) {
        return { ...baseUser, is_admin: false }; // No token means no verified admin role
      }

      // Fetch full profile from backend
      const fullProfile = await apiClient.getCurrentUser();

      // Merge is_admin into user state
      return {
        ...baseUser,
        is_admin: fullProfile.is_admin === true,
      };
    } catch (err) {
      console.warn('[AuthProvider] Failed to fetch user profile, using base user:', err);
      return { ...baseUser, is_admin: false }; // Fail closed if the role lookup fails
    }
  }, []);

  useEffect(() => {
    let active = true;
    let revision = 0;
    const applySession = (nextSession: Session | null) => {
      if (!active) return;
      const currentRevision = ++revision;
      setSession(nextSession);
      if (nextSession?.access_token) setAccessToken(nextSession.access_token);
      else clearAccessToken();
      if (nextSession?.user) {
        const baseUser: User = {
          id: nextSession.user.id,
          email: nextSession.user.email || '',
          subscription_status: 'free',
          created_at: nextSession.user.created_at,
        };
        // Publish the authenticated identity before loading optional profile
        // details, so the callback cannot send a signed-in reader back to login.
        setUser(baseUser);
        void fetchUserProfile(baseUser).then(fullUser => {
          if (active && revision === currentRevision) setUser(fullUser);
        });
      } else {
        setUser(null);
        setOnboardingComplete(null);
        setOnboardingChecked(false);
        setHasVerifiedMagicLink(false);
      }
      setLoading(false);
    };

    const initialRevision = revision;
    void supabase.auth.getSession().then(({ data: { session } }) => {
      // An auth event is newer than the initial session lookup.
      if (revision === initialRevision) applySession(session);
    }).catch(() => {
      if (revision === initialRevision) applySession(null);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      applySession(session);
    });
    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, [fetchUserProfile]);

  // Check onboarding status function (can be called manually or automatically)
  // Using useCallback to stabilize the function reference
  const checkOnboardingStatus = React.useCallback(async () => {
    if (!user) {
      setOnboardingComplete(null);
      setOnboardingChecked(false);
      return;
    }

    // Only check onboarding if we have an access token
    const token = getAccessToken();
    if (!token) {
      setOnboardingComplete(false);
      setOnboardingChecked(true);
      return;
    }

    // Short-circuit if we already confirmed onboarding exists — avoids a race
    // condition where GET /api/onboarding resolves before a concurrent save finishes.
    const cached = localStorage.getItem(HAS_ONBOARDING_KEY);
    if (cached === '1') {
      setOnboardingComplete(true);
      setOnboardingChecked(true);
      return;
    }

    try {
      setOnboardingChecked(false);

      await apiClient.getOnboarding();

      // If we get here, onboarding exists
      setOnboardingComplete(true);
      setOnboardingChecked(true);
    } catch (err: any) {
      const status = err?.response?.status;

      // 401 means token/session isn't accepted by backend
      if (status === 401) {
        setOnboardingComplete(false);
        setOnboardingChecked(true);
        return;
      }

      // 404 means onboarding truly doesn't exist yet
      if (status === 404) {
        setOnboardingComplete(false);
        setOnboardingChecked(true);
        return;
      }

      // If we got a response but it's 5xx or other errors, treat as UNKNOWN
      if (status && status >= 500) {
        console.error("Backend error while checking onboarding (treating as unknown):", err);
        setOnboardingComplete(null);
        setOnboardingChecked(true);
        return;
      }

      // Network errors / CORS errors: no response object
      if (!err?.response) {
        const debug = getApiBaseUrlDebug();
        console.error(
          `Backend unreachable/CORS while checking onboarding (treating as unknown). Confirm FastAPI is running and CORS allows this origin. (API_BASE_URL=${debug.API_BASE_URL})`,
          err
        );
        setOnboardingComplete(null);
        setOnboardingChecked(true);
        return;
      }

      // Any other non-404/401 HTTP error -> unknown
      setOnboardingComplete(null);
      setOnboardingChecked(true);
    }
  }, [user]);

  // The loading route owns saving pending answers and handling failures. A
  // background save here used to race the callback and discard newer drafts.
  useEffect(() => {
    if (user && localStorage.getItem(PENDING_ONBOARDING_KEY)) {
      setOnboardingComplete(null);
      setOnboardingChecked(false);
      return;
    }
    void checkOnboardingStatus();
  }, [user, checkOnboardingStatus]);

  const logout = async () => {
    await supabase.auth.signOut();
    setUser(null);
    setSession(null);
    setOnboardingComplete(null);
    setOnboardingChecked(false);
    setHasVerifiedMagicLink(false);
    // Clear onboarding cache on logout
    localStorage.removeItem(HAS_ONBOARDING_KEY);
  };

  const isAuthenticated = user !== null;

  return (
    <AuthContext.Provider value={{ user, session, loading, isAuthenticated, onboardingComplete, onboardingChecked, hasVerifiedMagicLink, setHasVerifiedMagicLink, logout, refreshOnboardingStatus: checkOnboardingStatus }}>
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


