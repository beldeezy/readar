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
  // Guard to prevent navigation from being called multiple times
  const hasNavigatedRef = useRef<boolean>(false);
  // Track which effect run we're in (for debugging race conditions)
  const runIdRef = useRef<number>(0);

  // Helper to check whether onboarding exists for the authenticated user
  async function checkExistingOnboarding(): Promise<boolean> {
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
    const currentRunId = ++runIdRef.current;

    const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    async function run() {
      try {
        console.log(`[RecommendationsLoading] Effect run #${currentRunId} starting`);

        const pendingOnboardingStr = localStorage.getItem(PENDING_ONBOARDING_KEY);
        const userId = authUser?.id ?? 'anon';

        const runKey = `${userId}|limit=${limit}|pending=${pendingOnboardingStr ? '1' : '0'}`;
        if (lastRunKeyRef.current === runKey) {
          console.log(`[RecommendationsLoading] Run #${currentRunId} skipping (duplicate key: ${runKey})`);
          return;
        }
        lastRunKeyRef.current = runKey;
        console.log(`[RecommendationsLoading] Run #${currentRunId} executing for key: ${runKey}`);

        // Check if we can skip magic link verification (user already has onboarding in backend)
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

        // CASE 1: pending exists AND NOT authenticated => preview flow => login
        if (pendingOnboardingStr && !authUser) {
          try {
            const pendingOnboarding = JSON.parse(pendingOnboardingStr);
            const payload = normalizePendingOnboardingToPayload(pendingOnboarding);

            console.log('[RecommendationsLoading] Fetching preview recommendations...');
            const recs = await withTimeout(
              apiClient.getPreviewRecommendations(payload),
              20000,
              'Fetching preview recommendations took too long. Backend may be down or stuck.'
            );
            if (cancelled) return;

            const itemCount = Array.isArray(recs) ? recs.length : 0;
            console.log(`[RecommendationsLoading] Received ${itemCount} preview recommendations, navigating to login`);

            localStorage.setItem(PREVIEW_RECS_KEY, JSON.stringify(recs));
            setPhase('finalizing');

            await sleep(1200);
            if (cancelled) return;

            setPostAuthRedirect('/recommendations');
            navigate('/login');
            return;
          } catch (e: any) {
            if (cancelled) return;
            console.error('[RecommendationsLoading] Error generating preview recommendations:', e);
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

            await withTimeout(
              apiClient.saveOnboarding(payload),
              20000,
              'Saving onboarding took too long. Backend may be down or stuck.'
            );

            await refreshRef.current?.();

            localStorage.removeItem(PENDING_ONBOARDING_KEY);
            localStorage.removeItem(PREVIEW_RECS_KEY);
            localStorage.setItem(HAS_ONBOARDING_KEY, '1');

            console.log('[RecommendationsLoading] Fetching recommendations after onboarding save...');
            const recs = await withTimeout(
              fetchRecommendations({ limit }),
              20000,
              'Fetching recommendations took too long. Backend may be down or stuck.'
            );

            const itemCount = recs?.items?.length ?? 0;
            console.log(`[RecommendationsLoading] Run #${currentRunId} received ${itemCount} recommendations`);

            // Check if already navigated
            if (hasNavigatedRef.current) {
              console.log(`[RecommendationsLoading] Run #${currentRunId} - already navigated, skipping`);
              return;
            }

            // Mark navigation intent IMMEDIATELY, before ANY state updates or checks that could trigger cleanup
            hasNavigatedRef.current = true;

            if (cancelled) {
              console.log(`[RecommendationsLoading] Run #${currentRunId} - cancelled=true but hasNavigated=true, proceeding anyway`);
              // Still navigate since we marked intent - don't let cancellation block us
            }

            console.log(`[RecommendationsLoading] Run #${currentRunId} calling navigate() now...`);

            // Navigate immediately - no state updates, no delays, no animation
            navigate('/recommendations', { state: { prefetchedRecommendations: recs }, replace: true });
            console.log(`[RecommendationsLoading] Run #${currentRunId} navigate() succeeded`);
            return;
          } catch (e: any) {
            if (cancelled) {
              console.log('[RecommendationsLoading] Cancelled after error');
              return;
            }
            console.error('[RecommendationsLoading] Error:', e);
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

        // If user is authenticated but not magic-link-verified AND onboarding does not exist yet, require login
        if (!pendingOnboardingStr && authUser && !hasVerifiedMagicLink && !canSkipMagicLink) {
          setPostAuthRedirect('/recommendations');
          navigate('/login');
          return;
        }

        // CASE 3: no pending => normal authenticated flow
        try {
          console.log('[RecommendationsLoading] Fetching recommendations (normal flow)...');
          const recs = await withTimeout(
            fetchRecommendations({ limit }),
            20000,
            'Fetching recommendations took too long. Backend may be down or stuck.'
          );

          const itemCount = recs?.items?.length ?? 0;
          console.log(`[RecommendationsLoading] Run #${currentRunId} received ${itemCount} recommendations`);

          // Check if already navigated (prevent duplicate navigations in StrictMode)
          if (hasNavigatedRef.current) {
            console.log(`[RecommendationsLoading] Run #${currentRunId} - already navigated, skipping`);
            return;
          }

          // Mark navigation intent IMMEDIATELY, before ANY state updates or checks that could trigger cleanup
          hasNavigatedRef.current = true;

          if (cancelled) {
            console.log(`[RecommendationsLoading] Run #${currentRunId} - cancelled=true but hasNavigated=true, proceeding anyway`);
            // Still navigate since we marked intent - don't let cancellation block us
          }

          console.log(`[RecommendationsLoading] Run #${currentRunId} calling navigate() now...`);

          // Navigate immediately - no state updates, no delays, no animation
          navigate('/recommendations', { state: { prefetchedRecommendations: recs }, replace: true });
          console.log(`[RecommendationsLoading] Run #${currentRunId} navigate() succeeded`);
          return;
        } catch (e: any) {
          if (cancelled) {
            console.log('[RecommendationsLoading] Cancelled after error');
            return;
          }
          console.error('[RecommendationsLoading] Error:', e);
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
      console.log(`[RecommendationsLoading] Cleanup for run #${currentRunId}, setting cancelled=true`);
      cancelled = true;
    };
  }, [limit, navigate, authUser?.id, hasVerifiedMagicLink, setHasVerifiedMagicLink]);

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
          <p style={{ fontSize: 'var(--rd-font-size-sm)', color: 'var(--readar-warm)', marginBottom: '1.5rem' }}>{error}</p>
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
            <button
              onClick={() => {
                setError(null);
                setPhase('fetching');
                window.location.reload();
              }}
              style={{
                padding: '0.75rem 1.5rem',
                backgroundColor: 'var(--readar-mint)',
                color: 'var(--rd-surface)',
                border: 'none',
                borderRadius: 'var(--rd-radius-md)',
                fontSize: 'var(--rd-font-size-base)',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              Retry
            </button>
            <button
              onClick={() => navigate('/onboarding')}
              style={{
                padding: '0.75rem 1.5rem',
                backgroundColor: 'transparent',
                color: 'var(--rd-text)',
                border: '1px solid var(--rd-border)',
                borderRadius: 'var(--rd-radius-md)',
                fontSize: 'var(--rd-font-size-base)',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              Back to Onboarding
            </button>
          </div>
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
