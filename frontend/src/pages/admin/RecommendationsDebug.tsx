import React, { useState } from 'react';
import { apiClient } from '../../api/client';
import type { RecommendationsResponse, RecommendationItem } from '../../api/types';
import Button from '../../components/Button';
import './RecommendationsDebug.css';

export default function RecommendationsDebug() {
  const [limit, setLimit] = useState(5);
  const [debug, setDebug] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const handleFetch = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.getAdminRecommendationsDebug(limit, debug);
      setData(response);
    } catch (err: any) {
      console.error('Failed to fetch recommendations', err);
      const errorMessage = err?.response?.data?.detail || err?.message || 'Failed to fetch recommendations';
      setError(errorMessage);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCopyJson = () => {
    if (!data) return;
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
  };

  const toggleRow = (bookId: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(bookId)) {
      newExpanded.delete(bookId);
    } else {
      newExpanded.add(bookId);
    }
    setExpandedRows(newExpanded);
  };

  const getDominantInsight = (item: RecommendationItem): string | null => {
    if (!item.matched_insights || item.matched_insights.length === 0) {
      return null;
    }
    const sorted = [...item.matched_insights].sort((a, b) => b.weight - a.weight);
    return sorted[0]?.key || null;
  };

  return (
    <div className="readar-recs-debug-page">
      <div className="readar-recs-debug-header">
        <h1 className="readar-admin-page-title">📚 Recommendations Debug</h1>
        <p className="readar-admin-page-subtitle">
          Inspect scoring, insights, and diversity penalties (debug=true).
        </p>
      </div>

      {/* Controls Row */}
      <div className="readar-recs-debug-controls-panel">
        <div className="readar-recs-debug-controls-row">
          <div className="readar-recs-debug-control-group">
            <label htmlFor="limit-input" className="readar-recs-debug-control-label">
              Limit
            </label>
            <input
              id="limit-input"
              type="number"
              className="readar-recs-debug-input"
              min={1}
              max={50}
              value={limit}
              onChange={(e) => setLimit(Math.max(1, Math.min(50, parseInt(e.target.value, 10) || 5)))}
            />
          </div>

          <div className="readar-recs-debug-control-group">
            <label className="readar-recs-debug-control-label">
              <input
                type="checkbox"
                checked={debug}
                onChange={(e) => setDebug(e.target.checked)}
                className="readar-recs-debug-checkbox"
              />
              <span style={{ marginLeft: '0.5rem' }}>Debug</span>
            </label>
          </div>

          <div className="readar-recs-debug-control-group">
            <Button onClick={handleFetch} variant="primary" disabled={loading}>
              {loading ? 'Fetching...' : 'Fetch'}
            </Button>
          </div>

          {data && (
            <div className="readar-recs-debug-control-group">
              <Button onClick={handleCopyJson} variant="secondary" size="sm">
                Copy JSON
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="readar-recs-debug-loading">
          <p>Fetching recommendations…</p>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="readar-recs-debug-error-panel">
          <h3>Error</h3>
          <p>{error}</p>
          <Button onClick={handleFetch} variant="primary">
            Retry
          </Button>
        </div>
      )}

      {/* Success State */}
      {data && !loading && (
        <div className="readar-recs-debug-results-card">
          <div className="readar-recs-debug-results-header">
            <h3>Results ({data.items.length} items)</h3>
            {data.request_id && (
              <span className="readar-recs-debug-request-id">Request ID: {data.request_id}</span>
            )}
          </div>

          <div className="readar-recs-debug-table-container">
            <table className="readar-recs-debug-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Author</th>
                  <th>base_score</th>
                  <th>insight_score_total</th>
                  <th>diversity_penalty_applied</th>
                  <th>final_score</th>
                  <th>dominant_insight</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => {
                  const isExpanded = expandedRows.has(item.book_id);
                  const dominantInsight = getDominantInsight(item);
                  return (
                    <React.Fragment key={item.book_id}>
                      <tr className="readar-recs-debug-table-row">
                        <td className="readar-recs-debug-title-cell">{item.title}</td>
                        <td>{item.author_name || '—'}</td>
                        <td>{item.base_score?.toFixed(2) ?? '—'}</td>
                        <td>{item.insight_score_total?.toFixed(2) ?? '—'}</td>
                        <td>{item.diversity_penalty_applied?.toFixed(2) ?? '—'}</td>
                        <td>{item.final_score?.toFixed(2) ?? item.relevancy_score?.toFixed(2) ?? '—'}</td>
                        <td>{dominantInsight || '—'}</td>
                        <td>
                          <button
                            className="readar-recs-debug-expand-btn"
                            onClick={() => toggleRow(item.book_id)}
                          >
                            {isExpanded ? '▼' : '▶'}
                          </button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="readar-recs-debug-details-row">
                          <td colSpan={8} className="readar-recs-debug-details-cell">
                            <div className="readar-recs-debug-details-content">
                              <div className="readar-recs-debug-details-section">
                                <h4>Matched Insights</h4>
                                {item.matched_insights && item.matched_insights.length > 0 ? (
                                  <ul className="readar-recs-debug-insights-list">
                                    {item.matched_insights.map((insight, idx) => (
                                      <li key={idx}>
                                        <strong>{insight.key}</strong> (weight: {insight.weight.toFixed(2)})
                                        {insight.reason && <span>: {insight.reason}</span>}
                                      </li>
                                    ))}
                                  </ul>
                                ) : (
                                  <p className="readar-recs-debug-empty">No matched insights</p>
                                )}
                              </div>

                              {item.score_factors && (
                                <div className="readar-recs-debug-details-section">
                                  <h4>Score Factors</h4>
                                  <ul className="readar-recs-debug-factors-list">
                                    {Object.entries(item.score_factors).map(([key, value]) => (
                                      <li key={key}>
                                        <strong>{key}:</strong> {typeof value === 'number' ? value.toFixed(2) : String(value)}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              <div className="readar-recs-debug-details-section">
                                <h4>Full Debug Blob</h4>
                                <details>
                                  <summary>Click to expand JSON</summary>
                                  <pre className="readar-recs-debug-json">{JSON.stringify(item, null, 2)}</pre>
                                </details>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

