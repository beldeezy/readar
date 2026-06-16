import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient, fetchRecommendations, logEvent } from '../api/client';
import type { RecommendationItem, BookPreferenceStatus } from '../api/types';
import RecommendationCard from '../components/RecommendationCard';
import Card from '../components/Card';
import Button from '../components/Button';
import RadarIcon from '../components/RadarIcon';
import { useAuth } from '../auth/AuthProvider';
import './RecommendationsPage.css';

interface BookPitch {
  challenge: string;
  solution: string;
  outcome: string;
}

interface PresentationPitch {
  book_id: string;
  pitch: BookPitch;
}

const PREVIEW_RECS_KEY = 'readar_preview_recs';
const PITCHES_CACHE_KEY = 'readar_pitches_cache';

// Free users get a soft daily refresh allowance; hitting it prompts an upgrade.
// (Client-side metering — fine for validating willingness-to-pay; would move
// server-side before treating it as a hard paywall.)
const FREE_DAILY_REFRESHES = 3;

function refreshCountKey(): string {
  return `readar_refreshes_${new Date().toISOString().slice(0, 10)}`;
}
function getRefreshesUsed(): number {
  try {
    return parseInt(localStorage.getItem(refreshCountKey()) || '0', 10) || 0;
  } catch {
    return 0;
  }
}
function bumpRefreshesUsed(): number {
  const n = getRefreshesUsed() + 1;
  try { localStorage.setItem(refreshCountKey(), String(n)); } catch { /* ignore */ }
  return n;
}

export default function RecommendationsPage() {
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pitches, setPitches] = useState<Record<string, BookPitch>>({});
  const [pitchesLoading, setPitchesLoading] = useState(false);
  const [carouselIndex, setCarouselIndex] = useState(0);
  const [refreshesUsed, setRefreshesUsed] = useState(getRefreshesUsed());
  const [showUpgrade, setShowUpgrade] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user: authUser } = useAuth();

  // Defensive: ProtectedRoute should guarantee auth. Never call navigate during
  // render (breaks the Rules of Hooks) — redirect from an effect instead.
  useEffect(() => {
    if (!authUser) navigate('/login');
  }, [authUser, navigate]);

  useEffect(() => {

    // Liveness check: verify backend is reachable
    const rawBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
    const apiBaseUrl = rawBase.endsWith('/api') ? rawBase : `${rawBase}/api`;

    // Check if we have prefetched recommendations from the loading page
    const prefetchedData = (location.state as any)?.prefetchedRecommendations;

    const prefetchedRecs = Array.isArray(prefetchedData)
      ? prefetchedData as RecommendationItem[]
      : prefetchedData?.items as RecommendationItem[] | undefined;
    const prefetchedRequestId = prefetchedData?.request_id as string | undefined;

    if (prefetchedRecs !== undefined) {
      // Use prefetched results immediately (even if empty array)
      setRecommendations(prefetchedRecs);
      if (prefetchedRequestId) {
        setRequestId(prefetchedRequestId);
      }
      setLoading(false);
      return;
    }

    // Otherwise, check backend health first, then fetch recommendations
    let cancelled = false;

    async function checkHealthAndLoad() {
      // First, check backend health
      try {
        const healthRes = await fetch(`${apiBaseUrl}/health`, {
          method: 'GET',
          credentials: 'include', // Include credentials for CORS
        });
        
        if (!healthRes.ok) {
          throw new Error(`Backend health check failed: ${healthRes.status} ${healthRes.statusText}`);
        }
        
        await healthRes.json();
      } catch (err: any) {
        console.error('[Backend Health] Backend is unreachable:', err);

        // If backend is down, try to fall back to preview recs from localStorage
        const previewRecsStr = localStorage.getItem(PREVIEW_RECS_KEY);
        if (previewRecsStr) {
          try {
            const previewRecs = JSON.parse(previewRecsStr);
            if (!cancelled) {
              setRecommendations(previewRecs);
              setLoading(false);
              // Clear preview recs after using them
              localStorage.removeItem(PREVIEW_RECS_KEY);
            }
            return;
          } catch (parseErr) {
            console.error('Failed to parse preview recs:', parseErr);
          }
        }
        
        if (!cancelled) {
          setError('offline');
          setLoading(false);
        }
        return; // Don't proceed with recommendations fetch if backend is down
      }

      // Backend is healthy, proceed with recommendations
      if (cancelled) return;

      setLoading(true);
      setError(null);

      try {
        const response = await fetchRecommendations({ limit: 5 });
        if (!cancelled) {
          setRecommendations(response.items);
          setRequestId(response.request_id);
          // Clear preview recs if we successfully fetched from backend
          localStorage.removeItem(PREVIEW_RECS_KEY);
        }
      } catch (err: any) {
        if (!cancelled) {
          console.error("[RecommendationsPage] Failed to load recommendations", err);
          
          // Fall back to preview recs if backend errors
          const previewRecsStr = localStorage.getItem(PREVIEW_RECS_KEY);
          if (previewRecsStr) {
            try {
              const previewRecs = JSON.parse(previewRecsStr);
              setRecommendations(previewRecs);
              setLoading(false);
              // Clear preview recs after using them
              localStorage.removeItem(PREVIEW_RECS_KEY);
              return;
            } catch (parseErr) {
              console.error('Failed to parse preview recs:', parseErr);
            }
          }
          
          setError(err?.message || "Failed to fetch recommendations");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    checkHealthAndLoad();

    return () => {
      cancelled = true;
    };
  }, [location.state]);

  // Fetch personalized pitches once recommendations are loaded
  useEffect(() => {
    if (!recommendations.length) return;

    // Check sessionStorage cache first — avoids re-fetching on back-navigation
    const cacheKey = `${PITCHES_CACHE_KEY}_${recommendations.map(r => r.book_id).join(',')}`;
    try {
      const cached = sessionStorage.getItem(cacheKey);
      if (cached) {
        setPitches(JSON.parse(cached));
        return;
      }
    } catch { /* ignore */ }

    let cancelled = false;

    // Resolve pitch context: navigation state → localStorage → stored backend
    // profile. The last fallback is essential for returning users who land here
    // directly (no nav state / local answers) — without it, cards show no pitch.
    const resolveAnswers = async (): Promise<Record<string, any> | null> => {
      const fromState = (location.state as any)?.onboardingAnswers;
      if (fromState) return fromState;
      try {
        const saved = localStorage.getItem('readar_onboarding_answers');
        if (saved) return JSON.parse(saved);
      } catch { /* ignore */ }
      try {
        return await apiClient.getOnboarding();
      } catch {
        return null;
      }
    };

    const fetchPitches = async () => {
      const onboardingAnswers = await resolveAnswers();
      if (cancelled || !onboardingAnswers) return;

      setPitchesLoading(true);
      const pitchMap: Record<string, BookPitch> = {};

      const toBook = (rec: typeof recommendations[0]) => ({
        book_id: rec.book_id,
        title: rec.title,
        author_name: rec.author_name || '',
        promise: rec.promise ?? null,
        best_for: rec.best_for ?? null,
        outcomes: rec.outcomes ?? null,
        description: rec.description ?? null,
      });

      try {
        // Fetch first book immediately so the carousel shows a pitch right away
        const firstResults = await apiClient.getPresentationPitches(
          onboardingAnswers,
          [toBook(recommendations[0])]
        );
        if (cancelled) return;
        for (const item of firstResults) pitchMap[item.book_id] = item.pitch;
        setPitches({ ...pitchMap });
        setPitchesLoading(false);

        // Fetch remaining books in the background
        if (recommendations.length > 1) {
          const restResults = await apiClient.getPresentationPitches(
            onboardingAnswers,
            recommendations.slice(1).map(toBook)
          );
          if (cancelled) return;
          for (const item of restResults) pitchMap[item.book_id] = item.pitch;
          setPitches({ ...pitchMap });
        }

        // Cache complete set for back-navigation
        try {
          sessionStorage.setItem(cacheKey, JSON.stringify(pitchMap));
        } catch { /* ignore quota errors */ }
      } catch (err) {
        console.error('[RecommendationsPage] Failed to fetch pitches:', err);
        if (!cancelled) setPitchesLoading(false);
      }
    };

    fetchPitches();
    return () => { cancelled = true; };
  }, [recommendations]);

  const refreshRecommendations = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchRecommendations({ limit: 5 });
      setRecommendations(response.items);
      setRequestId(response.request_id);
      setCarouselIndex(0);
      setPitches({});
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch recommendations');
    } finally {
      setLoading(false);
    }
  };

  const isPremium = authUser?.subscription_status === 'active';
  const freeRefreshesLeft = Math.max(0, FREE_DAILY_REFRESHES - refreshesUsed);

  // Explicit "Get new recommendations" spin — metered for free users.
  const handleRefreshClick = () => {
    if (isPremium) {
      refreshRecommendations();
      return;
    }
    if (refreshesUsed >= FREE_DAILY_REFRESHES) {
      setShowUpgrade(true);
      logEvent('refresh_limit_hit', { used: refreshesUsed, limit: FREE_DAILY_REFRESHES });
      return;
    }
    const n = bumpRefreshesUsed();
    setRefreshesUsed(n);
    logEvent('refresh_used', { used: n, limit: FREE_DAILY_REFRESHES });
    refreshRecommendations();
  };

  const handleUpgradeClick = () => {
    logEvent('upgrade_prompt_click', { source: 'recommendations_refresh' });
    navigate('/upgrade');
  };

  const handleBookAction = async (
    bookId: string,
    status: BookPreferenceStatus
  ) => {
    // Persist the interaction (the card already wrote book-status + feedback).
    try {
      await apiClient.updateUserBook(bookId, status);
    } catch (err: any) {
      console.error('Failed to update book status:', err);
    }
    // Keep the deck stable and advance to the next book. Only fetch a fresh set
    // once the user has worked through the current recommendations.
    if (carouselIndex >= recommendations.length - 1) {
      refreshRecommendations();
    } else {
      setCarouselIndex((i) => i + 1);
    }
  };

  if (loading) {
    return (
      <div className="readar-recommendations-page">
        <div className="container">
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.25rem' }}>
            <RadarIcon size={96} opacity={0.85} animationDuration={7} />
          </div>
          <h1 className="readar-recommendations-title" style={{
            fontSize: 'var(--rd-font-size-2xl)',
            fontWeight: 600,
            color: 'var(--rd-text)',
            marginBottom: '0.5rem',
            textAlign: 'center'
          }}>
            Your first reading plan
          </h1>
          <p style={{ 
            fontSize: 'var(--rd-font-size-sm)', 
            color: 'var(--rd-muted)',
            marginBottom: '1.5rem'
          }}>
            Finding books that match your stage, goals, and reading history…
          </p>
          {/* Simple skeleton */}
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
            Your recommendations
          </h1>
          <p style={{
            fontSize: 'var(--rd-font-size-sm)',
            color: 'var(--rd-muted)',
            marginBottom: '1.25rem'
          }}>
            We couldn't load your recommendations right now. Please try again in a moment.
          </p>
          <Button variant="primary" onClick={refreshRecommendations} delayMs={0}>
            Try again
          </Button>
        </div>
      </div>
    );
  }

  if (!recommendations.length) {
    return (
      <div className="readar-recommendations-page">
        <div className="container">
          <h1 style={{
            fontSize: 'var(--rd-font-size-2xl)',
            fontWeight: 600,
            color: 'var(--rd-text)',
            marginBottom: '0.5rem'
          }}>
            No recommendations yet
          </h1>
          <p style={{
            fontSize: 'var(--rd-font-size-sm)',
            color: 'var(--rd-muted)',
            marginBottom: '1.5rem',
            maxWidth: '48ch'
          }}>
            We don't have personalized picks for you yet. Mark a few books you've
            read in the Library, or sharpen your focus in your profile, and we'll
            surface the right books.
          </p>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <Button variant="primary" onClick={() => navigate('/library')} delayMs={0}>
              Browse the Library
            </Button>
            <Button variant="secondary" onClick={() => navigate('/profile')} delayMs={0}>
              Update your profile
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const hasPitches = Object.keys(pitches).length > 0;
  const currentBook = recommendations[carouselIndex];
  const currentPitch = currentBook ? pitches[currentBook.book_id] : undefined;

  return (
    <div className="readar-recommendations-page">
      <div className="container">
        <div className="readar-recommendations-header">
          <h1 className="readar-recommendations-title">Your recommendations</h1>
          <p className="readar-recommendations-subtitle">
            {hasPitches
              ? "Here's why each of these books is a strong fit for you."
              : "Based on your stage, focus areas, and reading history."}
          </p>
          {pitchesLoading && (
            <p style={{ fontSize: 'var(--rd-font-size-sm)', color: 'var(--rd-muted)', marginTop: '0.25rem' }}>
              Personalizing your book pitches…
            </p>
          )}
        </div>

        {/* Carousel — one book at a time */}
        <div className="recommendations-carousel">
          <div className="recommendations-carousel__card">
            {currentBook && (
              <RecommendationCard
                key={currentBook.book_id}
                book={currentBook}
                onAction={handleBookAction}
                isTopMatch={carouselIndex === 0}
                requestId={requestId || undefined}
                position={carouselIndex}
                pitch={currentPitch}
                pitchLoading={pitchesLoading}
              />
            )}
          </div>

          <div className="recommendations-carousel__nav">
            <button
              className="recommendations-carousel__btn"
              onClick={() => setCarouselIndex(i => Math.max(0, i - 1))}
              disabled={carouselIndex === 0}
              aria-label="Previous book"
            >
              ←
            </button>

            <div className="recommendations-carousel__dots">
              {recommendations.map((_, i) => (
                <button
                  key={i}
                  className={`recommendations-carousel__dot${i === carouselIndex ? ' recommendations-carousel__dot--active' : ''}`}
                  onClick={() => setCarouselIndex(i)}
                  aria-label={`Book ${i + 1}`}
                />
              ))}
            </div>

            <button
              className="recommendations-carousel__btn"
              onClick={() => setCarouselIndex(i => Math.min(recommendations.length - 1, i + 1))}
              disabled={carouselIndex === recommendations.length - 1}
              aria-label="Next book"
            >
              →
            </button>
          </div>

          <div className="recommendations-carousel__refresh">
            {showUpgrade ? (
              <div className="recommendations-upgrade-prompt">
                <p className="recommendations-upgrade-text">
                  You've used today's free refreshes. Upgrade to Premium for unlimited recommendations.
                </p>
                <div className="recommendations-upgrade-actions">
                  <Button variant="primary" size="sm" onClick={handleUpgradeClick} delayMs={0}>
                    Upgrade to Premium
                  </Button>
                  <button className="recommendations-refresh-btn" onClick={() => setShowUpgrade(false)}>
                    Maybe later
                  </button>
                </div>
              </div>
            ) : (
              <div className="recommendations-refresh-wrap">
                <button
                  className="recommendations-refresh-btn"
                  onClick={handleRefreshClick}
                  aria-label="Get new recommendations"
                >
                  ↻ Get new recommendations
                </button>
                {!isPremium && (
                  <span className="recommendations-refresh-hint">
                    {freeRefreshesLeft > 0
                      ? `${freeRefreshesLeft} free ${freeRefreshesLeft === 1 ? 'refresh' : 'refreshes'} left today`
                      : 'No free refreshes left today'}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

