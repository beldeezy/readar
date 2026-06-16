import { useEffect, useState } from 'react';
import { apiClient } from '../../api/client';
import type { AdminAnalytics } from '../../api/types';
import './Analytics.css';

const WINDOWS = [7, 30, 90];

function pct(v: number | null): string {
  return v == null ? '—' : `${(v * 100).toFixed(1)}%`;
}

export default function Analytics() {
  const [data, setData] = useState<AdminAnalytics | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    load(days);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days]);

  const load = async (d: number) => {
    setLoading(true);
    setError(null);
    try {
      setData(await apiClient.getAdminAnalytics(d));
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load analytics.');
    } finally {
      setLoading(false);
    }
  };

  const signupEntries = data ? Object.entries(data.signups_by_day).sort(([a], [b]) => a.localeCompare(b)) : [];
  const maxSignups = signupEntries.reduce((m, [, c]) => Math.max(m, c), 0);
  const eventEntries = data ? Object.entries(data.event_totals).sort(([, a], [, b]) => b - a) : [];

  return (
    <div className="readar-analytics-page">
      <div className="readar-analytics-header">
        <div>
          <h1 className="readar-admin-page-title">📊 Analytics</h1>
          <p className="readar-admin-page-subtitle">Funnel, monetization, and engagement at a glance.</p>
        </div>
        <div className="readar-analytics-window">
          {WINDOWS.map((w) => (
            <button
              key={w}
              className={`readar-analytics-window-btn${days === w ? ' readar-analytics-window-btn--active' : ''}`}
              onClick={() => setDays(w)}
            >
              {w}d
            </button>
          ))}
        </div>
      </div>

      {loading && <p className="readar-analytics-muted">Loading…</p>}
      {error && <p className="readar-analytics-error">{error}</p>}

      {data && !loading && (
        <>
          {/* Funnels */}
          <section className="readar-analytics-section">
            <h2 className="readar-analytics-section-title">Acquisition funnel</h2>
            <Funnel stages={data.funnel} />
          </section>

          <section className="readar-analytics-section">
            <h2 className="readar-analytics-section-title">Onboarding funnel</h2>
            <p className="readar-analytics-muted" style={{ marginBottom: '0.75rem' }}>
              Where people drop within onboarding (by anonymous session). The "Prompted to sign in" →
              "Completed" gap is the auth-wall leak.
            </p>
            <Funnel stages={data.onboarding_funnel} />
          </section>

          {/* Monetization */}
          <section className="readar-analytics-section">
            <h2 className="readar-analytics-section-title">Monetization (refresh paywall)</h2>
            <div className="readar-kpi-grid">
              <Kpi label="Spins used" value={data.monetization.refresh_used} />
              <Kpi label="Hit the wall" value={data.monetization.refresh_limit_hit} sub={`${data.monetization.refresh_limit_hit_users} users`} />
              <Kpi label="Upgrade clicks" value={data.monetization.upgrade_prompt_click} sub={`${data.monetization.upgrade_prompt_click_users} users`} />
              <Kpi label="Wall → click" value={pct(data.monetization.wall_to_click_rate)} highlight />
              <Kpi label="Paid users" value={data.monetization.paid_users} />
              <Kpi label="Free users" value={data.monetization.free_users} />
            </div>
          </section>

          {/* Engagement */}
          <section className="readar-analytics-section">
            <h2 className="readar-analytics-section-title">Engagement</h2>
            <div className="readar-kpi-grid">
              <Kpi label="Books read (history)" value={data.engagement.books_read} />
              <Kpi label="Users with shelves" value={data.engagement.users_with_shelves} />
              <Kpi label="Catalog size" value={data.engagement.catalog_size} />
            </div>
            {Object.keys(data.engagement.shelf_statuses).length > 0 && (
              <div className="readar-analytics-breakdown">
                <h3 className="readar-analytics-subtitle">Shelf statuses</h3>
                {Object.entries(data.engagement.shelf_statuses)
                  .sort(([, a], [, b]) => b - a)
                  .map(([status, count]) => (
                    <div key={status} className="readar-analytics-breakdown-row">
                      <span>{status}</span>
                      <strong>{count}</strong>
                    </div>
                  ))}
              </div>
            )}
          </section>

          {/* Signups over time */}
          <section className="readar-analytics-section">
            <h2 className="readar-analytics-section-title">New signups · last {data.window_days} days</h2>
            {signupEntries.length === 0 ? (
              <p className="readar-analytics-muted">No signups in this window.</p>
            ) : (
              <div className="readar-spark">
                {signupEntries.map(([date, count]) => (
                  <div key={date} className="readar-spark-col" title={`${date}: ${count}`}>
                    <div
                      className="readar-spark-bar"
                      style={{ height: `${maxSignups ? (count / maxSignups) * 100 : 0}%` }}
                    />
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Raw event totals */}
          <section className="readar-analytics-section">
            <h2 className="readar-analytics-section-title">Event totals (all time)</h2>
            {eventEntries.length === 0 ? (
              <p className="readar-analytics-muted">No events logged yet.</p>
            ) : (
              <div className="readar-analytics-breakdown">
                {eventEntries.map(([name, count]) => (
                  <div key={name} className="readar-analytics-breakdown-row">
                    <span>{name}</span>
                    <strong>{count}</strong>
                  </div>
                ))}
              </div>
            )}
          </section>

          <p className="readar-analytics-muted readar-analytics-foot">
            Generated {new Date(data.generated_at).toLocaleString()}
          </p>
        </>
      )}
    </div>
  );
}

function Funnel({ stages }: { stages: { stage: string; count: number; pct_of_top: number | null }[] }) {
  return (
    <div className="readar-funnel">
      {stages.map((s) => (
        <div key={s.stage} className="readar-funnel-row">
          <div className="readar-funnel-label">{s.stage}</div>
          <div className="readar-funnel-bar-track">
            <div className="readar-funnel-bar-fill" style={{ width: `${(s.pct_of_top ?? 0) * 100}%` }} />
          </div>
          <div className="readar-funnel-value">
            <strong>{s.count}</strong> <span>{pct(s.pct_of_top)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function Kpi({ label, value, sub, highlight }: { label: string; value: number | string; sub?: string; highlight?: boolean }) {
  return (
    <div className={`readar-kpi${highlight ? ' readar-kpi--highlight' : ''}`}>
      <div className="readar-kpi-value">{value}</div>
      <div className="readar-kpi-label">{label}</div>
      {sub && <div className="readar-kpi-sub">{sub}</div>}
    </div>
  );
}
