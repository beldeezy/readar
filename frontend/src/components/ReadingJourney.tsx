import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { ReadingCompletion, ReadingJourney } from '../api/types';
import Button from './Button';
import './ReadingJourney.css';

export function ReadingReturnCard({ journey, tz, onSaved }: { journey: ReadingJourney; tz: string; onSaved: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const saving = useRef(false);
  async function preference(show: boolean, days: 0 | 1 | 7) {
    if (saving.current) return;
    saving.current = true; setBusy(true); setError('');
    try { await apiClient.saveReadingJourneyPreferences(show, days, tz); onSaved(); }
    catch { setError("We couldn't save that preference. Please try again."); }
    finally { saving.current = false; setBusy(false); }
  }
  const action = journey.next_action;
  return <section className="reading-return" aria-label="Your next step">
    {action && <>
      <p className="reading-eyebrow">A next step for you</p>
      <h2>{action.title}</h2><p>{action.detail}</p>
      {action.href.startsWith('#') ? <a className="reading-text-link" href={action.href}>{action.label} →</a>
        : <Link className="reading-text-link" to={action.href}>{action.label} →</Link>}
    </>}
    <details className="reading-reminder-settings">
      <summary>{action ? 'Reminder preferences' : 'Next-step reminders are paused'}</summary>
      <p>These reminders appear here when you return. Your email preferences stay as you set them.</p>
      <div className="reading-book-actions">
        <Button size="sm" variant="secondary" disabled={busy} onClick={() => preference(true, 0)}>Show next steps</Button>
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => preference(true, 1)}>Snooze until tomorrow</Button>
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => preference(true, 7)}>Snooze for a week</Button>
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => preference(false, 0)}>Turn off</Button>
      </div>
      {busy && <p role="status">Saving preference…</p>}
      {error && <p className="readar-action-error" role="alert">{error}</p>}
    </details>
  </section>;
}

export function FinishBook({ bookId, title, challenge, tz, onSaved, onCancel, onBusyChange }: {
  bookId: string; title: string; challenge: string; tz: string;
  onSaved: (saved: ReadingCompletion) => void; onCancel: () => void; onBusyChange: (busy: boolean) => void;
}) {
  const [rating, setRating] = useState('');
  const [reflection, setReflection] = useState('');
  const [updateChallenge, setUpdateChallenge] = useState(false);
  const [nextChallenge, setNextChallenge] = useState(challenge);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false);
  const saving = useRef(false);
  const requestId = useRef(crypto.randomUUID());
  // Keep the challenge the reader actually reviewed, even if a background read refreshes.
  const originalChallenge = useRef(challenge);
  const id = `finish-${bookId}`;
  return <form className="reading-finish" aria-label={`Finish ${title}`} onSubmit={async (event) => {
    event.preventDefault();
    if (saving.current || conflict) return;
    saving.current = true; setBusy(true); onBusyChange(true); setError('');
    try {
      const saved = await apiClient.finishReadingBook(bookId, {
        request_id: requestId.current, rating: rating ? Number(rating) : null, reflection,
        next_challenge: updateChallenge ? nextChallenge.trim() : null,
        expected_challenge: updateChallenge ? originalChallenge.current : null,
      }, tz);
      onSaved(saved);
    } catch (cause: any) {
      setConflict(cause?.response?.status === 409);
      setError(cause?.response?.data?.detail || "We couldn't save your finish. Your answers are still here. Please try again.");
    } finally { saving.current = false; setBusy(false); onBusyChange(false); }
  }}>
    <h3>Finished {title}?</h3>
    <p>A chapter completed. Take a moment to notice what you’re taking with you.</p>
    <p className="reading-muted">The check-in below is optional. Your progress and takeaways stay saved.</p>
    <label htmlFor={`${id}-rating`}>How useful was this book? (optional)</label>
    <select id={`${id}-rating`} value={rating} disabled={busy || conflict} onChange={event => setRating(event.target.value)}>
      <option value="">Skip rating</option>
      <option value="1">1 — Not useful for me</option><option value="2">2 — A little useful</option>
      <option value="3">3 — Some useful ideas</option><option value="4">4 — Very useful</option><option value="5">5 — Exactly what I needed</option>
    </select>
    <label htmlFor={`${id}-reflection`}>What changed for you? (optional)</label>
    <textarea id={`${id}-reflection`} rows={3} maxLength={2000} value={reflection} disabled={busy || conflict}
      onChange={event => setReflection(event.target.value)} placeholder="An idea you used, a new perspective, or what didn’t fit…" />
    <p className="reading-muted">This check-in is private.</p>
    {originalChallenge.current && <>
      <p><strong>Your current challenge</strong><br />{originalChallenge.current}</p>
      <label className="reading-finish-check"><input type="checkbox" checked={updateChallenge} disabled={busy || conflict}
        onChange={event => setUpdateChallenge(event.target.checked)} /> I’d like my next book to focus on something different</label>
      {updateChallenge && <><label htmlFor={`${id}-challenge`}>What would you like help with next?</label>
        <textarea id={`${id}-challenge`} required rows={3} maxLength={2000} value={nextChallenge} disabled={busy || conflict}
          onChange={event => setNextChallenge(event.target.value)} /></>}
    </>}
    {error && <p role="alert" className="readar-action-error">{error}</p>}
    <div className="reading-book-actions">
      <Button type="submit" disabled={busy || conflict || (updateChallenge && !nextChallenge.trim())}>{busy ? 'Saving your finish…' : 'Save finished book'}</Button>
      <Button variant="ghost" type="button" disabled={busy} onClick={onCancel}>{conflict ? 'Close and refresh Reading' : 'Keep reading'}</Button>
    </div>
  </form>;
}

export function FinishedBooks({ books }: { books: ReadingCompletion[] }) {
  if (!books.length) return null;
  return <section className="reading-section" aria-labelledby="finished-books-heading">
    <h2 id="finished-books-heading">Recently finished</h2>
    <ul className="reading-list">{books.map(book => <li className="reading-book" key={book.book_id}>
      <h3>{book.title}</h3>
      <p className="reading-muted">Finished {book.completed_on}{book.rating ? ` · ${book.rating}/5 for usefulness` : ''}</p>
      {book.reflection && <p className="reading-finish-reflection">{book.reflection}</p>}
      {book.challenge_after !== book.challenge_before && <p><strong>Next focus:</strong> {book.challenge_after}</p>}
    </li>)}</ul>
    <Link className="reading-text-link" to="/recommendations">Find my next book →</Link>
  </section>;
}
