import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Session, User as SupabaseUser } from '@supabase/supabase-js';
import { supabase } from './supabaseClient';
import { apiClient, getApiBaseUrlDebug } from '../api/client';
import { getAccessToken } from './auth';
import type { User, OnboardingPayload } from '../api/types';

const PENDING_ONBOARDING_KEY = 'readar_pending_onboarding';
const PREVIEW_RECS_KEY = 'readar_preview_recs';
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

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      if (session?.user) {
        setUser({
          id: session.user.id,
          email: session.user.email || '',
          subscription_status: 'free',
          created_at: session.user.created_at,
        });
      }
      setLoading(false);
    });

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      if (session?.user) {
        setUser({
          id: session.user.id,
          email: session.user.email || '',
          subscription_status: 'free',
          created_at: session.user.created_at,
        });
      } else {
        setUser(null);
        setOnboardingComplete(null);
        setOnboardingChecked(false);
        setHasVerifiedMagicLink(false);
      }
      setLoading(false);
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

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

  // Finalize pending onboarding after login
  useEffect(() => {
    const finalizePendingOnboarding = async () => {
      if (!user) {
        return;
      }

      // Only check if we have an access token
      const token = getAccessToken();
      if (!token) {
        return;
      }

      // If user just authenticated and we have pending onboarding, finalize it once.
      const pending = localStorage.getItem(PENDING_ONBOARDING_KEY);
      if (pending) {
        try {
          const parsed = JSON.parse(pending);

          // Map pending payload to backend expected shape (match what RecommendationsLoadingPage does)
          const payload: OnboardingPayload = {
            ...parsed,
            business_model: parsed.business_models?.join(', ') || parsed.business_model || '',
            biggest_challenge: parsed.challenges_and_blockers || parsed.biggest_challenge || '',
            blockers: parsed.challenges_and_blockers || parsed.blockers || '',
            book_preferences: parsed.book_preferences || [],
          } as OnboardingPayload;

          await apiClient.saveOnboarding(payload);

          // ✅ Clear pending so we don't loop
          localStorage.removeItem(PENDING_ONBOARDING_KEY);

          // ✅ Mark onboarded locally to prevent redirect back
          setOnboardingComplete(true);
          
          // Refresh onboarding status to confirm it's saved
          await checkOnboardingStatus();
        } catch (e) {
          console.error("Failed to finalize pending onboarding after login", e);
          // leave pending for retry, but DO NOT redirect to onboarding endlessly
          // Still check onboarding status in case it was saved by another process
          checkOnboardingStatus();
        }
      } else {
        // No pending onboarding, just check status normally
        checkOnboardingStatus();
      }
    };

    if (user) {
      finalizePendingOnboarding();
    } else {
      setOnboardingComplete(null);
    }
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


