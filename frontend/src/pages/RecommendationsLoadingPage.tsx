import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchRecommendations } from '../api/client';
import type { RecommendationItem } from '../api/types';
import RadarIcon from '../components/RadarIcon';
import './RecommendationsPage.css';

export default function RecommendationsLoadingPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<"fetching" | "finalizing">("fetching");
  
  const userId = searchParams.get('userId');
  const limitParam = searchParams.get('limit');
  const limit = limitParam ? parseInt(limitParam, 10) : 5;

  useEffect(() => {
    let cancelled = false;

    const sleep = (ms: number) =>
      new Promise((resolve) => setTimeout(resolve, ms));

    async function run() {
      if (!userId) {
        setError('User ID is required');
        return;
      }

      try {
        console.log("RecommendationsLoadingPage mounted", { userId });

        // 1. Fetch recommendations as fast as possible
        const recs = await fetchRecommendations({ userId, limit });

        console.log("Recommendations fetched, holding loading screen");

        if (cancelled) return;

        // Update phase to show progress
        setPhase("finalizing");

        // 2. HOLD the loading page for 7 seconds AFTER fetch
        await sleep(7000);

        if (cancelled) return;

        // 3. Navigate to final recommendations page
        navigate(`/recommendations?userId=${encodeURIComponent(userId)}`, {
          state: { prefetchedRecommendations: recs }
        });
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message || "Failed to generate recommendations.");
      }
    }

    run();

    return () => {
      cancelled = true;
    };
  }, [userId, limit, navigate]);

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

