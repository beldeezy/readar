import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchRecommendations, apiClient, logEvent } from '../api/client';
import type { OnboardingPayload, RecommendationsResponse, RecommendationItem } from '../api/types';
import { setPostAuthRedirect } from '../auth/postAuthRedirect';
import { useAuth } from '../auth/AuthProvider';
import { withTimeout } from '../utils/withTimeout';
import RadarIcon from '../components/RadarIcon';
import './RecommendationsPage.css';

const PENDING_ONBOARDING_KEY = 'readar_pending_onboarding';
const PREVIEW_RECS_KEY = 'readar_preview_recs';
const HAS_ONBOARDING_KEY = 'readar_has_onboarding';

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

  const { user: authUser, loading: authLoading, refreshOnboardingStatus } = useAuth();
  const [attempt, setAttempt] = useState(0);
  const parsedLimit = Number(searchParams.get('limit') || 5);
  const limit = Number.isFinite(parsedLimit) ? Math.min(5, Math.max(1, Math.floor(parsedLimit))) : 5;
  const userId = authUser?.id;
  const refreshRef = useRef(refreshOnboardingStatus);
  refreshRef.current = refreshOnboardingStatus;

  type Result =
    | { kind: 'preview'; items: RecommendationItem[] }
    | { kind: 'saved' | 'existing'; recommendations: RecommendationsResponse };
  // StrictMode replays effects. Share the work, but give each effect its own
  // subscription: cleanup detaches the old subscriber, never the replacement.
  const requestRef = useRef<{ key: string; promise: Promise<Result> } | null>(null);

  useEffect(() => {
    if (authLoading) return;
    let active = true;
    const pending = localStorage.getItem(PENDING_ONBOARDING_KEY);
    if (!pending && !userId) {
      navigate('/onboarding', { replace: true });
      return;
    }
    const key = JSON.stringify([userId, limit, pending, attempt]);
    setError(null);
    setPhase('fetching');

    async function request(): Promise<Result> {
      const started = performance.now();
      try {
        if (pending) {
          const payload = normalizePendingOnboardingToPayload(JSON.parse(pending));
          if (!userId) {
            const items = await withTimeout(apiClient.getPreviewRecommendations(payload), 20000,
              'Finding your books is taking longer than expected. Your answers are saved. Please try again.');
            if (!Array.isArray(items) || items.length === 0) {
              throw new Error('We could not find your books yet. Your answers are saved. Try again or adjust your answers.');
            }
            return { kind: 'preview', items };
          }
          // This page owns finalization. Never discard the draft on a failed save
          // or fetch, and do not skip updated answers for an existing account.
          await withTimeout(apiClient.saveOnboarding(payload), 20000,
            'Saving your answers is taking longer than expected. Please try again.');
        }
        const recommendations = await withTimeout(fetchRecommendations({ limit }), 20000,
          'Finding your books is taking longer than expected. Please try again.');
        if (!Array.isArray(recommendations?.items) || recommendations.items.length === 0) {
          throw new Error('We could not find your books yet. Your answers are saved. Try again or adjust your answers.');
        }
        return { kind: pending ? 'saved' : 'existing', recommendations };
      } finally {
        console.info('[RecommendationsLoading] Request finished', {
          flow: userId ? 'authenticated' : 'preview', duration_ms: Math.round(performance.now() - started),
        });
      }
    }

    if (requestRef.current?.key !== key) requestRef.current = { key, promise: request() };
    void requestRef.current.promise.then(result => {
      if (!active) return;
      // Another tab or a newer onboarding conversation must not be overwritten.
      if (localStorage.getItem(PENDING_ONBOARDING_KEY) !== pending) {
        setAttempt(value => value + 1);
        return;
      }
      setPhase('finalizing');
      if (result.kind === 'preview') {
        localStorage.setItem(PREVIEW_RECS_KEY, JSON.stringify(result.items));
        void logEvent('onboarding_signin_prompted', { has_preview: true });
        setPostAuthRedirect('/recommendations/loading');
        navigate('/login', { replace: true });
      } else {
        if (result.kind === 'saved') {
          localStorage.removeItem(PENDING_ONBOARDING_KEY);
          localStorage.removeItem(PREVIEW_RECS_KEY);
          localStorage.setItem(HAS_ONBOARDING_KEY, '1');
          // A status refresh must not block delivery of already fetched books.
          void refreshRef.current();
        }
        navigate(result.kind === 'saved' ? '/onboarding/import' : '/recommendations', {
          state: { prefetchedRecommendations: result.recommendations }, replace: true,
        });
      }
      console.info('[RecommendationsLoading] Handoff complete', { flow: result.kind });
    }).catch(cause => {
      if (!active) return;
      console.error('[RecommendationsLoading] Handoff failed', cause);
      const message = cause instanceof Error && /Your answers|taking longer|Saving your answers/.test(cause.message)
        ? cause.message : "We couldn't load your books just now. Your answers are saved. Please try again.";
      setError(message);
    });
    return () => { active = false; };
  }, [authLoading, userId, limit, attempt, navigate]);

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
                setAttempt(value => value + 1);
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
              Try again
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
