import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient, fetchRecommendations, API_BASE_URL } from '../api/client';
import type { RecommendationItem, BookPreferenceStatus } from '../api/types';
import RecommendationCard from '../components/RecommendationCard';
import Card from '../components/Card';
import { useAuth } from '../auth/AuthProvider';
import './RecommendationsPage.css';

const PREVIEW_RECS_KEY = 'readar_preview_recs';
const PREVIEW_READY_KEY = 'readar_preview_ready';
const PREVIEW_ONBOARDING_KEY = 'readar_preview_onboarding';

export default function RecommendationsPage() {
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { user: authUser } = useAuth();
  
  if (!authUser) {
    // This should not happen as ProtectedRoute should handle it, but just in case
    navigate('/login');
    return null;
  }

  useEffect(() => {
    // Check if we have prefetched recommendations from the loading page
    const prefetchedData = (location.state as any)?.prefetchedRecommendations;
    const prefetchedRecs = Array.isArray(prefetchedData) 
      ? prefetchedData as RecommendationItem[]
      : prefetchedData?.items as RecommendationItem[] | undefined;
    const prefetchedRequestId = prefetchedData?.request_id as string | undefined;
    
    if (prefetchedRecs) {
      // Use prefetched results immediately
      setRecommendations(prefetchedRecs);
      if (prefetchedRequestId) {
        setRequestId(prefetchedRequestId);
      }
      setLoading(false);
      return;
    }

    // Check for preview recommendations in localStorage (from preview flow)
    const previewRecsStr = localStorage.getItem(PREVIEW_RECS_KEY);
    const previewReady = localStorage.getItem(PREVIEW_READY_KEY) === 'true';
    
    if (previewRecsStr && previewReady) {
      try {
        const previewRecs = JSON.parse(previewRecsStr);
        // Show preview recs immediately (fast win)
        setRecommendations(previewRecs);
        setLoading(false);
        
        // Then fetch authenticated recommendations in background
        // This will replace preview recs once successful
        fetchRecommendations({ limit: 5 })
          .then((response) => {
            setRecommendations(response.items);
            setRequestId(response.request_id);
            // Clear all preview storage keys after successful authenticated fetch
            localStorage.removeItem(PREVIEW_RECS_KEY);
            localStorage.removeItem(PREVIEW_READY_KEY);
            localStorage.removeItem(PREVIEW_ONBOARDING_KEY);
          })
          .catch((err) => {
            // If authenticated fetch fails, keep preview recs visible
            console.warn('Failed to fetch authenticated recommendations, keeping preview:', err);
          });
        return;
      } catch (parseErr) {
        console.error('Failed to parse preview recs:', parseErr);
        // Fall through to normal flow
      }
    }

    // Otherwise, check backend health first, then fetch recommendations
    let cancelled = false;

    async function checkHealthAndLoad() {
      // First, check backend health
      try {
        const healthRes = await fetch(`${API_BASE_URL}/health`, {
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
        const fallbackPreviewRecsStr = localStorage.getItem(PREVIEW_RECS_KEY);
        if (fallbackPreviewRecsStr) {
          try {
            const fallbackPreviewRecs = JSON.parse(fallbackPreviewRecsStr);
            if (!cancelled) {
              setRecommendations(fallbackPreviewRecs);
              setLoading(false);
            }
            return;
          } catch (parseErr) {
            console.error('Failed to parse preview recs:', parseErr);
          }
        }
        
        if (!cancelled) {
          setError(
            `Backend is offline (${errorMsg}). Please ensure FastAPI is running. ` +
            `API_BASE_URL=${API_BASE_URL}. Check browser console for details.`
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
        const response = await fetchRecommendations({ limit: 5 });
        if (!cancelled) {
          setRecommendations(response.items);
          setRequestId(response.request_id);
          // Clear preview recs if we successfully fetched from backend
          localStorage.removeItem(PREVIEW_RECS_KEY);
          localStorage.removeItem(PREVIEW_READY_KEY);
          localStorage.removeItem(PREVIEW_ONBOARDING_KEY);
        }
      } catch (err: any) {
        if (!cancelled) {
          console.error("Failed to load recommendations", err);
          
          // Fall back to preview recs if backend errors
          const fallbackPreviewRecsStr = localStorage.getItem(PREVIEW_RECS_KEY);
          if (fallbackPreviewRecsStr) {
            try {
              const fallbackPreviewRecs = JSON.parse(fallbackPreviewRecsStr);
              setRecommendations(fallbackPreviewRecs);
              setLoading(false);
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
            color: 'var(--rd-muted)'
          }}>
            We don&apos;t have enough signal yet. Try rating a few books or uploading your
            reading history.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="readar-recommendations-page">
      <div className="container">
        <div className="readar-recommendations-header">
          <h1 className="readar-recommendations-title">Your recommendations</h1>
          <p className="readar-recommendations-subtitle">
            Based on your stage, focus areas, and reading history.
          </p>
        </div>

        <div className="readar-recommendations-grid">
          {recommendations.map((book, index) => (
            <RecommendationCard
              key={book.book_id}
              book={book}
              onAction={handleBookAction}
              isTopMatch={index === 0}
              requestId={requestId || undefined}
              position={index}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

