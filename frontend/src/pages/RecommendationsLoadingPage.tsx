import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchRecommendations, apiClient } from '../api/client';
import type { OnboardingPayload } from '../api/types';
import { setPostAuthRedirect } from '../auth/postAuthRedirect';
import { useAuth } from '../auth/AuthProvider';
import RadarIcon from '../components/RadarIcon';
import './RecommendationsPage.css';

const PENDING_ONBOARDING_KEY = 'readar_pending_onboarding';
const PREVIEW_RECS_KEY = 'readar_preview_recs';
const HAS_ONBOARDING_KEY = 'readar_has_onboarding';

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

  const { user: authUser, hasVerifiedMagicLink, setHasVerifiedMagicLink, refreshOnboardingStatus } = useAuth();

  const limitParam = searchParams.get('limit');
  const limit = limitParam ? parseInt(limitParam, 10) : 5;

  // Keep latest refresh function without making it a dependency that can re-trigger the main effect
  const refreshRef = useRef(refreshOnboardingStatus);
  useEffect(() => {
    refreshRef.current = refreshOnboardingStatus;
  }, [refreshOnboardingStatus]);

  // Guard to prevent spam/re-runs
  const lastRunKeyRef = useRef<string | null>(null);

  // Helper to check whether onboarding exists for the authenticated user
  async function checkExistingOnboarding(): Promise<boolean> {
    // Check localStorage cache first (optional optimization)
    const cached = localStorage.getItem(HAS_ONBOARDING_KEY);
    if (cached === '1') {
      return true;
    }
    
    try {
      await apiClient.getOnboarding(); // GET /api/onboarding (auth required)
      // Cache the result
      localStorage.setItem(HAS_ONBOARDING_KEY, '1');
      return true; // 200 => onboarding exists
    } catch (e: any) {
      const status = e?.response?.status;
      if (status === 404) {
        // Clear cache if onboarding doesn't exist
        localStorage.removeItem(HAS_ONBOARDING_KEY);
        return false; // onboarding not created yet
      }
      // If 401 or network error, rethrow so we surface a real error/redirect
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
        const userId = authUser?.id ?? 'anon';

        // Build a run key based on the only things that should change the flow
        const runKey = `${userId}|limit=${limit}|pending=${pendingOnboardingStr ? '1' : '0'}`;

        // If we already ran this exact scenario, do nothing
        if (lastRunKeyRef.current === runKey) return;
        lastRunKeyRef.current = runKey;

        // Check if we can skip magic link verification (user already has onboarding in backend)
        let canSkipMagicLink = false;

        if (authUser && !hasVerifiedMagicLink) {
          try {
            canSkipMagicLink = await checkExistingOnboarding();
            // Optional: if onboarding exists, treat this as verified for the rest of this session to avoid re-checks
            if (canSkipMagicLink && typeof setHasVerifiedMagicLink === "function") {
              setHasVerifiedMagicLink(true);
            }
          } catch (e: any) {
            // If auth is invalid, let existing client interceptor handle redirect on 401.
            // For network/other errors, fall through to error handling below.
            // We'll just keep canSkipMagicLink false and let later calls fail with a useful message.
            const status = e?.response?.status;
            if (status === 401) {
              // Auth invalid - let interceptor handle it
              throw e;
            }
            // For network/timeout errors, show helpful message
            if (!e?.response || String(e?.message || '').includes('timeout') || String(e?.message || '').includes('timed out')) {
              setError('Backend unavailable or not responding. Confirm backend is running and DATABASE_URL is set.');
              return;
            }
            // Other errors - let them bubble up
            throw e;
          }
        }

        // CASE 1: pending exists AND NOT authenticated => preview flow => login
        if (pendingOnboardingStr && !authUser) {
          try {
            const pendingOnboarding = JSON.parse(pendingOnboardingStr);
            const payload = normalizePendingOnboardingToPayload(pendingOnboarding);

            const recs = await withTimeout(
              apiClient.getPreviewRecommendations(payload),
              20000,
              'Fetching preview recommendations took too long. Backend may be down or stuck.'
            );
            if (cancelled) return;

            localStorage.setItem(PREVIEW_RECS_KEY, JSON.stringify(recs));
            setPhase('finalizing');

            // Hold loading page a bit so it feels intentional
            await sleep(1200);
            if (cancelled) return;

            setPostAuthRedirect('/recommendations');
            navigate('/login');
            return;
          } catch (e: any) {
            if (cancelled) return;
            setError(e?.message || 'Failed to generate preview recommendations.');
            return;
          }
        }

        // Force login when user is authenticated but not verified AND cannot skip (no existing onboarding)
        if (pendingOnboardingStr && authUser && !hasVerifiedMagicLink && !canSkipMagicLink) {
          setPostAuthRedirect('/recommendations');
          navigate('/login');
          return;
        }

        // CASE 2: authenticated AND pending exists AND (verified OR can skip) => finalize pending into backend, then fetch real recs
        if (pendingOnboardingStr && authUser && (hasVerifiedMagicLink || canSkipMagicLink)) {
          try {
            const pendingOnboarding = JSON.parse(pendingOnboardingStr);
            const payload = normalizePendingOnboardingToPayload(pendingOnboarding);

            // Save once to backend now that we have auth
            await withTimeout(
              apiClient.saveOnboarding(payload),
              20000,
              'Saving onboarding took too long. Backend may be down or stuck.'
            );

            // Refresh auth/onboarding state (use ref to avoid effect dependency loops)
            await refreshRef.current?.();

            // Clear pending + preview recs so we don't loop
            localStorage.removeItem(PENDING_ONBOARDING_KEY);
            localStorage.removeItem(PREVIEW_RECS_KEY);
            // Mark onboarding as existing in cache
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
            // Improve error messaging for network/timeout errors
            if (!e?.response || String(e?.message || '').includes('timeout') || String(e?.message || '').includes('timed out')) {
              setError('Backend unavailable or not responding. Confirm backend is running and DATABASE_URL is set.');
            } else {
              setError(e?.message || 'Failed to finalize onboarding and fetch recommendations.');
            }
            return;
          }
        }

        // If user is authenticated but not magic-link-verified AND onboarding does not exist yet, require login
        if (!pendingOnboardingStr && authUser && !hasVerifiedMagicLink && !canSkipMagicLink) {
          setPostAuthRedirect('/recommendations');
          navigate('/login');
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
          // Improve error messaging for network/timeout errors
          if (!e?.response || String(e?.message || '').includes('timeout') || String(e?.message || '').includes('timed out')) {
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
  }, [limit, navigate, authUser]);

  if (error) {
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
            Error loading recommendations
          </h1>
          <p style={{ fontSize: 'var(--rd-font-size-sm)', color: 'var(--readar-warm)' }}>
            {error}
          </p>
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

        {/* Simple skeleton */}
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
