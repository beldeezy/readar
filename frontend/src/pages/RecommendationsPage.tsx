import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient, fetchRecommendations } from '../api/client';
import type { RecommendationItem, BookPreferenceStatus } from '../api/types';
import RecommendationCard from '../components/RecommendationCard';
import Card from '../components/Card';
import { useAuth } from '../contexts/AuthContext';
import { DEV_TEST_USER_ID } from '../api/constants';
import './RecommendationsPage.css';

interface RecommendationsPageProps {
  userId?: string;
}

export default function RecommendationsPage({ userId: propUserId }: RecommendationsPageProps = {}) {
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { user: authUser } = useAuth() ?? { user: null };
  
  // Use prop userId if provided, otherwise use auth context user, or fallback to dev test user
  const userId = propUserId ?? authUser?.id ?? DEV_TEST_USER_ID;

  useEffect(() => {
    if (!userId) {
      setError('User ID is required');
      setLoading(false);
      return;
    }

    // Check if we have prefetched recommendations from the loading page
    const prefetchedRecs = (location.state as any)?.prefetchedRecommendations as RecommendationItem[] | undefined;
    
    if (prefetchedRecs) {
      // Use prefetched results immediately
      setRecommendations(prefetchedRecs);
      setLoading(false);
      return;
    }

    // Otherwise, fetch recommendations normally
    let cancelled = false;

    async function loadRecommendations() {
      setLoading(true);
      setError(null);
      
      try {
        const recs = await fetchRecommendations({ userId, limit: 5 });
        if (!cancelled) {
          setRecommendations(recs);
        }
      } catch (err: any) {
        if (!cancelled) {
          console.error("Failed to load recommendations", err);
          setError(err?.message || "Failed to fetch recommendations");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadRecommendations();

    return () => {
      cancelled = true;
    };
  }, [userId, location.state]);

  const handleBookAction = async (
    bookId: string,
    status: BookPreferenceStatus
  ) => {
    try {
      await apiClient.updateUserBook(bookId, status);
      // Optionally refresh recommendations or update UI
      if (userId) {
        const recs = await fetchRecommendations({ userId, limit: 5 });
        setRecommendations(recs);
      }
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
            />
          ))}
        </div>
      </div>
    </div>
  );
}

