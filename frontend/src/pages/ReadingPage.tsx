import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Search } from 'lucide-react';
import { apiClient } from '../api/client';
import type { Book, BookStatusItem, ReadingStatus, ReadingJourney as Journey, ReadingCompletion } from '../api/types';
import Button from '../components/Button';
import { ReadingReturnCard, FinishBook, FinishedBooks } from '../components/ReadingJourney';
import { useReadingCalendar } from '../hooks/useReadingCalendar';
import BookReadingProgress from '../components/BookReadingProgress';
import ReadingRewards from '../components/ReadingRewards';
import FriendlyCompetition from '../components/FriendlyCompetition';
import ReadingTakeaways, { type TakeawayBookRequest } from '../components/ReadingTakeaways';
import EmptyState from '../components/EmptyState';
import ScrollTopButton from '../components/ScrollTopButton';
import { BookSignalArt } from '../components/illustrations';
import './ReadingPage.css';

const READING_STATES = new Set(['reading_next', 'waiting_for_book', 'currently_reading']);

/** A choice stays here until the reader explicitly starts or removes it. */
export default function ReadingPage() {
  const location = useLocation();
  const { day, tz } = useReadingCalendar();
  const [journey, setJourney] = useState<Journey | null>(null);
  const [journeyError, setJourneyError] = useState('');
  const [journeyRefresh, setJourneyRefresh] = useState(0);
  const [finishing, setFinishing] = useState<string | null>(null);
  const [finished, setFinished] = useState<ReadingCompletion | null>(null);
  const [items, setItems] = useState<BookStatusItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [reload, setReload] = useState(0);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Book[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [searchRetry, setSearchRetry] = useState(0);
  const [pending, setPending] = useState<{ id: string; action: string } | null>(null);
  const saving = useRef(false);
  const [actionError, setActionError] = useState('');
  const [notice, setNotice] = useState('');
  const [rewardsRefresh, setRewardsRefresh] = useState(0);
  const [takeawayBook, setTakeawayBook] = useState<TakeawayBookRequest | null>(null);
  const [takeawayEditing, setTakeawayEditing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setJourneyError('');
    apiClient.getReadingJourney(tz).then(data => { if (!cancelled) setJourney(data); })
      .catch(() => { if (!cancelled) setJourneyError("We couldn't load your next step or finished books. Your reading list is still available."); });
    return () => { cancelled = true; };
  }, [location.key, journeyRefresh, rewardsRefresh, reload, day, tz]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError('');
    apiClient.getBookStatusList().then((data) => {
      if (!cancelled) setItems(data.filter((item) => READING_STATES.has(item.status)));
    }).catch(() => {
      if (!cancelled) setLoadError("We couldn't load your reading list. Your saved choices haven't been removed.");
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [location.key, reload]);

  useEffect(() => {
    let cancelled = false;
    setResults([]);
    setSearchError('');
    if (query.trim().length < 2) { setSearching(false); return; }
    setSearching(true);
    const timer = setTimeout(async () => {
      try {
        const books = await apiClient.getBooks({ q: query.trim(), curated: true, limit: 8 });
        if (!cancelled) {
          const selectedIds = new Set(items.map((item) => item.book_id));
          setResults(books.filter((book) => !selectedIds.has(book.id)));
        }
      } catch {
        if (!cancelled) setSearchError("We couldn't search right now. Please try again.");
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 250);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [query, items, searchRetry]);

  const beginSave = (id: string, action: string) => {
    if (saving.current || loading || loadError) return false;
    saving.current = true;
    setPending({ id, action });
    setActionError('');
    setNotice('');
    return true;
  };
  const endSave = () => { saving.current = false; setPending(null); };

  const choose = async (book: Book) => {
    if (!beginSave(book.id, 'choose')) return;
    try {
      const saved = await apiClient.selectBookForReading({ book_id: book.id });
      setItems((current) => [{
        book_id: book.id, status: saved.status, updated_at: new Date().toISOString(),
        title: book.title, author_name: book.author_name,
        cover_image_url: book.cover_image_url || book.thumbnail_url,
      }, ...current.filter((item) => item.book_id !== book.id)]);
      setQuery('');
      setJourneyRefresh(value => value + 1);
      setNotice(`${book.title} is saved to your reading list.`);
    } catch {
      setActionError(`We couldn't save ${book.title}. Please try again.`);
    } finally { endSave(); }
  };

  const changeStatus = async (item: BookStatusItem, status: ReadingStatus) => {
    if (!beginSave(item.book_id, status)) return;
    try {
      await apiClient.setBookStatus({ book_id: item.book_id, status, source: 'reading_page' });
      setItems((current) => current.map((book) => book.book_id === item.book_id ? { ...book, status } : book));
      setJourneyRefresh(value => value + 1);
      const label = item.title || 'Your book';
      setNotice(status === 'currently_reading' ? `${label} is now in Now reading.`
        : status === 'waiting_for_book' ? `${label} is saved while you wait for your copy.`
        : `${label} is back in Up next.`);
    } catch {
      setActionError(`We couldn't update ${item.title || 'this book'}. Please try again.`);
    } finally { endSave(); }
  };

  const remove = async (item: BookStatusItem) => {
    if (!beginSave(item.book_id, 'remove')) return;
    try {
      await apiClient.deleteBookStatus(item.book_id);
      setItems((current) => current.filter((book) => book.book_id !== item.book_id));
      setJourneyRefresh(value => value + 1);
      setNotice(`${item.title || 'The book'} was removed from your reading list.`);
    } catch {
      setActionError("We couldn't remove that book. Please try again.");
    } finally { endSave(); }
  };

  const disabled = pending !== null || loading || !!loadError || finishing !== null;
  const active = items.filter((item) => item.status === 'currently_reading');
  const upcoming = items.filter((item) => item.status !== 'currently_reading');

  const renderBook = (item: BookStatusItem) => {
    const started = item.status === 'currently_reading';
    const waiting = item.status === 'waiting_for_book';
    const busy = pending?.id === item.book_id;
    const purchaseUrl = item.purchase_url || (item.title
      ? `https://www.amazon.com/s?k=${encodeURIComponent(`${item.title} ${item.author_name || ''}`.trim())}` : null);
    return (
      <li key={item.book_id} id={`reading-book-${item.catalog_book_id || item.book_id}`} className="reading-book" aria-busy={busy}>
        <div className="reading-book-header">
          {item.cover_image_url && <img className="reading-cover" src={item.cover_image_url} alt="" loading="lazy" referrerPolicy="no-referrer" />}
          <div>
            <Link className="reading-item-link" to={`/book/${item.book_id}`}>
              <h3>{item.title || 'Selected book'}</h3>
            </Link>
            {item.author_name && <p className="reading-muted">by {item.author_name}</p>}
            {waiting && <p className="reading-waiting">Waiting for my copy</p>}
          </div>
        </div>
        {started ? <BookReadingProgress bookId={item.catalog_book_id || item.book_id} disabled={disabled} onSaved={() => setRewardsRefresh((n) => n + 1)} onBusyChange={(isBusy) => {
          saving.current = isBusy;
          setPending(isBusy ? { id: item.book_id, action: 'progress' } : null);
        }} /> : <p className="reading-muted">
          {waiting ? 'Your choice is saved. Come back when your copy is ready.'
            : 'Have a copy? Start when you’re ready. Still getting it? Keep your choice here.'}
        </p>}
        <div className="reading-book-actions">
          {started && <Button variant="secondary" disabled={disabled || takeawayEditing || !journey || !!journeyError} onClick={() => { setFinishing(item.book_id); setFinished(null); }}>Finish book</Button>}
          {started && <Button variant="secondary" disabled={disabled || takeawayEditing} title={takeawayEditing ? 'Save or cancel your open takeaway first.' : undefined} onClick={() => setTakeawayBook((current) => ({ id: item.catalog_book_id || item.book_id, title: item.title || 'Selected book', request: (current?.request ?? 0) + 1 }))}>Capture a takeaway</Button>}
          {!started && (
            <Button onClick={() => changeStatus(item, 'currently_reading')} disabled={disabled}>
              {busy && pending?.action === 'currently_reading' ? 'Starting…' : 'Start reading'}
            </Button>
          )}
          {!started && !waiting && (
            <Button variant="secondary" onClick={() => changeStatus(item, 'waiting_for_book')} disabled={disabled}>
              {busy && pending?.action === 'waiting_for_book' ? 'Saving…' : "I'm waiting for my copy"}
            </Button>
          )}
          {(started || waiting) && (
            <Button variant="ghost" onClick={() => changeStatus(item, 'reading_next')} disabled={disabled}>
              {busy && pending?.action === 'reading_next' ? 'Saving…' : 'Move to Up next'}
            </Button>
          )}
          {!started && purchaseUrl && <a className="reading-text-link" href={purchaseUrl} target="_blank" rel="noopener noreferrer">Get book ↗</a>}
          <button className="reading-remove" onClick={() => remove(item)} disabled={disabled} aria-label={`Remove ${item.title || 'book'} from reading list`}>
            {busy && pending?.action === 'remove' ? 'Removing…' : 'Remove'}
          </button>
        </div>
        {finishing === item.book_id && journey && <FinishBook bookId={item.catalog_book_id || item.book_id} title={item.title || 'this book'} challenge={journey.challenge} tz={tz}
          onCancel={() => { setFinishing(null); setReload(value => value + 1); }}
          onBusyChange={isBusy => { saving.current = isBusy; setPending(isBusy ? { id: item.book_id, action: 'finish' } : null); }}
          onSaved={saved => {
            setFinished(saved); setFinishing(null);
            setItems(current => current.filter(book => book.book_id !== item.book_id));
            setJourneyRefresh(value => value + 1);
          }} />}
      </li>
    );
  };

  return (
    <div className="reading-page rd-scan-bg">
      <div className="container">
        <h1 className="reading-title">Reading</h1>
        <p className="reading-sub reading-muted">Your next book, and the ones you’ve started.</p>
        {journeyError ? <div role="alert" className="reading-feedback"><p>{journeyError}</p><Button onClick={() => setJourneyRefresh(value => value + 1)}>Reload next step</Button></div>
          : journey && <ReadingReturnCard journey={journey} tz={tz} onSaved={() => setJourneyRefresh(value => value + 1)} />}
        {finished && <section className="reading-finish-saved" role="status" aria-live="polite">
          <h2>You finished {finished.title}.</h2><p>Your book and check-in are saved. Take that idea into your next chapter.</p>
          <Link className="reading-text-link" to="/recommendations">Find my next book →</Link> · <a className="reading-text-link" href="#reading-takeaways">Revisit my takeaways</a>
        </section>}
        <ReadingRewards refreshKey={rewardsRefresh} />
        <p className="reading-takeaways-shortcut"><a href="#reading-takeaways">My takeaways & actions ↓</a> · <a href="#friendly-competition">Friendly Competition ↓</a></p>
        <div className="reading-add">
          <label htmlFor="reading-search" className="reading-search-label">Choose a book</label>
          <div className="reading-search">
            <Search size={18} strokeWidth={2} className="reading-search-icon" aria-hidden="true" />
            <input id="reading-search" className="reading-search-input" placeholder="Search by title or author…"
              value={query} onChange={(event) => setQuery(event.target.value)} disabled={disabled} autoComplete="off" />
          </div>
          {searching && <p role="status" className="reading-muted">Searching…</p>}
          {searchError && <div role="alert"><p className="readar-action-error">{searchError}</p><Button variant="ghost" onClick={() => setSearchRetry((n) => n + 1)}>Try search again</Button></div>}
          {!searching && !searchError && query.trim().length >= 2 && results.length === 0 && <p className="reading-muted">No new books found. Try another title or author.</p>}
          {results.length > 0 && <ul className="reading-results">
            {results.map((book) => <li key={book.id}>
              <button type="button" className="reading-result" onClick={() => choose(book)} disabled={disabled}>
                <span className="reading-result-add" aria-hidden="true">+</span>
                <span><strong>{book.title}</strong>{book.author_name && <span className="reading-muted"> by {book.author_name}</span>}<span className="reading-result-hint">{pending?.id === book.id ? 'Saving…' : 'Choose this book'}</span></span>
              </button>
            </li>)}
          </ul>}
          <p className="reading-browse"><Link to="/recommendations">Find a recommendation</Link> · <Link to="/shelves">Browse saved books</Link></p>
        </div>
        <div className="reading-feedback">
          {notice && <p role="status" className="reading-notice">{notice}</p>}
          {actionError && <p role="alert" className="readar-action-error">{actionError}</p>}
        </div>
        {loading ? <p className="reading-sub reading-muted" role="status">Loading your reading list…</p>
          : loadError ? <div className="reading-feedback" role="alert"><p className="readar-action-error">{loadError}</p><Button onClick={() => setReload((n) => n + 1)}>Try again</Button></div>
          : items.length === 0 ? <EmptyState art={<BookSignalArt />} title="Your next chapter starts here" message="Choose a book from your recommendations or search above. We’ll keep it here until you’re ready to start." action={<Link className="reading-text-link" to="/recommendations">Find my next book →</Link>} />
          : <>
            <section className="reading-section" aria-labelledby="now-reading-heading">
              <h2 id="now-reading-heading">Now reading</h2>
              {active.length > 0 ? <ul className="reading-list">{active.map(renderBook)}</ul> : <p className="reading-muted">When you’re ready, select Start reading on a book below.</p>}
            </section>
            {upcoming.length > 0 && <section className="reading-section" aria-labelledby="up-next-heading">
              <h2 id="up-next-heading">Up next</h2>
              <ul className="reading-list">{upcoming.map(renderBook)}</ul>
            </section>}
          </>}
        {journey && <FinishedBooks books={journey.completions} />}
        <FriendlyCompetition books={items} refreshKey={rewardsRefresh} booksReady={!loading && !loadError} disabled={pending !== null || finishing !== null} onBusyChange={(isBusy) => {
          saving.current = isBusy;
          setPending(isBusy ? { id: 'competition', action: 'pairing' } : null);
        }} />
        <ReadingTakeaways books={items} requestedBook={takeawayBook} disabled={pending !== null || finishing !== null} onEditingChange={setTakeawayEditing} onBusyChange={(isBusy) => {
          saving.current = isBusy;
          setPending(isBusy ? { id: 'takeaways', action: 'takeaway' } : null);
          if (!isBusy) setJourneyRefresh(value => value + 1);
        }} />
      </div>
      <ScrollTopButton />
    </div>
  );
}
