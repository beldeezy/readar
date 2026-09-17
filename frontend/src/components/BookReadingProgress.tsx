import { useEffect, useId, useRef, useState } from 'react';
import { apiClient } from '../api/client';
import type { ReadingProgress } from '../api/types';
import { useReadingCalendar } from '../hooks/useReadingCalendar';
import Button from './Button';
import './BookReadingProgress.css';

interface Props { bookId: string; disabled?: boolean; onBusyChange: (busy: boolean) => void; onSaved: () => void; }

export default function BookReadingProgress({ bookId, disabled, onBusyChange, onSaved }: Props) {
  const id = useId();
  const { tz, day } = useReadingCalendar();
  const dirty = useRef(false);
  const loadedKey = useRef('');
  const refreshingRef = useRef(false);
  const [refreshing, setRefreshing] = useState(false);
  const [data, setData] = useState<ReadingProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState('');
  const saving = useRef(false);
  const positionInput = useRef<HTMLInputElement>(null);
  const [date, setDate] = useState('');
  const [position, setPosition] = useState('');
  const [unit, setUnit] = useState<'pages' | 'chapters'>('pages');
  const [start, setStart] = useState('0');
  const [total, setTotal] = useState('');
  const [goal, setGoal] = useState('10');
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false);
  const [notice, setNotice] = useState('');

  const fillSettings = (saved: ReadingProgress) => {
    setUnit(saved.unit); setStart(String(saved.starting_position));
    setTotal(saved.total_units == null ? '' : String(saved.total_units));
    setGoal(String(saved.daily_goal));
  };

  useEffect(() => {
    const key = `${bookId}|${tz}|${day}|${reload}`;
    if (busy || disabled || loadedKey.current === key) return;
    let cancelled = false;
    refreshingRef.current = true; setRefreshing(true);
    if (!data) setLoading(true);
    setLoadError(false);
    apiClient.getReadingProgress(bookId, tz).then((saved) => {
      if (cancelled) return;
      loadedKey.current = key;
      const changedElsewhere = dirty.current && data !== null && saved.revision !== data.revision;
      setData(saved);
      setError(changedElsewhere ? 'Your saved progress changed while you were editing. Reload before saving again.' : '');
      setConflict(changedElsewhere);
      if (!dirty.current) {
        fillSettings(saved); setDate(saved.today); setPosition(String(saved.current_position));
      } else {
        setNotice('The reading day changed. Your entry is still here; check its reading date before saving.');
      }
    }).catch(() => {
      if (cancelled) return;
      if (!data) setLoadError(true);
      else { setError('We couldn’t refresh your progress for today. Reload before saving.'); setConflict(true); }
    })
      .finally(() => {
        if (!cancelled) { refreshingRef.current = false; setRefreshing(false); setLoading(false); }
      });
    return () => { cancelled = true; refreshingRef.current = false; setRefreshing(false); };
  }, [bookId, tz, day, reload, busy, disabled]);

  const save = async (action: string, operation: () => Promise<ReadingProgress>, message: string) => {
    if (saving.current || refreshingRef.current || disabled || conflict) return;
    saving.current = true; setBusy(action); onBusyChange(true); setError(''); setNotice('');
    try {
      const saved = await operation();
      setData(saved); fillSettings(saved); dirty.current = false;
      const earnedGoal = action === 'log' && date === saved.today && saved.goal_met && !data?.logs.find((log) => log.reading_date === date)?.goal_met;
      setNotice(earnedGoal ? 'Daily goal reached. Progress saved.' : message);
      onSaved();
      if (action === 'settings') {
        setDate(saved.today); setPosition(String(saved.current_position));
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : "We couldn't save your progress. Your entry is still here; please try again.");
      setConflict(err?.response?.status === 409);
    } finally {
      saving.current = false; setBusy(''); onBusyChange(false);
    }
  };

  if (loading) return <p role="status" className="reading-muted">Loading progress…</p>;
  if (loadError || !data) return <div role="alert" className="reading-progress"><p>We couldn’t load your saved progress.</p><Button variant="secondary" disabled={disabled} onClick={() => setReload((n) => n + 1)}>Try again</Button></div>;

  const locked = !!disabled || !!busy || refreshing || conflict;
  const singular = data.unit === 'pages' ? 'page' : 'chapter';
  const savedOnDate = data.logs.find((log) => log.reading_date === date);
  const displayDate = (value: string) => new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });

  return <section className="reading-progress" aria-label="Book progress" aria-busy={!!busy || refreshing}>
    <div className="reading-progress-summary">
      <strong>{data.unit === 'pages' ? 'Page' : 'Chapter'} {data.current_position}{data.total_units != null ? ` of ${data.total_units}` : ''}</strong>
      {data.percent_complete != null && <span>{data.percent_complete}%</span>}
    </div>
    {data.total_units != null && <progress className="reading-progress-bar" max={data.total_units} value={data.current_position} aria-label="Book progress" />}
    <p className="reading-progress-goal">{data.today_units} / {data.today_goal} {data.unit} logged today{data.goal_met ? ' · Daily goal reached' : ''}</p>
    {data.today_goal !== data.daily_goal && <p className="reading-progress-hint">Today’s saved goal stays at {data.today_goal} {data.unit}. New entries use {data.daily_goal}.</p>}
    {refreshing && <p role="status" className="reading-muted">Refreshing today’s progress…</p>}

    <form onChange={() => { dirty.current = true; }} onSubmit={(event) => {
      event.preventDefault();
      if (position === '' || !Number.isInteger(Number(position))) return;
      void save('log', () => apiClient.saveReadingLog(bookId, date, Number(position), data.revision, tz), 'Progress saved.');
    }}>
      <h4>Where did you stop?</h4>
      <div className="reading-progress-fields">
        <label htmlFor={`${id}-position`}>{data.unit === 'pages' ? 'Page you reached' : 'Chapters completed'}
          <input ref={positionInput} id={`${id}-position`} type="number" inputMode="numeric" min="0" max={data.total_units ?? 100000} step="1" required value={position} disabled={locked} onChange={(event) => setPosition(event.target.value)} />
        </label>
        <label htmlFor={`${id}-date`}>Reading date
          <input id={`${id}-date`} type="date" required max={data.today} value={date} disabled={locked} onChange={(event) => {
            setDate(event.target.value);
            const entry = data.logs.find((log) => log.reading_date === event.target.value);
            setPosition(entry ? String(entry.position) : event.target.value === data.today ? String(data.current_position) : '');
          }} />
        </label>
      </div>
      <Button type="submit" disabled={locked}>{busy === 'log' ? 'Saving…' : savedOnDate ? 'Update progress' : 'Save progress'}</Button>
      <p className="reading-progress-hint">Enter your stopping point, not the amount you read. Saving again updates that day’s entry.</p>
      {savedOnDate && <p className="reading-progress-hint">Goal saved for this date: {savedOnDate.goal_target} {data.unit}.</p>}
    </form>

    {notice && <p role="status" className="reading-notice">{notice}</p>}
    {error && <p role="alert" className="readar-action-error">{error}</p>}
    {conflict && <Button variant="secondary" disabled={!!busy || disabled} onClick={() => { dirty.current = false; setReload((n) => n + 1); }}>Reload saved progress</Button>}

    <details className="reading-progress-settings">
      <summary>Book settings · {data.daily_goal} {data.unit}/day</summary>
      <p className="reading-progress-hint">Already partway through? Set your starting position. Earlier pages won’t count as newly logged reading. Goal changes apply to new entries; existing dates keep their saved goals.</p>
      <form onChange={() => { dirty.current = true; }} onSubmit={(event) => {
        event.preventDefault();
        if (start === '' || goal === '') return;
        void save('settings', () => apiClient.saveReadingSettings(bookId, {
          unit, starting_position: Number(start), total_units: total === '' ? null : Number(total),
          daily_goal: Number(goal), expected_revision: data.revision,
        }, tz), 'Book settings saved.');
      }}>
        <div className="reading-progress-fields">
          <label htmlFor={`${id}-unit`}>Track by
            <select id={`${id}-unit`} value={unit} disabled={locked || data.logs.length > 0} onChange={(event) => {
              const next = event.target.value as 'pages' | 'chapters';
              setUnit(next); setGoal(next === 'pages' ? '10' : '1'); setStart('0'); setTotal('');
            }}><option value="pages">Pages</option><option value="chapters">Chapters</option></select>
          </label>
          <label htmlFor={`${id}-goal`}>Daily goal ({unit})<input id={`${id}-goal`} type="number" min="1" max="1000" step="1" required value={goal} disabled={locked} onChange={(event) => setGoal(event.target.value)} /></label>
          <label htmlFor={`${id}-start`}>Starting {unit === 'pages' ? 'page' : 'chapter'}<input id={`${id}-start`} type="number" min="0" max="100000" step="1" required value={start} disabled={locked} onChange={(event) => setStart(event.target.value)} /></label>
          <label htmlFor={`${id}-total`}>Total {unit} (optional)<input id={`${id}-total`} type="number" min="1" max="100000" step="1" value={total} disabled={locked} placeholder="Unknown" onChange={(event) => setTotal(event.target.value)} /></label>
        </div>
        {data.logs.length > 0 && <p className="reading-progress-hint">Tracking units stay fixed while logs exist.</p>}
        <Button type="submit" variant="secondary" disabled={locked}>{busy === 'settings' ? 'Saving…' : 'Save book settings'}</Button>
      </form>
    </details>

    <details className="reading-progress-history">
      <summary>Reading history ({data.logs.length})</summary>
      {data.logs.length === 0 ? <p className="reading-muted">No reading logged yet. Your first entry will appear here.</p> : <>
        <p className="reading-progress-hint">Amounts are the change since the previous entry, or your starting position. Correcting or removing an entry recalculates later amounts, streaks and points.</p>
        <ul>{data.logs.map((log) => <li key={log.reading_date}>
          <span>{displayDate(log.reading_date)} · {singular} {log.position}<small>+{log.units_read} {data.unit} · Goal: {log.goal_target}{log.goal_met ? ' · Goal met' : ''}</small></span>
          <div>
            <Button size="sm" variant="ghost" disabled={locked} aria-label={`Edit reading on ${displayDate(log.reading_date)}`} onClick={() => {
              dirty.current = true; setDate(log.reading_date); setPosition(String(log.position)); positionInput.current?.focus();
            }}>Edit</Button>
            <Button size="sm" variant="ghost" disabled={locked} aria-label={`Remove reading on ${displayDate(log.reading_date)}`} onClick={() => {
              void save(`delete-${log.reading_date}`, () => apiClient.deleteReadingLog(bookId, log.reading_date, data.revision, tz), 'Entry removed. You can add it again if needed.');
            }}>{busy === `delete-${log.reading_date}` ? 'Removing…' : 'Remove'}</Button>
          </div>
        </li>)}</ul>
      </>}
    </details>
  </section>;
}
