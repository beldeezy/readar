import { useEffect, useId, useRef, useState } from 'react';
import { apiClient } from '../api/client';
import type { ReadingReflection, ReadingTakeaway, ReflectionOutcome, ReflectionText } from '../api/types';
import Button from './Button';

const outcomes: Record<ReflectionOutcome, string> = {
  helped: 'It helped', mixed: 'Mixed results', did_not_help: 'It didn’t help', too_soon: 'Too soon to tell',
};
interface Draft extends Omit<ReflectionText, 'outcome'> {
  outcome: ReflectionOutcome | '';
  id?: string;
  clientId: string;
  revision: number;
  action: string;
  goal: string;
}
interface Props {
  entry: ReadingTakeaway;
  calendar: { day: string; tz: string };
  disabled: boolean;
  onBusyChange: (busy: boolean) => void;
  onEditingChange: (editing: boolean) => void;
  onSaved: (entry: ReadingTakeaway, message: string, keepVisible?: boolean) => void;
}

export default function ActionReflection({ entry, calendar, disabled, onBusyChange, onEditingChange, onSaved }: Props) {
  const id = useId();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [history, setHistory] = useState<ReadingReflection[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [before, setBefore] = useState<number | null>(null);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState<{ reflectionId?: string } | null>(null);
  const saving = useRef(false);
  const dirty = useRef(false);
  const resultRef = useRef<HTMLTextAreaElement>(null);
  const startRef = useRef<HTMLDivElement>(null);
  const locked = disabled || !!busy;

  useEffect(() => {
    const protect = (event: BeforeUnloadEvent) => {
      if (dirty.current || saving.current) { event.preventDefault(); event.returnValue = ''; }
    };
    window.addEventListener('beforeunload', protect);
    return () => window.removeEventListener('beforeunload', protect);
  }, []);
  useEffect(() => { if (draft) resultRef.current?.focus(); }, [draft?.clientId]);

  const open = (saved: ReadingTakeaway, reflection?: ReadingReflection) => {
    setDraft({ id: reflection?.id, clientId: reflection?.id || crypto.randomUUID(), revision: saved.revision,
      attempted_on: reflection?.attempted_on || calendar.day, outcome: reflection?.outcome || '', result: reflection?.result || '',
      next_step: reflection?.next_step || '', completed: reflection?.completed || false,
      action: reflection?.action_snapshot || saved.next_step || saved.action_text, goal: reflection?.goal_snapshot || saved.goal_context });
    dirty.current = false; setError(''); setConflict(null); onEditingChange(true);
  };
  const close = () => {
    dirty.current = false; setDraft(null); setError(''); setConflict(null); onEditingChange(false);
    startRef.current?.focus();
  };
  const change = (changes: Partial<Draft>) => { dirty.current = true; setDraft((current) => current ? { ...current, ...changes } : current); };
  const mergeHistory = (saved: ReadingReflection) => setHistory((current) => [saved, ...current.filter((row) => row.id !== saved.id)].sort((a, b) => b.sequence - a.sequence));
  const begin = (operation: string) => { saving.current = true; setBusy(operation); setError(''); onBusyChange(true); };
  const end = () => { saving.current = false; setBusy(''); onBusyChange(false); };
  const failed = (err: any, fallback: string) => {
    const detail = err?.response?.data?.detail;
    setError(typeof detail === 'string' ? detail : detail?.message || fallback);
    if (err?.response?.status === 409) setConflict({ reflectionId: detail?.existing_id || draft?.id });
  };

  const loadHistory = async (more = false) => {
    if (historyBusy) return;
    setHistoryBusy(true); setHistoryError('');
    try {
      const data = await apiClient.getReadingReflections(entry.id, more ? before ?? undefined : undefined);
      setHistory((current) => more ? [...current, ...data.items.filter((row) => !current.some((old) => old.id === row.id))] : data.items);
      setBefore(data.next_before); setLoaded(true);
    } catch { setHistoryError('We couldn’t load your reflections. Please try again.'); }
    finally { setHistoryBusy(false); }
  };
  const edit = async (reflectionId: string) => {
    if (locked || saving.current) return;
    begin('edit');
    try {
      const saved = await apiClient.getReadingReflection(entry.id, reflectionId);
      open(saved.takeaway, saved.reflection); onSaved(saved.takeaway, '', true); mergeHistory(saved.reflection);
    } catch { setError('We couldn’t open this reflection. Please try again.'); }
    finally { end(); }
  };
  const save = async () => {
    if (!draft || !draft.outcome || locked || saving.current || conflict) return;
    begin('save');
    const payload = { attempted_on: draft.attempted_on, outcome: draft.outcome, result: draft.result.trim(), next_step: draft.next_step.trim(), completed: draft.completed, expected_revision: draft.revision };
    try {
      const saved = draft.id
        ? await apiClient.updateReadingReflection(entry.id, draft.id, payload, calendar.tz)
        : await apiClient.createReadingReflection(entry.id, { ...payload, client_id: draft.clientId }, calendar.tz);
      mergeHistory(saved.reflection); close();
      onSaved(saved.takeaway, draft.id ? 'Reflection updated.' : saved.takeaway.action_status === 'completed' ? 'Reflection saved. Action completed — you can reopen it anytime.' : 'Reflection saved. Your next step is ready.');
    } catch (err) { failed(err, 'We couldn’t save your reflection. Your draft is still here; please try again.'); }
    finally { end(); }
  };
  const reopen = async () => {
    if (locked || saving.current || conflict) return;
    begin('reopen');
    try { onSaved(await apiClient.reopenReadingAction(entry.id, entry.revision), 'Action reopened. Your past reflections are still here.'); }
    catch (err) { failed(err, 'We couldn’t reopen this action. Please try again.'); }
    finally { end(); }
  };
  const loadLatest = async () => {
    if (!conflict || locked || saving.current) return;
    if (dirty.current && !window.confirm('Replace your unsaved reflection with the latest saved version?')) return;
    begin('latest');
    try {
      if (conflict.reflectionId) {
        const saved = await apiClient.getReadingReflection(entry.id, conflict.reflectionId);
        open(saved.takeaway, saved.reflection); mergeHistory(saved.reflection); onSaved(saved.takeaway, 'Latest reflection loaded. You can edit it now.', true);
      } else {
        const saved = await apiClient.getReadingTakeaway(entry.id);
        if (draft && saved.action_status === 'pending') {
          open(saved); onSaved(saved, 'Latest action loaded. Record your attempt when you’re ready.', true);
        } else { close(); onSaved(saved, 'Latest action loaded.'); }
      }
    } catch { setError('We couldn’t load the latest version. Your draft is still here; please try again.'); }
    finally { end(); }
  };

  return <div ref={startRef} tabIndex={-1} className="reading-reflections" aria-busy={!!busy}>
    {!draft && <div className="reading-takeaways-actions">
      {entry.action_status === 'pending' && <Button size="sm" disabled={locked || !!conflict} onClick={() => open(entry)}>Record attempt</Button>}
      {entry.action_status === 'completed' && <Button size="sm" variant="secondary" disabled={locked || !!conflict} onClick={() => void reopen()}>{busy === 'reopen' ? 'Reopening…' : 'Reopen action'}</Button>}
    </div>}
    {draft && <form className="reading-takeaway-editor" onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <h3>{draft.id ? 'Edit reflection' : 'How did it go?'}</h3>
      <p className="reading-takeaways-text"><strong>What you planned to try:</strong> {draft.action}</p>
      <p className="reading-takeaways-hint reading-takeaways-text">For: {draft.goal}</p>
      <label htmlFor={`${id}-date`}>When did you try it?
        <input id={`${id}-date`} type="date" required max={calendar.day} value={draft.attempted_on} disabled={locked} onChange={(event) => change({ attempted_on: event.target.value })} />
      </label>
      <label htmlFor={`${id}-result`}>What did you try, and what happened?
        <textarea ref={resultRef} id={`${id}-result`} rows={3} maxLength={4000} required value={draft.result} disabled={locked} onChange={(event) => change({ result: event.target.value })} placeholder="What changed? What surprised you?" />
      </label>
      <label htmlFor={`${id}-outcome`}>Did it help with your goal?
        <select id={`${id}-outcome`} required value={draft.outcome} disabled={locked} onChange={(event) => change({ outcome: event.target.value as ReflectionOutcome })}>
          <option value="" disabled>Choose a result</option>{Object.entries(outcomes).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      <label className="reading-reflection-checkbox"><input type="checkbox" checked={draft.completed} disabled={locked} onChange={(event) => change({ completed: event.target.checked })} /> Mark this action completed</label>
      <label htmlFor={`${id}-next`}>{draft.completed ? 'Anything to carry forward? (optional)' : 'What’s one next step?'}
        <textarea id={`${id}-next`} rows={2} maxLength={2000} required={!draft.completed} value={draft.next_step} disabled={locked} onChange={(event) => change({ next_step: event.target.value })} placeholder="A small, concrete step you can return to." />
      </label>
      {draft.id && <p className="reading-takeaways-hint">Correcting an earlier reflection keeps newer plans intact. The latest reflection updates your action if you haven’t since changed its context or reopened it.</p>}
      <div className="reading-takeaways-actions">
        <Button type="submit" disabled={locked || !!conflict || !draft.outcome || !draft.result.trim() || (!draft.completed && !draft.next_step.trim())}>{busy === 'save' ? 'Saving…' : 'Save reflection'}</Button>
        <Button variant="ghost" disabled={locked} onClick={() => { if (!dirty.current || window.confirm('Discard this unsaved reflection?')) close(); }}>Cancel</Button>
      </div>
    </form>}
    {error && <p role="alert" className="readar-action-error">{error}</p>}
    {conflict && <Button variant="secondary" disabled={locked} onClick={() => void loadLatest()}>{busy === 'latest' ? 'Loading…' : 'Load latest version'}</Button>}
    {entry.reflection_count > 0 && <div className="reading-reflection-history">
      <Button variant="ghost" size="sm" aria-expanded={historyOpen} aria-controls={`${id}-history`} disabled={!!draft || locked || historyBusy} onClick={() => {
        setHistoryOpen(!historyOpen); if (!historyOpen && !loaded) void loadHistory();
      }}>{historyOpen ? 'Hide' : 'View'} reflections ({entry.reflection_count})</Button>
      {historyOpen && <div id={`${id}-history`}>
        {historyBusy && <p role="status">Loading reflections…</p>}
        {historyError && <div role="alert"><p>{historyError}</p><Button variant="ghost" disabled={historyBusy || locked || !!draft} onClick={() => void loadHistory()}>Retry reflections</Button></div>}
        <ol className="reading-reflection-list">{history.map((row) => <li key={row.id}>
          <h4><time dateTime={row.attempted_on}>{new Date(`${row.attempted_on}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</time> · {outcomes[row.outcome]}</h4>
          <p className="reading-takeaways-text"><strong>Action:</strong> {row.action_snapshot}</p>
          <p className="reading-takeaways-text">{row.result}</p>
          <p>{row.completed ? 'Marked completed in this reflection.' : 'Kept open for another step.'}</p>
          {row.next_step && <p className="reading-takeaways-text"><strong>Next step noted:</strong> {row.next_step}</p>}
          <details><summary>Original idea and goal</summary><p className="reading-takeaways-text">{row.takeaway_snapshot}</p><p className="reading-takeaways-text"><strong>Goal:</strong> {row.goal_snapshot}</p></details>
          <Button variant="ghost" size="sm" disabled={locked || !!draft} onClick={() => void edit(row.id)} aria-label={`Edit reflection from ${row.attempted_on}`}>Edit reflection</Button>
        </li>)}</ol>
        {before && <Button variant="secondary" size="sm" disabled={locked || historyBusy || !!draft} onClick={() => void loadHistory(true)}>Older reflections</Button>}
      </div>}
    </div>}
  </div>;
}
