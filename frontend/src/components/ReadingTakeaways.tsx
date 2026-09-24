import { useEffect, useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { BookStatusItem, ReadingTakeaway, ReadingTakeawayText, TakeawayFilter } from '../api/types';
import Button from './Button';
import ActionReflection from './ActionReflection';
import { useReadingCalendar } from '../hooks/useReadingCalendar';
import './ReadingTakeaways.css';

export interface TakeawayBookRequest { id: string; title: string; request: number; }
interface Draft extends ReadingTakeawayText {
  id?: string;
  revision?: number;
  clientId: string;
  bookId: string;
  bookTitle: string;
}
interface Props {
  books: BookStatusItem[];
  requestedBook: TakeawayBookRequest | null;
  disabled: boolean;
  onBusyChange: (busy: boolean) => void;
  onEditingChange: (editing: boolean) => void;
}

export default function ReadingTakeaways({ books, requestedBook, disabled, onBusyChange, onEditingChange }: Props) {
  const id = useId();
  const calendar = useReadingCalendar();
  const [filter, setFilter] = useState<TakeawayFilter>('all');
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [items, setItems] = useState<ReadingTakeaway[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [reload, setReload] = useState(0);
  const [goalSuggestion, setGoalSuggestion] = useState('');
  const [cursor, setCursor] = useState<string | null>(null);
  const [moreBusy, setMoreBusy] = useState(false);
  const [editor, setEditor] = useState<Draft | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [conflictId, setConflictId] = useState('');
  const [notice, setNotice] = useState('');
  const saving = useRef(false);
  const dirty = useRef(false);
  const handledRequest = useRef<number | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setLoadError(''); setItems([]); setCursor(null);
    apiClient.getReadingTakeaways(undefined, filter).then((data) => {
      if (cancelled) return;
      setItems(data.items); setGoalSuggestion(data.suggested_goal); setCursor(data.next_cursor);
    }).catch(() => {
      if (!cancelled) setLoadError('We couldn’t load your takeaways. Your saved ideas haven’t been removed.');
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [reload, filter]);

  const openNew = (bookId: string, bookTitle: string) => {
    setEditor({ clientId: crypto.randomUUID(), bookId, bookTitle, takeaway: '', action_text: '', goal_context: goalSuggestion });
    dirty.current = false; setError(''); setConflictId(''); setNotice(''); onEditingChange(true);
  };

  useEffect(() => {
    if (!requestedBook || loading || handledRequest.current === requestedBook.request || editor || reviewing) return;
    handledRequest.current = requestedBook.request;
    openNew(requestedBook.id, requestedBook.title);
  }, [requestedBook, loading, editor, reviewing]);

  useEffect(() => {
    if (editor) {
      inputRef.current?.focus({ preventScroll: true });
      inputRef.current?.scrollIntoView({ block: 'center' });
    }
  }, [editor?.clientId]);

  useEffect(() => {
    const protectDraft = (event: BeforeUnloadEvent) => {
      if (dirty.current || saving.current) { event.preventDefault(); event.returnValue = ''; }
    };
    window.addEventListener('beforeunload', protectDraft);
    return () => window.removeEventListener('beforeunload', protectDraft);
  }, []);

  const matchesFilter = (entry: ReadingTakeaway) => filter === 'all' || entry.action_status === filter;
  const mergeSaved = (saved: ReadingTakeaway, keepVisible = false) => setItems((current) => [...(keepVisible || matchesFilter(saved) ? [saved] : []), ...current.filter((entry) => entry.id !== saved.id)]);
  const openSaved = (entry: ReadingTakeaway) => {
    setEditor({ ...entry, clientId: entry.id, bookId: entry.book_id, bookTitle: entry.book_title });
    dirty.current = false; setError(''); setConflictId(''); setNotice(''); onEditingChange(true);
  };
  const closeEditor = () => {
    setEditor(null); setItems((current) => current.filter(matchesFilter)); dirty.current = false; setError(''); setConflictId(''); onEditingChange(false);
    headingRef.current?.focus();
  };
  const change = (field: keyof ReadingTakeawayText, value: string) => {
    dirty.current = true;
    setEditor((current) => current ? { ...current, [field]: value } : current);
  };

  const save = async () => {
    if (!editor || saving.current || disabled || conflictId) return;
    saving.current = true; setBusy('save'); onBusyChange(true); setError(''); setNotice('');
    const payload = { takeaway: editor.takeaway.trim(), action_text: editor.action_text.trim(), goal_context: editor.goal_context.trim() };
    try {
      const saved = editor.id
        ? await apiClient.updateReadingTakeaway(editor.id, { ...payload, expected_revision: editor.revision! })
        : await apiClient.createReadingTakeaway({ ...payload, book_id: editor.bookId, client_id: editor.clientId });
      mergeSaved(saved); closeEditor();
      setNotice(saved.action_text ? 'Takeaway saved. Your next step is ready when you are.' : 'Idea saved. Add one thing to try whenever you’re ready.');
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : detail?.message || 'We couldn’t save your takeaway. Your draft is still here; please try again.');
      if (err?.response?.status === 409) setConflictId(detail?.existing_id || editor.id || '');
    } finally { saving.current = false; setBusy(''); onBusyChange(false); }
  };

  const loadLatest = async () => {
    if (!conflictId || saving.current || disabled) return;
    if (dirty.current && !window.confirm('Replace your unsaved edits with the latest saved version?')) return;
    saving.current = true; setBusy('latest'); onBusyChange(true);
    try {
      const saved = await apiClient.getReadingTakeaway(conflictId);
      mergeSaved(saved, true); openSaved(saved);
      setNotice('Latest saved version loaded. You can edit it now.');
    } catch { setError('We couldn’t load the latest version. Your draft is still here; please try again.'); }
    finally { saving.current = false; setBusy(''); onBusyChange(false); }
  };

  const loadMore = async () => {
    if (!cursor || moreBusy) return;
    setMoreBusy(true); setLoadError('');
    try {
      const data = await apiClient.getReadingTakeaways(cursor, filter);
      setItems((current) => [...current, ...data.items.filter((entry) => !current.some((saved) => saved.id === entry.id))]);
      setCursor(data.next_cursor);
    } catch { setLoadError('We couldn’t load more takeaways. Try again below.'); }
    finally { setMoreBusy(false); }
  };

  const choices = new Map(books.filter((book) => book.status === 'currently_reading').map((book) => [book.catalog_book_id || book.book_id, book.title || 'Selected book']));
  items.forEach((entry) => choices.set(entry.book_id, entry.book_title));
  if (editor) choices.set(editor.bookId, editor.bookTitle);
  const firstBook = choices.entries().next().value as [string, string] | undefined;
  const locked = disabled || !!busy || loading;

  return <section id="reading-takeaways" className="reading-takeaways" aria-labelledby={`${id}-heading`} aria-busy={!!busy}>
    <div className="reading-takeaways-heading">
      <div><h2 id={`${id}-heading`} ref={headingRef} tabIndex={-1}>Put it to work</h2><p>One useful idea. One step toward what matters to you.</p></div>
      {!editor && !reviewing && firstBook && <Button variant="secondary" disabled={locked} onClick={() => openNew(...firstBook)}>New takeaway</Button>}
    </div>
    <p className="reading-takeaways-hint">Your private takeaways and actions, kept with their books.</p>
    <label className="reading-takeaways-filter" htmlFor={`${id}-filter`}>Show
      <select id={`${id}-filter`} value={filter} disabled={locked || moreBusy || !!editor || !!reviewing} onChange={(event) => { setFilter(event.target.value as TakeawayFilter); setNotice(''); }}>
        <option value="all">All takeaways</option><option value="pending">Pending actions</option><option value="completed">Completed actions</option><option value="idea">Ideas without an action</option>
      </select>
    </label>
    {notice && <p role="status" className="reading-notice">{notice}</p>}
    {loading && <p role="status" className="reading-muted">Loading your takeaways…</p>}
    {loadError && <div role="alert"><p className="readar-action-error">{loadError}</p><Button variant="ghost" disabled={locked || moreBusy || !!editor || !!reviewing} onClick={() => setReload((n) => n + 1)}>Reload takeaways</Button></div>}
    {editor && <form className="reading-takeaway-editor" onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <h3>{editor.id ? 'Edit your takeaway' : 'Capture what stood out'}</h3>
      <label htmlFor={`${id}-book`}>Book
        <select id={`${id}-book`} value={editor.bookId} disabled={locked || !!editor.id || !!conflictId} onChange={(event) => {
          dirty.current = true; setEditor({ ...editor, bookId: event.target.value, bookTitle: choices.get(event.target.value)! });
        }}>{[...choices].map(([bookId, title]) => <option key={bookId} value={bookId}>{title}</option>)}</select>
      </label>
      <label htmlFor={`${id}-idea`}>What stood out?
        <textarea ref={inputRef} id={`${id}-idea`} rows={3} maxLength={4000} required value={editor.takeaway} disabled={locked} onChange={(event) => change('takeaway', event.target.value)} placeholder="A useful idea, in your own words…" />
      </label>
      <label htmlFor={`${id}-action`}>One thing I’ll try <span className="reading-takeaways-optional">(optional)</span>
        <textarea id={`${id}-action`} rows={2} maxLength={2000} value={editor.action_text} disabled={locked} onChange={(event) => change('action_text', event.target.value)} placeholder="For example: ask two customers where they got stuck this week." />
      </label>
      <p className="reading-takeaways-hint">Keep it small enough to try. You can save the idea first and add an action later. {editor.id && "Replacing or clearing the action resets its next step and completion state. Past reflections stay saved."}</p>
      <label htmlFor={`${id}-goal`}>The goal or challenge this serves
        <textarea id={`${id}-goal`} rows={2} maxLength={2000} required value={editor.goal_context} disabled={locked} onChange={(event) => change('goal_context', event.target.value)} placeholder="What do you want this idea to help you improve?" />
      </label>
      <p className="reading-takeaways-hint">{editor.id ? 'This is the context saved with your idea. You can refine it.' : goalSuggestion ? 'Started from your onboarding. Adjust it for this idea.' : 'Add the context that makes this idea useful to you.'} Updating this entry won’t change your profile.</p>
      {error && <p role="alert" className="readar-action-error">{error}</p>}
      <div className="reading-takeaways-actions">
        <Button type="submit" disabled={locked || !!conflictId || !editor.takeaway.trim() || !editor.goal_context.trim()}>{busy === 'save' ? 'Saving…' : editor.id ? 'Save changes' : 'Save takeaway'}</Button>
        {conflictId && <Button variant="secondary" disabled={locked} onClick={() => void loadLatest()}>{busy === 'latest' ? 'Loading…' : 'Load latest version'}</Button>}
        <Button variant="ghost" disabled={locked} onClick={() => { if (!dirty.current || window.confirm('Discard this unsaved draft?')) closeEditor(); }}>Cancel</Button>
      </div>
    </form>}
    {!loading && !loadError && items.length === 0 && !editor && <p className="reading-takeaways-empty">{filter === 'all' ? 'Nothing captured yet. When an idea stands out, choose Capture a takeaway on a book in Now reading.' : filter === 'pending' ? 'No pending actions. Add an action to an idea, or reopen a completed action.' : filter === 'completed' ? 'No completed actions yet. Record what happened when you try an action.' : 'No ideas without an action. You can save a takeaway first and add an action later.'}</p>}
    <ul className="reading-takeaways-list">{items.map((entry) => <li key={entry.id}>
      <div className="reading-takeaways-item-heading">
        <Link to={`/book/${entry.book_id}`}>{entry.book_title}{entry.book_author ? ` · ${entry.book_author}` : ''}</Link>
        <span>{entry.action_status === 'completed' ? 'Completed' : entry.action_status === 'pending' ? 'Pending' : 'Idea saved'}</span>
      </div>
      <h3>What stood out</h3><p className="reading-takeaways-text">{entry.takeaway}</p>
      <div className="reading-takeaways-next"><h3>Action</h3><p className="reading-takeaways-text">{entry.action_text || 'No action yet. Add a small next step when you’re ready.'}</p></div>
      {entry.next_step && <div className="reading-takeaways-next"><h3>{entry.action_status === 'completed' ? 'Next step noted' : 'Next step'}</h3><p className="reading-takeaways-text">{entry.next_step}</p></div>}
      <h3>My goal or challenge</h3><p className="reading-takeaways-text reading-muted">{entry.goal_context}</p>
      <div className="reading-takeaways-actions"><small>Saved {new Date(entry.updated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</small>
        <Button size="sm" variant="ghost" disabled={locked || !!editor || !!reviewing} onClick={() => openSaved(entry)} aria-label={`Edit takeaway from ${entry.book_title}`}>{entry.action_text ? 'Edit' : 'Add action / edit'}</Button>
      </div>
      <ActionReflection entry={entry} calendar={calendar} disabled={locked || !!editor || (!!reviewing && reviewing !== entry.id)} onBusyChange={onBusyChange}
        onEditingChange={(editing) => { setReviewing(editing ? entry.id : null); onEditingChange(editing); if (!editing) setItems((current) => current.filter(matchesFilter)); }}
        onSaved={(saved, message, keepVisible) => { mergeSaved(saved, keepVisible); setNotice(message); }} />
    </li>)}</ul>
    {cursor && <Button variant="secondary" disabled={locked || moreBusy || !!editor || !!reviewing} onClick={() => void loadMore()}>{moreBusy ? 'Loading…' : 'Load more takeaways'}</Button>}
  </section>;
}
