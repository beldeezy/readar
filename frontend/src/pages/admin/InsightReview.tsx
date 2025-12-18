import { useEffect, useState } from 'react';
import Input from '../../components/Input';
import Button from '../../components/Button';
import type { InsightReviewItem } from '../../api/types';
// Ensure API_BASE_URL includes /api prefix if not already present
const envApiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_BASE_URL = envApiBaseUrl.endsWith('/api') ? envApiBaseUrl : `${envApiBaseUrl}/api`;
import './InsightReview.css';

export default function InsightReview() {
  const [userId, setUserId] = useState<string>('');
  const [data, setData] = useState<InsightReviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchInsightReview = async (userUuid: string) => {
    if (!userUuid.trim()) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const url = `${API_BASE_URL}/admin/insight-review?user_id=${encodeURIComponent(userUuid)}`;
      const response = await fetch(url, {
        method: 'GET',
      });

      if (!response.ok) {
        let message = `Failed to fetch insight review (status ${response.status}).`;
        try {
          const errorData = await response.json();
          if (errorData && typeof errorData.detail === 'string') {
            message = errorData.detail;
          }
        } catch {
          // ignore JSON parse errors
        }
        throw new Error(message);
      }

      const result = await response.json();
      setData(result);
    } catch (err: any) {
      console.error('Failed to fetch insight review', err);
      setError(err?.message || 'Failed to fetch insight review');
      setData([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchInsightReview(userId);
  };

  const handleBlur = () => {
    if (userId.trim()) {
      fetchInsightReview(userId);
    }
  };

  // Helper to check if a row has low insight signal
  // Highlight rows where all insight matches = 0.0 (bad candidate)
  // or where total score > 2.0 but all insights = 0 (might be false positives)
  const hasLowInsightSignal = (item: InsightReviewItem): boolean => {
    const insightFields = [
      item.promise_match,
      item.framework_match,
      item.outcome_match,
    ];
    const allInsightZero = insightFields.every((val) => val === 0);
    // Highlight if all insights are zero (bad candidate) or if total is high but insights are zero (false positive)
    return allInsightZero || (item.total_score > 2.0 && allInsightZero);
  };

  return (
    <div className="readar-insight-review">
      <div className="readar-insight-review-header">
        <h1 className="readar-insight-review-title">Insight Review Tool</h1>
        <p className="readar-insight-review-subtitle">
          Review book recommendations and their score factors for a given user
        </p>
      </div>

      <form onSubmit={handleSubmit} className="readar-insight-review-form">
        <Input
          label="User ID"
          type="text"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          onBlur={handleBlur}
          placeholder="Enter user UUID"
          className="readar-insight-review-input"
        />
        <Button type="submit" disabled={loading || !userId.trim()}>
          {loading ? 'Loading...' : 'Fetch Recommendations'}
        </Button>
      </form>

      {error && (
        <div className="readar-insight-review-error">
          <p>{error}</p>
        </div>
      )}

      {data.length > 0 && (
        <div className="readar-insight-review-table-container">
          <table className="readar-insight-review-table">
            <thead>
              <tr>
                <th>Book Title</th>
                <th>Total Score</th>
                <th>Stage Fit</th>
                <th>Challenge Fit</th>
                <th>Promise Match</th>
                <th>Framework Match</th>
                <th>Outcome Match</th>
              </tr>
            </thead>
            <tbody>
              {data.map((item, index) => {
                const isLowInsight = hasLowInsightSignal(item);
                return (
                  <tr
                    key={index}
                    className={isLowInsight ? 'readar-insight-review-row--low-signal' : ''}
                  >
                    <td className="readar-insight-review-title-cell">{item.title}</td>
                    <td>{item.total_score.toFixed(2)}</td>
                    <td>{item.stage_fit.toFixed(2)}</td>
                    <td>{item.challenge_fit.toFixed(2)}</td>
                    <td>{item.promise_match.toFixed(2)}</td>
                    <td>{item.framework_match.toFixed(2)}</td>
                    <td>{item.outcome_match.toFixed(2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && data.length === 0 && userId && (
        <div className="readar-insight-review-empty">
          <p>No recommendations found for this user.</p>
        </div>
      )}
    </div>
  );
}

