import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchRecommendations, apiClient } from '../api/client';
import type { OnboardingPayload } from '../api/types';
import { setPostAuthRedirect } from '../auth/postAuthRedirect';
import { useAuth } from '../auth/AuthProvider';
import RadarIcon from '../components/RadarIcon';
import PrimaryButton from '../components/PrimaryButton';
import './RecommendationsPage.css';

const PENDING_ONBOARDING_KEY = 'readar_pending_onboarding';
const PREVIEW_RECS_KEY = 'readar_preview_recs';
const HAS_ONBOARDING_KEY = 'readar_has_onboarding';
const PREVIEW_READY_KEY = 'readar_preview_ready';
const PREVIEW_ONBOARDING_KEY = 'readar_preview_onboarding';

async function withTimeout<T>(promise: Promise<T>, ms: number, message: string): Promise<T> {
  const timeoutPromise = new Promise<T>((_, reject) =>
    setTimeout(() => reject(new Error(message)), ms)
  );
  return Promise.race([promise, timeoutPromise]);
}

function normalizePendingOnboardingToPayload(pendingOnboarding: any): OnboardingPayload {
  return {
    ...pendingOnboarding,

    // Backend expects business_model as a string
    business_model: Array.isArray(pendingOnboarding.business_models)
      ? pendingOnboarding.business_models.join(', ')
      : (pendingOnboarding.business_model || ''),

    // Backend expects biggest_challenge as a string
    biggest_challenge:
      pendingOnboarding.biggest_challenge ||
      pendingOnboarding.challenges_and_blockers ||
      '',

    // Backend expects blockers as a string
    blockers:
      pendingOnboarding.blockers ||
      pendingOnboarding.challenges_and_blockers ||
      '',

    // Backend expects book_preferences as an array
    book_preferences: Array.isArray(pendingOnboarding.book_preferences)
      ? pendingOnboarding.book_preferences
      : [],
  } as OnboardingPayload;
}

export default function RecommendationsLoadingPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<'fetching' | 'finalizing'>('fetching');
  const [status, setStatus] = useState<'loading' | 'error'>('loading');

  const { user: authUser, hasVerifiedMagicLink, setHasVerifiedMagicLink, refreshOnboardingStatus } =
    useAuth();

  const limitParam = searchParams.get('limit');
  const limit = limitParam ? parseInt(limitParam, 10) : 5;

  // Keep latest refresh function without making it a dependency that can re-trigger the main effect
  const refreshRef = useRef(refreshOnboardingStatus);
  useEffect(() => {
    refreshRef.current = refreshOnboardingStatus;
  }, [refreshOnboardingStatus]);

  // Guard to prevent spam/re-runs
  const lastRunKeyRef = useRef<string | null>(null);
  // Guard to prevent repeat preview requests
  const startedRef = useRef(false);

  // Helper to check whether onboarding exists for the authenticated user
  // SKIP this entirely when pending onboarding exists (preview flow)
  async function checkExistingOnboarding(): Promise<boolean> {
    const pendingOnboardingStr = localStorage.getItem(PENDING_ONBOARDING_KEY);
    // DO NOT call /onboarding endpoint when pending onboarding exists
    if (pendingOnboardingStr) {
      return false;
    }

    const cached = localStorage.getItem(HAS_ONBOARDING_KEY);
    if (cached === '1') return true;

    try {
      await apiClient.getOnboarding(); // GET /api/onboarding (auth required)
      localStorage.setItem(HAS_ONBOARDING_KEY, '1');
      return true;
    } catch (e: any) {
      const status = e?.response?.status;
      if (status === 404) {
        localStorage.removeItem(HAS_ONBOARDING_KEY);
        return false;
      }
      throw e;
    }
  }

  useEffect(() => {
    let cancelled = false;

    const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    async function run() {
      try {
        console.log('RecommendationsLoadingPage mounted');

        const pendingOnboardingStr = localStorage.getItem(PENDING_ONBOARDING_KEY);
        
        // EARLY RETURN: If pending onboarding exists AND user is NOT verified, ONLY run preview flow - NO onboarding API calls
        // This prevents /api/onboarding calls during preview flow
        if (pendingOnboardingStr && (!authUser || (authUser && !hasVerifiedMagicLink))) {
          // Guard to prevent repeat requests
          if (startedRef.current) return;
          startedRef.current = true;

          try {
            setStatus('loading');
            setError(null);
            setPhase('fetching');

            const pendingOnboarding = JSON.parse(pendingOnboardingStr);
            const payload = normalizePendingOnboardingToPayload(pendingOnboarding);

            // Generate preview recommendations (works without auth) - call exactly once
            const recs = await withTimeout(
              apiClient.getPreviewRecommendations(payload),
              20000,
              'Fetching preview recommendations took too long. Backend may be down or stuck.'
            );
            if (cancelled) return;

            // Store preview results and markers
            localStorage.setItem(PREVIEW_RECS_KEY, JSON.stringify(recs));
            localStorage.setItem(PREVIEW_READY_KEY, 'true');
            localStorage.setItem(PREVIEW_ONBOARDING_KEY, pendingOnboardingStr);
            setPhase('finalizing');

            await sleep(1200);
            if (cancelled) return;

            // After preview is ready, redirect to login
            navigate(`/login?next=${encodeURIComponent('/recommendations')}`);
            return;
          } catch (e: any) {
            if (cancelled) return;
            setStatus('error');
            setError(e?.message || 'Failed to generate preview recommendations.');
            // Reset startedRef so "Try again" can work
            startedRef.current = false;
            return;
          }
        }

        // If no pending onboarding, reset startedRef for next time
        startedRef.current = false;

        const runKey = `${userId}|limit=${limit}|pending=0`;
        if (lastRunKeyRef.current === runKey) return;
        lastRunKeyRef.current = runKey;

        // Check if we can skip magic link verification (user already has onboarding in backend)
        // NOTE: This only runs when NO pending onboarding exists
        let canSkipMagicLink = false;

        if (authUser && !hasVerifiedMagicLink) {
          try {
            canSkipMagicLink = await checkExistingOnboarding();
            if (canSkipMagicLink && typeof setHasVerifiedMagicLink === 'function') {
              setHasVerifiedMagicLink(true);
            }
          } catch (e: any) {
            const status = e?.response?.status;
            if (status === 401) throw e;

            if (
              !e?.response ||
              String(e?.message || '').includes('timeout') ||
              String(e?.message || '').includes('timed out')
            ) {
              setError('Backend unavailable or not responding. Confirm backend is running and DATABASE_URL is set.');
              return;
            }
            throw e;
          }
        }

        // CASE 2: authenticated AND pending exists AND (verified OR can skip) => finalize pending into backend, then fetch real recs
        // NOTE: This case should only run AFTER user has verified via magic link (after auth callback)
        // During preview flow, this should NOT run - the early return above prevents it
        const currentPendingOnboardingStr = localStorage.getItem(PENDING_ONBOARDING_KEY);
        if (currentPendingOnboardingStr && authUser && (hasVerifiedMagicLink || canSkipMagicLink)) {
          try {
            const pendingOnboarding = JSON.parse(currentPendingOnboardingStr);
            const payload = normalizePendingOnboardingToPayload(pendingOnboarding);

            await withTimeout(
              apiClient.saveOnboarding(payload),
              20000,
              'Saving onboarding took too long. Backend may be down or stuck.'
            );

            // Only refresh onboarding status if no pending onboarding exists (to avoid calling /onboarding during preview)
            const stillPending = localStorage.getItem(PENDING_ONBOARDING_KEY);
            if (!stillPending) {
              await refreshRef.current?.();
            }

            localStorage.removeItem(PENDING_ONBOARDING_KEY);
            localStorage.removeItem(PREVIEW_RECS_KEY);
            localStorage.removeItem(PREVIEW_READY_KEY);
            localStorage.removeItem(PREVIEW_ONBOARDING_KEY);
            localStorage.setItem(HAS_ONBOARDING_KEY, '1');

            const recs = await withTimeout(
              fetchRecommendations({ limit }),
              20000,
              'Fetching recommendations took too long. Backend may be down or stuck.'
            );
            if (cancelled) return;

            setPhase('finalizing');
            await sleep(900);
            if (cancelled) return;

            navigate('/recommendations', { state: { prefetchedRecommendations: recs } });
            return;
          } catch (e: any) {
            if (cancelled) return;
            if (
              !e?.response ||
              String(e?.message || '').includes('timeout') ||
              String(e?.message || '').includes('timed out')
            ) {
              setError('Backend unavailable or not responding. Confirm backend is running and DATABASE_URL is set.');
            } else {
              setError(e?.message || 'Failed to finalize onboarding and fetch recommendations.');
            }
            return;
          }
        }

        // If user is authenticated but not magic-link-verified AND no pending onboarding, send to onboarding
        if (!pendingOnboardingStr && authUser && !hasVerifiedMagicLink && !canSkipMagicLink) {
          navigate('/onboarding');
          return;
        }

        // If no pending onboarding and not authenticated, send to onboarding
        if (!pendingOnboardingStr && !authUser) {
          navigate('/onboarding');
          return;
        }

        // CASE 3: no pending => normal authenticated flow
        try {
          const recs = await withTimeout(
            fetchRecommendations({ limit }),
            20000,
            'Fetching recommendations took too long. Backend may be down or stuck.'
          );
          if (cancelled) return;

          setPhase('finalizing');
          await sleep(900);
          if (cancelled) return;

          navigate('/recommendations', { state: { prefetchedRecommendations: recs } });
          return;
        } catch (e: any) {
          if (cancelled) return;
          if (
            !e?.response ||
            String(e?.message || '').includes('timeout') ||
            String(e?.message || '').includes('timed out')
          ) {
            setError('Backend unavailable or not responding. Confirm backend is running and DATABASE_URL is set.');
          } else {
            setError(e?.message || 'Failed to generate recommendations.');
          }
          return;
        }
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message || 'Failed to generate recommendations.');
      }
    }

    run();

    return () => {
      cancelled = true;
    };
  }, [limit, navigate, authUser, hasVerifiedMagicLink, setHasVerifiedMagicLink]);

  const handleTryAgain = () => {
    setError(null);
    setStatus('loading');
    startedRef.current = false;
    // Trigger re-run by clearing lastRunKey
    lastRunKeyRef.current = null;
  };

  if (status === 'error' && error) {
    return (
      <div className="readar-recommendations-page">
        <div className="container">
          <h1
            style={{
              fontSize: 'var(--rd-font-size-2xl)',
              fontWeight: 600,
              color: 'var(--rd-text)',
              marginBottom: '0.5rem',
            }}
          >
            Couldn't generate recommendations
          </h1>
          <p style={{ fontSize: 'var(--rd-font-size-sm)', color: 'var(--readar-warm)', marginBottom: '1.5rem' }}>
            {error}
          </p>
          <PrimaryButton onClick={handleTryAgain}>
            Try again
          </PrimaryButton>
        </div>
      </div>
    );
  }

  return (
    <div className="readar-recommendations-page">
      <div className="container">
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            marginBottom: '2rem',
          }}
        >
          <RadarIcon size={120} opacity={0.8} animationDuration={8} />
          <h1
            style={{
              fontSize: 28,
              fontWeight: 700,
              color: 'var(--rd-text)',
              marginTop: '1.5rem',
              marginBottom: '0.5rem',
            }}
          >
            Scanning your next reads…
          </h1>
        </div>

        {phase === 'fetching' && (
          <p
            style={{
              fontSize: 'var(--rd-font-size-sm)',
              color: 'var(--rd-muted)',
              marginBottom: '1.5rem',
              textAlign: 'center',
            }}
          >
            Analyzing your inputs…
          </p>
        )}

        {phase === 'finalizing' && (
          <p
            style={{
              fontSize: 'var(--rd-font-size-sm)',
              color: 'var(--rd-muted)',
              marginBottom: '1.5rem',
              textAlign: 'center',
            }}
          >
            Finalizing your recommendations…
          </p>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: '1rem',
            marginTop: '1.5rem',
          }}
        >
          {[...Array(6)].map((_, i) => (
            <div
              key={i}
              style={{
                height: '200px',
                borderRadius: 'var(--rd-radius-lg)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                backgroundColor: 'var(--rd-surface)',
                opacity: 0.6,
                animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
