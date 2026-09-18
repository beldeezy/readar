import { useEffect, useId, useRef, useState } from 'react';
import { apiClient } from '../api/client';
import type { BookStatusItem, FriendlyPairing, JoinPairing, PairingCommand } from '../api/types';
import Button from './Button';
import './FriendlyCompetition.css';

interface Props {
  books: BookStatusItem[];
  booksReady: boolean;
  disabled: boolean;
  onBusyChange: (busy: boolean) => void;
}

const labels = { inactive: 'Optional', waiting: 'Finding a reader', paired: 'Paired', ended: 'Pairing ended' };

export default function FriendlyCompetition({ books, booksReady, disabled, onBusyChange }: Props) {
  const id = useId();
  const [data, setData] = useState<FriendlyPairing | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [draft, setDraft] = useState<JoinPairing | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [conflict, setConflict] = useState(false);
  const current = useRef<FriendlyPairing | null>(null);
  const saving = useRef(false);
  const fetching = useRef(false);
  const editing = useRef(false);
  const dirty = useRef(false);
  const blocked = useRef(disabled);
  const conflicted = useRef(false);
  const alive = useRef(true);
  const epoch = useRef(0);
  const leaveRequest = useRef<PairingCommand | null>(null);
  const nameInput = useRef<HTMLInputElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  blocked.current = disabled;
  const activeBooks = books.filter((book) => book.status === 'currently_reading');
  const choices = new Map(activeBooks.map((book) => [book.catalog_book_id || book.book_id, book.title || 'Selected book']));
  const locked = disabled || !!busy || loading || checking;

  const apply = (saved: FriendlyPairing) => { current.current = saved; setData(saved); };
  const close = () => { editing.current = false; dirty.current = false; setDraft(null); heading.current?.focus(); };
  const clearConflict = () => { conflicted.current = false; setConflict(false); leaveRequest.current = null; setError(''); };

  const refresh = async (explicit = false) => {
    if (saving.current || fetching.current || (!explicit && (editing.current || blocked.current || conflicted.current))) return;
    if (explicit && dirty.current && !window.confirm('Discard your unsaved pairing choices and load your latest status?')) return;
    if (explicit) { close(); clearConflict(); }
    const requestEpoch = ++epoch.current;
    fetching.current = true; setChecking(true);
    try {
      const saved = await apiClient.getFriendlyPairing();
      if (!alive.current || requestEpoch !== epoch.current) return;
      const previous = current.current;
      apply(saved); setLoadError('');
      if (previous?.status === 'waiting' && saved.status === 'paired') setNotice('You’re paired! Meet your reading partner below.');
      else if (previous?.status === 'paired' && saved.status === 'ended') setNotice('Your pairing has ended. Your individual reading progress is still here.');
      else if (explicit) setNotice('Your pairing status is up to date.');
      if (previous?.revision !== saved.revision) clearConflict();
    } catch {
      if (alive.current && requestEpoch === epoch.current) setLoadError('We couldn’t confirm your latest pairing status. Check again when you’re connected.');
    } finally {
      if (requestEpoch === epoch.current) {
        fetching.current = false;
        if (alive.current) { setLoading(false); setChecking(false); }
      }
    }
  };

  useEffect(() => {
    alive.current = true;
    void refresh();
    const check = () => {
      if (document.visibilityState !== 'visible') return;
      if (current.current?.status === 'waiting' || current.current?.status === 'paired') void refresh();
    };
    const timer = window.setInterval(check, 30000);
    window.addEventListener('focus', check);
    document.addEventListener('visibilitychange', check);
    const protect = (event: BeforeUnloadEvent) => {
      if (dirty.current || saving.current) { event.preventDefault(); event.returnValue = ''; }
    };
    window.addEventListener('beforeunload', protect);
    return () => {
      alive.current = false; epoch.current += 1; fetching.current = false;
      window.clearInterval(timer); window.removeEventListener('focus', check);
      document.removeEventListener('visibilitychange', check); window.removeEventListener('beforeunload', protect);
    };
  }, []);
  useEffect(() => { if (draft) nameInput.current?.focus(); }, [draft?.request_id]);

  const open = () => {
    if (!data || locked || loadError || conflict) return;
    const previousBook = data.selected_book_id && choices.has(data.selected_book_id) ? data.selected_book_id : choices.keys().next().value || '';
    editing.current = true; dirty.current = false; clearConflict(); setNotice('');
    setDraft({ request_id: crypto.randomUUID(), expected_revision: data.revision, reading_name: data.you?.reading_name || '', book_id: previousBook, share_with_partner: false });
  };
  const change = (fields: Partial<JoinPairing>) => { dirty.current = true; setDraft((value) => value ? { ...value, ...fields } : value); };
  const mutate = async (action: 'join' | 'leave') => {
    if (!data || locked || saving.current || conflict || loadError) return;
    if (action === 'join' && (!draft || !draft.share_with_partner || !draft.reading_name.trim() || !choices.has(draft.book_id))) return;
    if (action === 'leave' && !leaveRequest.current) {
      const question = data.status === 'waiting' ? 'Stop looking for a reading partner?' : 'Leave this pairing? Sharing ends for both readers. Your reading progress stays saved.';
      if (!window.confirm(question)) return;
      leaveRequest.current = { request_id: crypto.randomUUID(), expected_revision: data.revision };
    }
    saving.current = true; epoch.current += 1; setChecking(false); setBusy(action); onBusyChange(true); setError(''); setNotice('');
    try {
      const saved = action === 'join'
        ? await apiClient.joinFriendlyPairing({ ...draft!, reading_name: draft!.reading_name.trim() })
        : await apiClient.leaveFriendlyPairing(leaveRequest.current!);
      if (!alive.current) return;
      apply(saved); close(); clearConflict();
      setNotice(saved.status === 'paired' ? 'You’re paired! Meet your reading partner below.'
        : saved.status === 'waiting' ? 'You’re in the queue. Keep reading while we find a partner.'
        : saved.status === 'ended' ? 'Pairing ended. Your individual progress is still yours.' : 'Search stopped. You can join again whenever you’re ready.');
    } catch (err: any) {
      if (!alive.current) return;
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((row: { msg?: string }) => row.msg).filter(Boolean).join(' ')
        : 'We couldn’t save your choice. Try again, or check status if you’re unsure whether it saved.');
      if (err?.response?.status === 409) { conflicted.current = true; setConflict(true); }
    } finally { saving.current = false; if (alive.current) setBusy(''); onBusyChange(false); }
  };

  return <section id="friendly-competition" className="friendly-competition" aria-labelledby={`${id}-heading`} aria-busy={loading || !!busy}>
    <div className="friendly-heading"><div><h2 id={`${id}-heading`} ref={heading} tabIndex={-1}>A little company. A little momentum.</h2><p>Friendly Competition · read alongside another reader.</p></div>
      {data && <span className="friendly-badge">{labels[data.status]}</span>}
    </div>
    {loading && <p role="status">Loading Friendly Competition…</p>}
    {notice && <p role="status" className="reading-notice">{notice}</p>}
    {loadError && <p role="alert" className="readar-action-error">{loadError}</p>}
    {data && !draft && <>
      {data.status === 'inactive' && <><h3>Keep your own book. Find a reading partner.</h3><p>Opt in when you want some shared momentum. We’ll pair you with another reader who has opted in, even if you’re reading different books.</p></>}
      {data.status === 'waiting' && <div className="friendly-state"><h3>You’re in. Your next page is waiting, too.</h3><p>We’ll pair you when another reader joins. You can leave this page and keep reading; your search stays active until you stop it.</p><p className="reading-muted">No match yet. Check back here for your partner. While this page is visible, status updates every 30 seconds.</p><a href="#now-reading-heading">Back to my reading ↓</a></div>}
      {data.status === 'paired' && data.partner && !loadError && <div className="friendly-state">
        <h3>Meet {data.partner.reading_name}</h3><p>They’re reading <strong>{data.partner.book_title}</strong>{data.partner.book_author && <> by {data.partner.book_author}</>}.</p>
        <p>Different books, shared momentum. Keep showing up for your own next page.</p><a href="#now-reading-heading">Log my reading ↓</a>
      </div>}
      {data.status === 'ended' && <div className="friendly-state"><h3>{data.ended_by_you ? 'You’ve left this pairing.' : 'Your reading partner has left.'}</h3><p>Sharing has ended for both readers. Your reading progress, streaks and points stay with you. You haven’t been put into another search.</p></div>}
      {(data.status === 'waiting' || data.status === 'paired') && data.you && <div className="friendly-sharing"><h3>{data.status === 'paired' ? 'What your partner can see' : 'What you’ve chosen to share'}</h3><p><strong>{data.you.reading_name}</strong> · {data.you.book_title}{data.you.book_author && <> by {data.you.book_author}</>}</p><p className="reading-muted">This book stays selected for the pairing. To change these details, leave and choose again.</p></div>}
      {(data.status === 'inactive' || data.status === 'ended') && <div className="friendly-actions">
        {booksReady && choices.size > 0 ? <Button disabled={locked || !!loadError || conflict} onClick={open}>Find a reading partner</Button>
          : <p className="reading-muted">{booksReady ? 'Start a book in Now reading, then come back to find a partner.' : 'Your reading list needs to finish loading before you choose a book to share.'}</p>}
      </div>}
      {(data.status === 'waiting' || data.status === 'paired') && <Button variant="ghost" disabled={locked || !!loadError || conflict} onClick={() => void mutate('leave')}>
        {busy === 'leave' ? 'Leaving…' : data.status === 'waiting' ? 'Stop searching' : 'Leave pairing'}
      </Button>}
    </>}
    {draft && <form className="friendly-form" onSubmit={(event) => { event.preventDefault(); void mutate('join'); }}>
      <h3>Choose what you share</h3>
      <label htmlFor={`${id}-name`}>Reading name <span className="reading-muted">(a nickname is fine)</span>
        <input ref={nameInput} id={`${id}-name`} required maxLength={32} autoComplete="off" value={draft.reading_name} disabled={locked} onChange={(event) => change({ reading_name: event.target.value })} placeholder="How your partner will know you" />
      </label>
      <label htmlFor={`${id}-book`}>The book you’re reading
        <select id={`${id}-book`} required value={draft.book_id} disabled={locked || !booksReady} onChange={(event) => change({ book_id: event.target.value })}>
          <option value="" disabled>Choose a book from Now reading</option>{[...choices].map(([bookId, title]) => <option key={bookId} value={bookId}>{title}</option>)}
        </select>
      </label>
      {!choices.has(draft.book_id) && <p role="status">That book is no longer in Now reading. Choose another started book before joining.</p>}
      <p>We’ll match you with any available reader who has opted in. You don’t need to read the same book.</p>
      <label className="friendly-consent"><input type="checkbox" required checked={draft.share_with_partner} disabled={locked} onChange={(event) => change({ share_with_partner: event.target.checked })} /><span>I want a partner and agree to share my reading name and this book’s title and author with them.</span></label>
      <p className="friendly-privacy">Your email, onboarding answers, notes and reflections stay private. You can stop searching or leave the pairing at any time.</p>
      <div className="friendly-actions"><Button type="submit" disabled={locked || conflict || !booksReady || !choices.has(draft.book_id) || !draft.share_with_partner || !draft.reading_name.trim()}>{busy === 'join' ? 'Finding a partner…' : 'Join Friendly Competition'}</Button>
        <Button variant="ghost" disabled={locked} onClick={() => { if (!dirty.current || window.confirm('Discard these unsaved pairing choices?')) { close(); clearConflict(); void refresh(true); } }}>Cancel</Button>
      </div>
    </form>}
    {error && <p role="alert" className="readar-action-error">{error}</p>}
    {(!draft || conflict || error) && <div className="friendly-actions"><Button variant="secondary" size="sm" disabled={locked} onClick={() => void refresh(true)}>{checking ? 'Checking…' : 'Check status'}</Button></div>}
    {!draft && <p className="friendly-privacy">Only your chosen reading name and selected book title/author are shared with your current partner. Your email, notes, takeaways, reflections and onboarding answers stay private.</p>}
  </section>;
}
