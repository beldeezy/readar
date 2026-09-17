import { useEffect, useState } from 'react';
import { Check, Flame, Sparkles, Trophy } from 'lucide-react';
import { apiClient } from '../api/client';
import type { ReadingRewards as Rewards } from '../api/types';
import { useReadingCalendar } from '../hooks/useReadingCalendar';
import Button from './Button';
import './ReadingRewards.css';

export default function ReadingRewards({ refreshKey }: { refreshKey: number }) {
  const { day, tz } = useReadingCalendar();
  const [data, setData] = useState<Rewards | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const refresh = () => {
      setLoading(true); setFailed(false);
      // Last request wins if a save, focus and midnight refresh overlap.
      const request = ++sequence;
      apiClient.getReadingRewards(tz).then((saved) => {
        if (!cancelled && request === sequence) setData(saved);
      }).catch(() => {
        if (!cancelled && request === sequence) setFailed(true);
      }).finally(() => {
        if (!cancelled && request === sequence) setLoading(false);
      });
    };
    let sequence = 0;
    const onVisible = () => { if (document.visibilityState === 'visible') refresh(); };
    refresh();
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      cancelled = true;
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [refreshKey, retry, day, tz]);

  const titles = { new: 'Start with one good day.', active: 'You showed up today.', continue: 'Keep your rhythm.', restart: 'A fresh start counts.' };
  const dateLabel = (date: string) => new Date(`${date}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

  return <section className="reading-rewards" aria-label="Your reading rhythm" aria-busy={loading}>
    <p className="reading-rewards-eyebrow">Your reading rhythm</p>
    {!data && loading && <p role="status">Loading streaks and points…</p>}
    {failed && <div role="alert">
      <p>We couldn’t refresh your rewards. {data ? 'The numbers below are from the last successful check.' : 'Your saved reading is still there.'}</p>
      <Button size="sm" variant="secondary" onClick={() => setRetry((n) => n + 1)}>Retry rewards</Button>
    </div>}
    {data && <>
      <div className="reading-rewards-message" role="status" aria-live="polite" aria-atomic="true">
        <h2>{titles[data.state]}</h2>
        <p>{data.state === 'active' ? `${data.points_per_day} points earned for today. Come back tomorrow for the next day of your streak.`
          : data.state === 'continue' ? `Meet one book’s daily goal today to continue your ${data.current_streak}-day streak.`
          : data.state === 'restart' ? 'Your earned points are still here. Meet a goal today to start a new streak.'
          : `Meet a daily goal on any book to start your streak and earn ${data.points_per_day} points.`}</p>
      </div>
      <dl className="reading-rewards-stats">
        <div><dt><Flame size={16} aria-hidden="true" />Current streak</dt><dd>{data.current_streak}<span>{data.current_streak === 1 ? 'day' : 'days'}</span></dd></div>
        <div><dt><Trophy size={16} aria-hidden="true" />Best streak</dt><dd>{data.best_streak}<span>{data.best_streak === 1 ? 'day' : 'days'}</span></dd></div>
        <div><dt><Sparkles size={16} aria-hidden="true" />Total points</dt><dd>{data.total_points}<span>{data.qualifying_days} goal {data.qualifying_days === 1 ? 'day' : 'days'}</span></dd></div>
      </dl>
      <ol className="reading-rewards-days" aria-label="Last seven reading days">
        {data.recent_days.map((entry) => <li key={entry.reading_date} className={`${entry.qualified ? 'is-qualified' : ''} ${entry.reading_date === data.today ? 'is-today' : ''}`} aria-current={entry.reading_date === data.today ? 'date' : undefined}>
          <span>{new Date(`${entry.reading_date}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short' })}</span>
          <span className="reading-rewards-day-mark" aria-label={`${dateLabel(entry.reading_date)}: ${entry.qualified ? 'goal met' : entry.reading_date === data.today ? 'still time today' : 'no goal recorded'}`}>
            {entry.qualified ? <Check size={18} aria-hidden="true" /> : '—'}
          </span>
          <small>{entry.reading_date === data.today ? 'Today' : new Date(`${entry.reading_date}T12:00:00`).getDate()}</small>
        </li>)}
      </ol>
      {loading && <p className="reading-rewards-sync" role="status">Updating rewards…</p>}
      <details>
        <summary>How streaks and points work</summary>
        <ul>
          <li>Meet one book’s saved daily goal to earn {data.points_per_day} points. Each date counts once across all books; pages and chapters from different books aren’t combined.</li>
          <li>A goal day adds to your streak. You have all of today to continue yesterday’s streak. Missing a full day resets the current streak, while your points and best streak stay.</li>
          <li>Each entry keeps the goal from its first save. Changing your goal applies to new entries. Correcting or removing logs, or changing your starting position, recalculates credit.</li>
          <li>Forgot to log reading? Choose its actual reading date on the book. Saved dates stay fixed when you travel.</li>
        </ul>
        <p>Today follows {data.timezone.replace(/_/g, ' ')}. These points track your personal progress.</p>
      </details>
    </>}
  </section>;
}
