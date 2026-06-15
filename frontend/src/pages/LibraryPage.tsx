import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { apiClient } from '../api/client';
import type { Book, BookPreferenceStatus } from '../api/types';
import Card from '../components/Card';
import Button from '../components/Button';
import './LibraryPage.css';

const READING_GOAL = 50;

const ACTIONS: { status: BookPreferenceStatus; label: string; variant: 'secondary' | 'ghost' }[] = [
  { status: 'interested', label: 'Save as Interested', variant: 'secondary' },
  { status: 'read_liked', label: 'Mark as Read (Liked)', variant: 'secondary' },
  { status: 'read_disliked', label: 'Mark as Read (Disliked)', variant: 'ghost' },
  { status: 'not_interested', label: 'Not for me', variant: 'ghost' },
];

const READ_STATUSES: BookPreferenceStatus[] = ['read_liked', 'read_disliked'];

function truncate(text: string | undefined, max = 200): string {
  if (!text) return '';
  const clean = text.trim();
  return clean.length > max ? clean.slice(0, max).trimEnd() + '…' : clean;
}

export default function LibraryPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);

  // Shelf state (for showing active status on each card)
  const [shelfMap, setShelfMap] = useState<Record<string, BookPreferenceStatus>>({});

  // Reading goal progress
  const [booksRead, setBooksRead] = useState(0);

  useEffect(() => {
    loadShelves();
    loadBooksRead();
  }, []);

  // Debounced search
  useEffect(() => {
    const t = setTimeout(() => loadBooks(query), 250);
    return () => clearTimeout(t);
  }, [query]);

  const loadBooks = async (q: string) => {
    setLoading(true);
    try {
      const books = await apiClient.getBooks({
        q: q.trim() || undefined,
        sort: 'title',
        order: 'asc',
        curated: true,
        limit: 48,
      });
      setResults(books);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const loadBooksRead = async () => {
    try {
      const profile = await apiClient.getReadingProfile();
      setBooksRead(profile?.total_books_read ?? 0);
    } catch {
      // 404 = no reading profile yet
    }
  };

  const loadShelves = async () => {
    try {
      const statuses: BookPreferenceStatus[] = ['interested', 'currently_reading', 'read_liked', 'read_disliked'];
      const allStatuses = [...statuses, 'not_for_me'];
      const lists = await Promise.all(allStatuses.map((s) => apiClient.getBookStatusList(s)));
      const map: Record<string, BookPreferenceStatus> = {};
      allStatuses.forEach((status, i) => {
        const normalized = (status === 'not_for_me' ? 'not_interested' : status) as BookPreferenceStatus;
        for (const it of lists[i]) {
          map[it.book_id] = normalized;
        }
      });
      setShelfMap(map);
    } catch {
      // non-fatal
    }
  };

  const setShelf = async (book: Book, status: BookPreferenceStatus) => {
    const prev = shelfMap[book.id];
    const wasRead = prev ? READ_STATUSES.includes(prev) : false;
    const nowRead = READ_STATUSES.includes(status);

    setShelfMap((m) => ({ ...m, [book.id]: status }));
    if (nowRead && !wasRead) setBooksRead((n) => n + 1);

    try {
      await apiClient.setBookStatus({ book_id: book.id, status, source: 'library' });
      if (status !== 'currently_reading') {
        try { await apiClient.updateUserBook(book.id, status); } catch { /* non-fatal */ }
      }
    } catch {
      setShelfMap((m) => {
        const next = { ...m };
        if (prev) next[book.id] = prev; else delete next[book.id];
        return next;
      });
      if (nowRead && !wasRead) setBooksRead((n) => Math.max(0, n - 1));
    }
  };

  const goalPct = Math.min(100, Math.round((booksRead / READING_GOAL) * 100));
  const remaining = Math.max(0, READING_GOAL - booksRead);

  return (
    <div className="readar-library-page">
      <div className="container">
        <h1 className="readar-library-title">Library</h1>
        <p className="readar-library-subtitle">Readar's curated catalog of books for entrepreneurs.</p>

        {/* Reading goal */}
        {booksRead < READING_GOAL && (
          <Card variant="flat" className="readar-goal-card">
            <div className="readar-goal-head">
              <span className="readar-goal-label">📚 Reading goal</span>
              <span className="readar-goal-count">{booksRead} / {READING_GOAL} read</span>
            </div>
            <div className="readar-goal-bar">
              <div className="readar-goal-fill" style={{ width: `${goalPct}%` }} />
            </div>
            <p className="readar-goal-hint">
              {remaining} more {remaining === 1 ? 'book' : 'books'} to fully tune your recommendations.
            </p>
          </Card>
        )}

        <div className="readar-library-search">
          <Search size={18} strokeWidth={2} className="readar-library-search-icon" />
          <input
            type="text"
            className="readar-library-search-input"
            placeholder="Search by title or author…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        {loading ? (
          <p className="readar-library-muted">Loading catalog…</p>
        ) : results.length === 0 ? (
          <p className="readar-library-muted">No books found. Try a different search.</p>
        ) : (
          <div className="readar-library-grid">
            {results.map((book) => {
              const active = shelfMap[book.id];
              const cover = book.cover_image_url || book.thumbnail_url;
              return (
                <Card key={book.id} variant="flat" className="readar-lib-card">
                  {cover && (
                    <div
                      className="readar-lib-cover-wrap"
                      onClick={() => navigate(`/book/${book.id}`)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/book/${book.id}`); }}
                    >
                      <img src={cover} alt={book.title} className="readar-lib-cover" loading="lazy" />
                    </div>
                  )}
                  <div className="readar-lib-info">
                    <strong
                      className="readar-lib-book-title readar-lib-title-link"
                      onClick={() => navigate(`/book/${book.id}`)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/book/${book.id}`); }}
                    >
                      {book.title}
                    </strong>
                    <span className="readar-lib-book-author">{book.author_name}</span>
                    <p className="readar-lib-desc">
                      {book.promise || book.best_for
                        ? truncate(book.promise || book.best_for)
                        : <span className="readar-lib-no-desc">No description available yet.</span>
                      }
                    </p>
                  </div>
                  <div className="readar-lib-actions">
                    {ACTIONS.map((a) => (
                      <Button
                        key={a.status}
                        variant={active === a.status ? 'primary' : a.variant}
                        size="sm"
                        delayMs={0}
                        onClick={() => setShelf(book, a.status)}
                      >
                        {active === a.status ? `✓ ${a.label}` : a.label}
                      </Button>
                    ))}
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
