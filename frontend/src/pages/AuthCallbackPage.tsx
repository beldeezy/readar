import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { supabase } from '../auth/supabaseClient';
import { apiClient } from '../api/client';
import { setAccessToken, clearAccessToken } from '../auth/auth';
import { popPostAuthRedirect } from '../auth/postAuthRedirect';
import { useAuth } from '../auth/AuthProvider';
import type { OnboardingPayload } from '../api/types';
import Card from '../components/Card';
import './AuthPage.css';

const PENDING_ONBOARDING_KEY = 'readar_pending_onboarding';
const PREVIEW_RECS_KEY = 'readar_preview_recs';
const HAS_ONBOARDING_KEY = 'readar_has_onboarding';
const PENDING_CSV_KEY = 'readar_pending_csv';

export default function AuthCallbackPage() {
  const [status, setStatus] = useState<'checking' | 'success' | 'error'>('checking');
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const authContext = useAuth();

  useEffect(() => {
    const handleAuthCallback = async () => {
      try {
        // Check if we have an OAuth code parameter (Google OAuth flow)
        const code = searchParams.get('code');
        let session = null;
        let error = null;

        if (code) {
          // Exchange the OAuth code for a session
          const { data, error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
          session = data.session;
          error = exchangeError;
        } else {
          // Fallback: Get the session from the URL hash (magic link flow)
          const { data, error: sessionError } = await supabase.auth.getSession();
          session = data.session;
          error = sessionError;
        }

        if (error) {
          console.error('Auth callback error:', error);
          clearAccessToken();
          setStatus('error');
          setTimeout(() => navigate('/login'), 2000);
          return;
        }

        if (session?.access_token) {
          // Store access token in localStorage
          setAccessToken(session.access_token);

          // Mark magic link verified for this session
          authContext.setHasVerifiedMagicLink(true);

          setStatus('success');

          // Set up auth state change listener to keep token updated
          supabase.auth.onAuthStateChange((_event, session) => {
            if (session?.access_token) {
              setAccessToken(session.access_token);
            } else {
              clearAccessToken();
            }
          });

          // Check if there's pending onboarding in localStorage
          const pendingOnboardingStr = localStorage.getItem(PENDING_ONBOARDING_KEY);
          let hadPendingOnboarding = false;
          if (pendingOnboardingStr) {
            hadPendingOnboarding = true;
            try {
              const pendingOnboarding = JSON.parse(pendingOnboardingStr);

              // Map form data to backend payload format
              const payload: OnboardingPayload = {
                ...pendingOnboarding,
                business_model: pendingOnboarding.business_models?.join(', ') || pendingOnboarding.business_model || '',
                biggest_challenge: pendingOnboarding.challenges_and_blockers || pendingOnboarding.biggest_challenge || '',
                blockers: pendingOnboarding.challenges_and_blockers || pendingOnboarding.blockers || '',
                book_preferences: pendingOnboarding.book_preferences || [],
              } as OnboardingPayload;

              // Persist onboarding to backend
              await apiClient.saveOnboarding(payload);
              console.log("Persisted pending onboarding to backend");

              // Clear pending onboarding and set cache so AuthProvider skips the
              // GET /api/onboarding race condition on first load.
              localStorage.removeItem(PENDING_ONBOARDING_KEY);
              localStorage.setItem(HAS_ONBOARDING_KEY, '1');
            } catch (err: any) {
              console.error("Failed to persist pending onboarding:", err);
              // Continue anyway - user can complete onboarding later
            }
          }

          // Upload any CSV reading history the user attached during onboarding
          const pendingCsvStr = localStorage.getItem(PENDING_CSV_KEY);
          if (pendingCsvStr) {
            try {
              const { name, data } = JSON.parse(pendingCsvStr);
              const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0));
              const csvFile = new File([bytes], name, { type: 'text/csv' });
              await apiClient.uploadReadingHistoryCsv(csvFile);
              console.log('Uploaded pending reading history CSV');
            } catch (err) {
              console.error('Failed to upload pending CSV:', err);
            } finally {
              localStorage.removeItem(PENDING_CSV_KEY);
            }
          }

          // Get stored redirect path, fall back to next param
          let target = popPostAuthRedirect() || searchParams.get('next');

          if (hadPendingOnboarding) {
            // Onboarding was just completed pre-auth and saved above. Offer the
            // optional Goodreads import as the final step before recommendations
            // (peak buy-in), overriding any stored redirect.
            target = '/onboarding/import';
          } else if (!target) {
            // No redirect specified — route by the user's actual onboarding status.
            if (localStorage.getItem(HAS_ONBOARDING_KEY) === '1') {
              target = '/recommendations';
            } else {
              try {
                // Returning users have an onboarding profile on the backend.
                await apiClient.getOnboarding();
                localStorage.setItem(HAS_ONBOARDING_KEY, '1');
                target = '/recommendations';
              } catch {
                // No profile yet (404) — send new users to onboarding.
                const hasPreview = !!localStorage.getItem(PREVIEW_RECS_KEY);
                target = hasPreview ? '/recommendations' : '/onboarding';
              }
            }
          }

          navigate(target, { replace: true });
        } else {
          clearAccessToken();
          setStatus('error');
          setTimeout(() => navigate('/login'), 2000);
        }
      } catch (err) {
        console.error('Unexpected error in auth callback:', err);
        clearAccessToken();
        setStatus('error');
        setTimeout(() => navigate('/login'), 2000);
      }
    };

    handleAuthCallback();
  }, [navigate, searchParams]);

  return (
    <div className="readar-auth-page">
      <Card variant="elevated" className="readar-auth-card">
        <h1 className="readar-auth-title">
          {status === 'checking' && 'Signing you in...'}
          {status === 'success' && 'Success! Redirecting...'}
          {status === 'error' && 'Authentication failed. Redirecting to login...'}
        </h1>
      </Card>
    </div>
  );
}


