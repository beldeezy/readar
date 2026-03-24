import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient, fetchRecommendations } from '../api/client';
import type { RecommendationItem, BookPreferenceStatus } from '../api/types';
import RecommendationCard from '../components/RecommendationCard';
import Card from '../components/Card';
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

export default function RecommendationsPage() {
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pitches, setPitches] = useState<Record<string, BookPitch>>({});
  const [pitchesLoading, setPitchesLoading] = useState(false);
  const [carouselIndex, setCarouselIndex] = useState(0);
  const navigate = useNavigate();
  const location = useLocation();
  const { user: authUser } = useAuth();
  
  if (!authUser) {
    // This should not happen as ProtectedRoute should handle it, but just in case
    navigate('/login');
    return null;
  }

  useEffect(() => {
    console.log('[RecommendationsPage] Mounted/re-rendered');

    // Liveness check: verify backend is reachable
    const rawBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
    const apiBaseUrl = rawBase.endsWith('/api') ? rawBase : `${rawBase}/api`;

    // Check if we have prefetched recommendations from the loading page
    const prefetchedData = (location.state as any)?.prefetchedRecommendations;
    console.log('[RecommendationsPage] Checking for prefetched data:', {
      hasPrefetchedData: !!prefetchedData,
      isArray: Array.isArray(prefetchedData),
      hasItems: prefetchedData?.items !== undefined,
    });

    const prefetchedRecs = Array.isArray(prefetchedData)
      ? prefetchedData as RecommendationItem[]
      : prefetchedData?.items as RecommendationItem[] | undefined;
    const prefetchedRequestId = prefetchedData?.request_id as string | undefined;

    if (prefetchedRecs !== undefined) {
      // Use prefetched results immediately (even if empty array)
      const itemCount = prefetchedRecs?.length ?? 0;
      console.log(`[RecommendationsPage] Using prefetched recommendations: ${itemCount} items`);
      setRecommendations(prefetchedRecs);
      if (prefetchedRequestId) {
        setRequestId(prefetchedRequestId);
      }
      setLoading(false);
      console.log('[RecommendationsPage] Prefetch complete, will render empty state or items');
      return;
    }

    console.log('[RecommendationsPage] No prefetched data, will check backend health');

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
        
        const healthData = await healthRes.json();
        console.log('[Backend Health] Backend is reachable:', healthData);
      } catch (err: any) {
        console.error('[Backend Health] Backend is unreachable:', err);
        const errorMsg = err?.message || 'Unknown error';
        
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
          setError(
            `Backend is offline (${errorMsg}). Please ensure FastAPI is running. ` +
            `API_BASE_URL=${apiBaseUrl}. Check browser console for details.`
          );
          setLoading(false);
        }
        return; // Don't proceed with recommendations fetch if backend is down
      }

      // Backend is healthy, proceed with recommendations
      if (cancelled) return;

      setLoading(true);
      setError(null);

      try {
        console.log('[RecommendationsPage] Fetching recommendations from backend...');
        const response = await fetchRecommendations({ limit: 5 });
        if (!cancelled) {
          const itemCount = response?.items?.length ?? 0;
          console.log(`[RecommendationsPage] Received ${itemCount} recommendations from backend`);
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

    // Use answers from navigation state, or fall back to localStorage (direct navigation)
    const onboardingAnswers =
      (location.state as any)?.onboardingAnswers ||
      (() => {
        try {
          const saved = localStorage.getItem('readar_onboarding_answers');
          return saved ? JSON.parse(saved) : null;
        } catch { return null; }
      })();
    if (!onboardingAnswers) return; // No answers available — skip pitches

    const fetchPitches = async () => {
      setPitchesLoading(true);
      try {
        const booksForPitch = recommendations.map((rec) => ({
          book_id: rec.book_id,
          title: rec.title,
          author_name: rec.author_name || '',
          promise: rec.promise ?? null,
          best_for: rec.best_for ?? null,
          outcomes: rec.outcomes ?? null,
          description: rec.description ?? null,
        }));

        const results = await apiClient.getPresentationPitches(onboardingAnswers, booksForPitch);
        const pitchMap: Record<string, BookPitch> = {};
        for (const item of results) {
          pitchMap[item.book_id] = item.pitch;
        }
        setPitches(pitchMap);
        // Cache for this session so back-navigation restores pitches instantly
        try {
          sessionStorage.setItem(cacheKey, JSON.stringify(pitchMap));
        } catch { /* ignore quota errors */ }
      } catch (err) {
        console.error('[RecommendationsPage] Failed to fetch pitches:', err);
        // Non-fatal — page still works without pitches
      } finally {
        setPitchesLoading(false);
      }
    };

    fetchPitches();
  }, [recommendations]);

  const handleBookAction = async (
    bookId: string,
    status: BookPreferenceStatus
  ) => {
    try {
      await apiClient.updateUserBook(bookId, status);
      // Optionally refresh recommendations or update UI
      const response = await fetchRecommendations({ limit: 5 });
      setRecommendations(response.items);
      setRequestId(response.request_id);
    } catch (err: any) {
      console.error('Failed to update book status:', err);
    }
  };

  if (loading) {
    return (
      <div className="readar-recommendations-page">
        <div className="container">
          <h1 className="readar-recommendations-title" style={{ 
            fontSize: 'var(--rd-font-size-2xl)', 
            fontWeight: 600, 
            color: 'var(--rd-text)',
            marginBottom: '0.5rem'
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
            color: 'var(--readar-warm)'
          }}>
            {error}
          </p>
        </div>
      </div>
    );
  }

  if (!recommendations.length) {
    console.log('[RecommendationsPage] Rendering empty state (0 recommendations)');
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
            marginBottom: '1rem'
          }}>
            Your catalog appears to be empty. To get personalized recommendations:
          </p>
          <ul style={{
            fontSize: 'var(--rd-font-size-sm)',
            color: 'var(--rd-muted)',
            paddingLeft: '1.5rem',
            listStyle: 'disc'
          }}>
            <li>Add books to your catalog (run seed script if in development)</li>
            <li>Rate books you&apos;ve read to improve recommendations</li>
            <li>Upload your reading history for better personalization</li>
          </ul>
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
        </div>
      </div>
    </div>
  );
}

