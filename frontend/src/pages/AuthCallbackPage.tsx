import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { Session } from '@supabase/supabase-js';
import { supabase } from '../auth/supabaseClient';
import { apiClient } from '../api/client';
import { setAccessToken } from '../auth/auth';
import { popPostAuthRedirect, safeReturnPath } from '../auth/postAuthRedirect';
import { useAuth } from '../auth/AuthProvider';
import { withTimeout } from '../utils/withTimeout';
import Card from '../components/Card';
import './AuthPage.css';

const PENDING_ONBOARDING_KEY = 'readar_pending_onboarding';
const HAS_ONBOARDING_KEY = 'readar_has_onboarding';
const PENDING_CSV_KEY = 'readar_pending_csv';

export default function AuthCallbackPage() {
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setHasVerifiedMagicLink } = useAuth();
  const code = searchParams.get('code');
  const next = searchParams.get('next');
  // OAuth codes can be exchanged only once. Effect replay subscribes to the
  // same exchange, and only the currently mounted subscriber can navigate.
  const sessionRef = useRef<{ code: string | null; promise: Promise<Session> } | null>(null);

  useEffect(() => {
    let active = true;
    setError(false);
    if (!sessionRef.current || sessionRef.current.code !== code) {
      const promise = (async () => {
        const { data, error: authError } = await withTimeout(
          code ? supabase.auth.exchangeCodeForSession(code) : supabase.auth.getSession(),
          20000, 'Sign-in timed out.');
        if (authError || !data.session?.access_token) throw authError || new Error('No session');
        return data.session;
      })();
      sessionRef.current = { code, promise };
    }

    async function finish() {
      try {
        const session = await sessionRef.current!.promise;
        if (!active) return;
        setAccessToken(session.access_token);
        setHasVerifiedMagicLink(true);

        // Preserve support for reading history attached by older clients. Never
        // clear a failed upload, or let it prevent an actionable error state.
        const pendingCsv = localStorage.getItem(PENDING_CSV_KEY);
        if (pendingCsv) {
          const { name, data } = JSON.parse(pendingCsv);
          const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0));
          await withTimeout(apiClient.uploadReadingHistoryCsv(new File([bytes], name, { type: 'text/csv' })),
            120000, 'Reading history upload timed out.');
          if (!active) return;
          if (localStorage.getItem(PENDING_CSV_KEY) === pendingCsv) localStorage.removeItem(PENDING_CSV_KEY);
        }

        if (localStorage.getItem(PENDING_ONBOARDING_KEY)) {
          popPostAuthRedirect();
          navigate('/recommendations/loading', { replace: true });
          return;
        }
        let target = safeReturnPath(popPostAuthRedirect()) || safeReturnPath(next);
        if (!target) {
          if (localStorage.getItem(HAS_ONBOARDING_KEY) === '1') {
            target = '/reading';
          } else {
            try {
              await withTimeout(apiClient.getOnboarding(), 20000, 'Checking your answers timed out.');
              if (!active) return;
              localStorage.setItem(HAS_ONBOARDING_KEY, '1');
              target = '/reading';
            } catch (cause: any) {
              if (cause?.response?.status !== 404) throw cause;
              target = '/onboarding';
            }
          }
        }
        if (active) navigate(target, { replace: true });
      } catch (cause) {
        if (!active) return;
        console.error('[AuthCallback] Could not finish sign-in', cause);
        setError(true);
      }
    }
    void finish();
    return () => { active = false; };
  }, [code, next, navigate, setHasVerifiedMagicLink, attempt]);

  return (
    <div className="readar-auth-page">
      <Card variant="elevated" className="readar-auth-card">
        <h1 className="readar-auth-title">{error ? "We couldn't finish signing you in" : 'Signing you in...'}</h1>
        {error && <>
          <p>Your onboarding answers are still saved.</p>
          <button onClick={() => setAttempt(value => value + 1)}>Try again</button>
          <button onClick={() => navigate('/login', { replace: true })}>Back to sign in</button>
        </>}
      </Card>
    </div>
  );
}
