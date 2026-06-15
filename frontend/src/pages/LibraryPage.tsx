import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { apiClient } from '../api/client';
import type { Book, BookPreferenceStatus } from '../api/types';
import Card from '../components/Card';
import Button from '../components/Button';
import './LibraryPage.css';

type LibraryTab = 'explore' | 'shelves';

const READING_GOAL = 50;

// Recommendation-style actions, shown on every library card.
const ACTIONS: { status: BookPreferenceStatus; label: string; variant: 'secondary' | 'ghost' }[] = [
  { status: 'interested', label: 'Save as Interested', variant: 'secondary' },
  { status: 'read_liked', label: 'Mark as Read (Liked)', variant: 'secondary' },
  { status: 'read_disliked', label: 'Mark as Read (Disliked)', variant: 'ghost' },
  { status: 'not_interested', label: 'Not for me', variant: 'ghost' },
];

const SHELF_SECTIONS: { status: BookPreferenceStatus; label: string }[] = [
  { status: 'currently_reading', label: 'Currently reading' },
  { status: 'interested', label: 'Want to read' },
  { status: 'read_liked', label: 'Read · liked' },
  { status: 'read_disliked', label: 'Read · disliked' },
];

const READ_STATUSES: BookPreferenceStatus[] = ['read_liked', 'read_disliked'];

interface ShelfItem {
  book_id: string;
  title?: string;
  author_name?: string;
}

function truncate(text: string | undefined, max = 180): string {
  if (!text) return '';
  const clean = text.trim();
  return clean.length > max ? clean.slice(0, max).trimEnd() + '…' : clean;
}

export default function LibraryPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<LibraryTab>('explore');

  // Explore
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);

  // Shelf membership: book_id -> current status
  const [shelfMap, setShelfMap] = useState<Record<string, BookPreferenceStatus>>({});
  const [shelfItems, setShelfItems] = useState<Record<string, ShelfItem>>({});

  // Reading goal progress
  const [booksRead, setBooksRead] = useState(0);

  useEffect(() => {
    loadShelves();
    loadBooksRead();
  }, []);

  // Debounced catalog search
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
      const statuses: BookPreferenceStatus[] = [
        'interested',
        'currently_reading',
        'read_liked',
        'read_disliked',
      ];
      // not_for_me is tracked for active state but isn't its own shelf
      const allStatuses = [...statuses, 'not_for_me'];
      const lists = await Promise.all(allStatuses.map((s) => apiClient.getBookStatusList(s)));
      const map: Record<string, BookPreferenceStatus> = {};
      const items: Record<string, ShelfItem> = {};
      allStatuses.forEach((status, i) => {
        // Backend stores "not_for_me"; normalize to the frontend's "not_interested"
        const normalized = (status === 'not_for_me' ? 'not_interested' : status) as BookPreferenceStatus;
        for (const it of lists[i]) {
          map[it.book_id] = normalized;
          items[it.book_id] = { book_id: it.book_id, title: it.title, author_name: it.author_name };
        }
      });
      setShelfMap(map);
      setShelfItems(items);
    } catch {
      // non-fatal
    }
  };

  const setShelf = async (book: Book, status: BookPreferenceStatus) => {
    const prev = shelfMap[book.id];
    // Optimistic update
    setShelfMap((m) => ({ ...m, [book.id]: status }));
    setShelfItems((m) => ({
      ...m,
      [book.id]: { book_id: book.id, title: book.title, author_name: book.author_name },
    }));
    // Optimistically bump the reading goal when a book becomes "read" for the first time.
    const wasRead = prev ? READ_STATUSES.includes(prev) : false;
    const nowRead = READ_STATUSES.includes(status);
    if (nowRead && !wasRead) {
      setBooksRead((n) => n + 1);
    }

    try {
      await apiClient.setBookStatus({ book_id: book.id, status, source: 'library' });
      // Graded/interest signals also feed the recommendation engine.
      if (status !== 'currently_reading') {
        try {
          await apiClient.updateUserBook(book.id, status);
        } catch {
          /* dashboard write already succeeded */
        }
      }
    } catch {
      // Revert on failure
      setShelfMap((m) => {
        const next = { ...m };
        if (prev) next[book.id] = prev;
        else delete next[book.id];
        return next;
      });
      if (nowRead && !wasRead) {
        setBooksRead((n) => Math.max(0, n - 1));
      }
    }
  };

  const removeFromShelf = async (bookId: string) => {
    const prev = shelfMap[bookId];
    const prevItem = shelfItems[bookId];
    setShelfMap((m) => {
      const next = { ...m };
      delete next[bookId];
      return next;
    });
    setShelfItems((m) => {
      const next = { ...m };
      delete next[bookId];
      return next;
    });
    try {
      await apiClient.deleteBookStatus(bookId);
    } catch {
      if (prev) setShelfMap((m) => ({ ...m, [bookId]: prev }));
      if (prevItem) setShelfItems((m) => ({ ...m, [bookId]: prevItem }));
    }
  };


  const goalPct = Math.min(100, Math.round((booksRead / READING_GOAL) * 100));
  const remaining = Math.max(0, READING_GOAL - booksRead);

  return (
    <div className="readar-library-page">
      <div className="container">
        <h1 className="readar-library-title">Library</h1>

        {/* Gamified reading goal */}
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

        <div className="readar-library-tabs">
          <button
            className={`readar-library-tab${tab === 'explore' ? ' readar-library-tab--active' : ''}`}
            onClick={() => setTab('explore')}
          >
            Explore
          </button>
          <button
            className={`readar-library-tab${tab === 'shelves' ? ' readar-library-tab--active' : ''}`}
            onClick={() => setTab('shelves')}
          >
            My shelves
          </button>
        </div>

        {tab === 'explore' ? (
          <>
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
              <p className="readar-library-muted">Searching…</p>
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
                        {book.description && (
                          <p className="readar-lib-desc">{truncate(book.description)}</p>
                        )}
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
          </>
        ) : (
          <div className="readar-library-shelves">
            {SHELF_SECTIONS.map((section) => {
              const items = Object.values(shelfItems).filter(
                (it) => shelfMap[it.book_id] === section.status,
              );
              return (
                <Card key={section.status} variant="flat" className="readar-shelf-section">
                  <h2 className="readar-shelf-heading">
                    {section.label}
                    <span className="readar-shelf-count">{items.length}</span>
                  </h2>
                  {items.length === 0 ? (
                    <p className="readar-library-muted">Nothing here yet.</p>
                  ) : (
                    <ul className="readar-shelf-list">
                      {items.map((it) => (
                        <li key={it.book_id} className="readar-shelf-item">
                          <span
                            className="readar-shelf-item-link"
                            onClick={() => navigate(`/book/${it.book_id}`)}
                            role="button"
                            tabIndex={0}
                            onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/book/${it.book_id}`); }}
                          >
                            {it.title ? (
                              <>
                                <strong>{it.title}</strong>
                                {it.author_name && <span className="readar-library-muted"> by {it.author_name}</span>}
                              </>
                            ) : (
                              <span className="readar-library-muted">{it.book_id}</span>
                            )}
                          </span>
                          <button
                            className="readar-shelf-remove"
                            onClick={() => removeFromShelf(it.book_id)}
                            aria-label="Remove from shelf"
                          >
                            Remove
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
