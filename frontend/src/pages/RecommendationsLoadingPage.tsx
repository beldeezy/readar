import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchRecommendations, apiClient } from '../api/client';
import type { RecommendationItem, OnboardingPayload } from '../api/types';
import { setPostAuthRedirect } from '../auth/postAuthRedirect';
import { useAuth } from '../auth/AuthProvider';
import RadarIcon from '../components/RadarIcon';
import './RecommendationsPage.css';

const PENDING_ONBOARDING_KEY = 'readar_pending_onboarding';
const PREVIEW_RECS_KEY = 'readar_preview_recs';

export default function RecommendationsLoadingPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<"fetching" | "finalizing">("fetching");

  const { user: authUser, refreshOnboardingStatus } = useAuth();

  const limitParam = searchParams.get('limit');
  const limit = limitParam ? parseInt(limitParam, 10) : 5;

  // Keep latest refresh function without making it a dependency that can re-trigger the main effect
  const refreshRef = useRef(refreshOnboardingStatus);
  useEffect(() => {
    refreshRef.current = refreshOnboardingStatus;
  }, [refreshOnboardingStatus]);

  // Guard to prevent spam/re-runs
  const lastRunKeyRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    async function run() {
      try {
        console.log("RecommendationsLoadingPage mounted");

        const pendingOnboardingStr = localStorage.getItem(PENDING_ONBOARDING_KEY);
        const userId = authUser?.id ?? "anon";

        // Build a run key based on the only things that should change the flow
        const runKey = `${userId}|limit=${limit}|pending=${pendingOnboardingStr ? "1" : "0"}`;

        // If we already ran this exact scenario, do nothing
        if (lastRunKeyRef.current === runKey) {
          return;
        }
        lastRunKeyRef.current = runKey;

        // If we have pending onboarding but authUser is not yet populated, give it a beat.
        // (Prevents bouncing into preview/login flow repeatedly while auth is settling.)
        if (pendingOnboardingStr && !authUser) {
          // If you have a visible "Logout" etc, authUser should exist soon; wait briefly once.
          await sleep(300);
          if (cancelled) return;

          const stillNoUser = !authUser; // note: authUser closure won't update; this is just a small delay guard
          // Continue into preview flow if still no user after a short delay
        }

        // CASE 1: pending exists AND NOT authenticated => preview flow => login
        if (pendingOnboardingStr && !authUser) {
          try {
            const pendingOnboarding = JSON.parse(pendingOnboardingStr);

            const payload: OnboardingPayload = {
              ...pendingOnboarding,
              business_model: pendingOnboarding.business_models?.join(', ') || pendingOnboarding.business_model || '',
              biggest_challenge: pendingOnboarding.challenges_and_blockers || pendingOnboarding.biggest_challenge || '',
              blockers: pendingOnboarding.challenges_and_blockers || pendingOnboarding.blockers || '',
              book_preferences: pendingOnboarding.book_preferences || [],
            } as OnboardingPayload;

            const recs = await apiClient.getPreviewRecommendations(payload);

            if (cancelled) return;

            localStorage.setItem(PREVIEW_RECS_KEY, JSON.stringify(recs));
            setPhase("finalizing");

            await sleep(7000);
            if (cancelled) return;

            setPostAuthRedirect('/recommendations');
            navigate('/login');
            return;
          } catch (e: any) {
            if (cancelled) return;
            setError(e?.message || "Failed to generate preview recommendations.");
            return;
          }
        }

        // CASE 2: authenticated AND pending exists => finalize pending into backend, then fetch real recs
        if (pendingOnboardingStr && authUser) {
          try {
            const pendingOnboarding = JSON.parse(pendingOnboardingStr);

            const payload: OnboardingPayload = {
              ...pendingOnboarding,
              business_model: pendingOnboarding.business_models?.join(', ') || pendingOnboarding.business_model || '',
              biggest_challenge: pendingOnboarding.challenges_and_blockers || pendingOnboarding.biggest_challenge || '',
              blockers: pendingOnboarding.challenges_and_blockers || pendingOnboarding.blockers || '',
              book_preferences: pendingOnboarding.book_preferences || [],
            } as OnboardingPayload;

            // Save once to backend now that we have auth
            await apiClient.saveOnboarding(payload);

            // Refresh onboarding status (do not depend on function identity)
            await refreshRef.current();

            // Clear pending + preview recs so we don't loop
            localStorage.removeItem(PENDING_ONBOARDING_KEY);
            localStorage.removeItem(PREVIEW_RECS_KEY);

            const response = await fetchRecommendations({ limit });
            if (cancelled) return;

            setPhase("finalizing");
            await sleep(7000);
            if (cancelled) return;

            navigate(`/recommendations`, { state: { prefetchedRecommendations: response } });
            return;
          } catch (e: any) {
            if (cancelled) return;
            setError(e?.message || "Failed to finalize onboarding and fetch recommendations.");
            return;
          }
        }

        // CASE 3: no pending => normal authed flow
        try {
          const response = await fetchRecommendations({ limit });
          if (cancelled) return;

          setPhase("finalizing");
          await sleep(7000);
          if (cancelled) return;

          navigate(`/recommendations`, { state: { prefetchedRecommendations: response } });
        } catch (e: any) {
          if (cancelled) return;
          setError(e?.message || "Failed to generate recommendations.");
        }
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message || "Failed to generate recommendations.");
      }
    }

    run();

    return () => {
      cancelled = true;
    };
  }, [limit, authUser?.id, navigate]);

  if (error) {
    return (
      <div className="readar-recommendations-page">
        <div className="container">
          <h1 style={{
            fontSize: 'var(--rd-font-size-2xl)',
            fontWeight: 600,
            color: 'var(--rd-text)',
            marginBottom: '0.5rem'
          }}>
            Error loading recommendations
          </h1>
          <p style={{
            fontSize: 'var(--rd-font-size-sm)',
            color: 'var(--readar-warm)'
          }}>
            {error}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="readar-recommendations-page">
      <div className="container">
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          marginBottom: '2rem'
        }}>
          <RadarIcon size={120} opacity={0.8} animationDuration={8} />
          <h1 style={{
            fontSize: 28,
            fontWeight: 700,
            color: 'var(--rd-text)',
            marginTop: '1.5rem',
            marginBottom: '0.5rem'
          }}>
            Scanning your next reads…
          </h1>
        </div>

        {phase === "fetching" && (
          <p style={{
            fontSize: 'var(--rd-font-size-sm)',
            color: 'var(--rd-muted)',
            marginBottom: '1.5rem',
            textAlign: 'center'
          }}>
            Analyzing your inputs…
          </p>
        )}

        {phase === "finalizing" && (
          <p style={{
            fontSize: 'var(--rd-font-size-sm)',
            color: 'var(--rd-muted)',
            marginBottom: '1.5rem',
            textAlign: 'center'
          }}>
            Finalizing your recommendations…
          </p>
        )}

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: '1rem',
          marginTop: '1.5rem'
        }}>
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
