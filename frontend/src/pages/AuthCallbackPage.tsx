import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { supabase } from '../auth/supabaseClient';
import { apiClient } from '../api/client';
import { setAccessToken, clearAccessToken } from '../auth/auth';
import { popPostAuthRedirect } from '../auth/postAuthRedirect';
import type { OnboardingPayload } from '../api/types';
import Card from '../components/Card';
import './AuthPage.css';

const PENDING_ONBOARDING_KEY = 'readar_pending_onboarding';
const PREVIEW_RECS_KEY = 'readar_preview_recs';

export default function AuthCallbackPage() {
  const [status, setStatus] = useState<'checking' | 'success' | 'error'>('checking');
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const handleAuthCallback = async () => {
      try {
        // Get the session from the URL hash
        const { data: { session }, error } = await supabase.auth.getSession();

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
          if (pendingOnboardingStr) {
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
              
              // Clear pending onboarding from localStorage
              localStorage.removeItem(PENDING_ONBOARDING_KEY);
            } catch (err: any) {
              console.error("Failed to persist pending onboarding:", err);
              // Continue anyway - user can complete onboarding later
            }
          }
          
          // Get stored redirect path, fall back to next param
          let target = popPostAuthRedirect() || searchParams.get('next');
          
          // If no redirect specified, check if we have preview recs
          if (!target) {
            const hasPreview = !!localStorage.getItem(PREVIEW_RECS_KEY);
            target = hasPreview ? '/recommendations' : '/onboarding';
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


