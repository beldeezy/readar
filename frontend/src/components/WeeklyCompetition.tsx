import { useEffect, useId, useRef, useState } from 'react';
import { apiClient } from '../api/client';
import type { CompetitionConsent, FriendlyPairing, WeeklyCompetitionSummary } from '../api/types';
import Button from './Button';
import './WeeklyCompetition.css';

interface Props {
  pairing: FriendlyPairing;
  refreshKey: number;
  disabled: boolean;
  onBusyChange: (busy: boolean) => void;
  onConsentSaved: () => void;
}
const dateLabel = (date: string) => new Date(`${date}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
const points = (value: number) => value.toLocaleString(undefined, { maximumFractionDigits: 2 });
const resultLabels = { win: 'Week won', loss: 'Week completed', shared_win: 'Shared win', quiet: 'A quiet week', ended: 'Pairing ended', ahead: 'You’re ahead', behind: 'Keep your momentum', even: 'All square', pending: 'Your first round is coming' };

export default function WeeklyCompetition({ pairing, refreshKey, disabled, onBusyChange, onConsentSaved }: Props) {
  const id = useId();
  const [data, setData] = useState<WeeklyCompetitionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false);
  const [notice, setNotice] = useState('');
  const fetching = useRef(false);
  const saving = useRef(false);
  const editing = useRef(false);
  const blocked = useRef(disabled);
  const paired = useRef(pairing.status === 'paired');
  const pairingConsent = useRef(pairing.progress_sharing);
  const epoch = useRef(0);
  const alive = useRef(true);
  const pending = useRef<CompetitionConsent | null>(null);
  blocked.current = disabled;
  paired.current = pairing.status === 'paired';
  pairingConsent.current = pairing.progress_sharing;
  const locked = disabled || loading || checking || busy;

  const refresh = async (explicit = false) => {
    if (saving.current || fetching.current || (!explicit && (editing.current || blocked.current))) return;
    if (explicit) { editing.current = false; setChecked(false); pending.current = null; setConflict(false); }
    const request = ++epoch.current;
    fetching.current = true; setChecking(true);
    try {
      const saved = await apiClient.syncWeeklyCompetition();
      if (!alive.current || request !== epoch.current) return;
      setData(saved); setError('');
      if (paired.current && saved.consented !== pairingConsent.current) onConsentSaved();
      if (explicit) setNotice('Your round is up to date.');
    } catch {
      if (alive.current && request === epoch.current) setError('We couldn’t update the round. Your saved reading is still there. Check again when you’re connected.');
    } finally {
      if (request === epoch.current) {
        fetching.current = false;
        if (alive.current) { setLoading(false); setChecking(false); }
      }
    }
  };
  useEffect(() => {
    alive.current = true;
    const check = () => { if (paired.current && document.visibilityState === 'visible') void refresh(); };
    const timer = window.setInterval(check, 30000);
    window.addEventListener('focus', check); document.addEventListener('visibilitychange', check);
    return () => { alive.current = false; epoch.current += 1; fetching.current = false; window.clearInterval(timer); window.removeEventListener('focus', check); document.removeEventListener('visibilitychange', check); };
  }, []);
  useEffect(() => {
    if (saving.current) return;
    // A pairing change supersedes any in-flight summary from the former state.
    epoch.current += 1; fetching.current = false; setChecking(false);
    if (pairing.status !== 'paired') { editing.current = false; pending.current = null; setChecked(false); setConflict(false); }
    void refresh(pairing.status !== 'paired');
  }, [pairing.revision, pairing.status, refreshKey]);

  const join = async () => {
    if (!data || !data.rule || !checked || data.reading_revision === null || locked || saving.current || conflict || data.state !== 'not_joined') return;
    pending.current = pending.current || { request_id: crypto.randomUUID(), expected_revision: data.revision,
      expected_reading_revision: data.reading_revision, timezone: data.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC', share_progress: true };
    saving.current = true; epoch.current += 1; setBusy(true); onBusyChange(true); setError(''); setNotice('');
    try {
      const saved = await apiClient.joinWeeklyCompetition(pending.current);
      if (!alive.current) return;
      setData(saved); pending.current = null; editing.current = false; setChecked(false); setConflict(false);
      setNotice(saved.state === 'waiting' ? 'You’re ready. The first round starts after your partner also joins.' : saved.state === 'unavailable' ? 'Your pairing has ended. Your saved results remain private to you.' : 'You’re both in. Your first full round is scheduled.');
      onConsentSaved();
    } catch (err: any) {
      if (!alive.current) return;
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'We couldn’t save your choice. Retry, or check the round if you’re unsure whether it saved.');
      if (err?.response?.status === 409) setConflict(true);
    } finally { saving.current = false; if (alive.current) setBusy(false); onBusyChange(false); }
  };

  if (!loading && !error && data?.state === 'unavailable' && data.all_time_points === 0 && !data.history.length) return null;
  const active = pairing.status === 'paired' && data?.consented && data.partner_consented && data.current && !error;
  const current = active ? data.current : null;
  const total = current && current.partner ? current.you.points + current.partner.points : 0;
  const share = current && total ? current.you.points / total * 100 : 50;
  const calendar = data?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

  return <section className="weekly-competition" aria-labelledby={`${id}-heading`} aria-busy={loading || busy}>
    <h3 id={`${id}-heading`}>Seven days. Keep showing up.</h3>
    {loading && <p role="status">Loading your rounds…</p>}
    {notice && <p role="status" className="reading-notice">{notice}</p>}
    {data && <>
      {pairing.status === 'paired' && data.state === 'not_joined' && <form onSubmit={(event) => { event.preventDefault(); void join(); }}>
        <p>Turn your pairing into a friendly weekly challenge. You each keep your own book; consistent reading carries the most weight.</p>
        {data.eligibility_error ? <p>{data.eligibility_error} <a href="#now-reading-heading">Go to Book settings ↑</a></p> : data.rule && <>
          <p><strong>Your qualifying day:</strong> {data.rule.daily_target} {data.rule.unit}. Your book is set to {data.rule.total_units} {data.rule.unit}.</p>
          <p><strong>Shared calendar:</strong> {calendar}. {data.partner_consented ? 'Your partner has chosen this calendar and is ready.' : 'Your partner will see this calendar before joining.'} The first seven-day round begins the day after both of you join.</p>
          <label className="friendly-consent weekly-consent"><input type="checkbox" checked={checked} required disabled={locked || conflict} onChange={(event) => { setChecked(event.target.checked); editing.current = event.target.checked; }} /><span>I agree to share my qualifying reading days, the percentage of my book read in the round, and my competition score with my current partner.</span></label>
          <p className="friendly-privacy">Notes and reflections remain private. Book units and length stay fixed for this pairing; leave it to change those settings or stop sharing.</p>
          <Button type="submit" disabled={locked || !checked || conflict}>{busy ? 'Joining…' : 'Join weekly rounds'}</Button>
        </>}
      </form>}
      {pairing.status === 'paired' && data.state === 'waiting' && <div className="weekly-waiting"><h4>You’re ready for your first round.</h4><p>Your partner still needs to opt into sharing weekly summaries. Scores stay private until you’re both in.</p><p className="reading-muted">Your rule: {data.rule?.daily_target} {data.rule?.unit} per qualifying day · {calendar}</p></div>}
      {current && current.partner && <div className="weekly-scoreboard">
        <div className="weekly-round-label"><strong>{current.status === 'scheduled' ? 'Starts ' : 'This round: '}{dateLabel(current.starts_on)} – {dateLabel(current.ends_on)}</strong><span>{calendar}</span></div>
        <p className="weekly-recognition" role="status">{resultLabels[current.result]}</p>
        {current.status === 'scheduled' && <p>Both of you get a full seven days. Reading before this round begins doesn’t add to its score.</p>}
        <div className="weekly-players"><div><span>You</span><strong>{points(current.you.points)} <small>pts</small></strong><span>{current.you.days}/7 qualifying days</span><span>{current.you.progress_percent}% of your book this round</span></div>
          <div><span>Your partner</span><strong>{points(current.partner.points)} <small>pts</small></strong><span>{current.partner.days}/7 qualifying days</span><span>{current.partner.progress_percent}% of their book this round</span></div></div>
        <div className="weekly-tug" role="img" aria-label={`Competition score: you ${points(current.you.points)}, partner ${points(current.partner.points)}. ${total ? '' : 'Both start equal.'}`}><div style={{ width: `${share}%` }} /><span aria-hidden="true" style={{ left: `${share}%` }}>◆</span></div>
        <p className="reading-muted">One more consistent day matters more than the whole progress bonus. <a href="#now-reading-heading">Log today’s reading ↑</a></p>
      </div>}
      {(data.consented || data.all_time_points > 0 || data.history.length > 0) && <p className="weekly-total"><strong>{points(data.all_time_points)} competition points</strong> all time · {data.wins} weeks won · {data.shared_wins} shared wins</p>}
      {data.history.length > 0 && <details className="weekly-history" open><summary>Your recent round results</summary><ol>{data.history.map((round, index) => <li key={`${round.starts_on}-${index}`}><div><strong>{resultLabels[round.result]}</strong><span>{dateLabel(round.starts_on)} – {dateLabel(round.ends_on)}</span></div><div><strong>{points(round.you.points)} pts</strong><span>{round.you.days} qualifying days</span></div>{round.status === 'ended' && <p>Ended early. Earned points kept; no winner.</p>}</li>)}</ol><p className="friendly-privacy">Your latest 12 results. Your all-time total includes every round. Former partners’ details stay private.</p></details>}
    </>}
    <details className="weekly-rules"><summary>How the score works</summary><ul><li>10 points for each qualifying reading day, up to 70 per round.</li><li>Up to 5 extra points for the percentage of your own book read during the round. Finishing 20% adds 1 point.</li><li>Pages require at least 10 per day. Chapter tracking uses the saved daily chapter goal when you join.</li><li>Log dates follow the shared round calendar. Book length, units and competition target stay fixed for the pairing.</li><li>Equal nonzero scores share the win. With no points, there’s no winner.</li><li>Closed results stay fixed. Later log corrections still update your personal reading record. Leaving ends the current round without a winner; earned competition points remain.</li></ul><p>Competition points are separate from your individual reading points.</p></details>
    {error && <p role="alert" className="readar-action-error">{error}</p>}
    <Button variant="secondary" size="sm" disabled={locked} onClick={() => void refresh(true)}>{checking ? 'Checking…' : 'Check round'}</Button>
  </section>;
}
