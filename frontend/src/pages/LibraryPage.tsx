import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, BookOpen } from 'lucide-react';
import { apiClient } from '../api/client';
import type { Book, BookPreferenceStatus } from '../api/types';
import Card from '../components/Card';
import './LibraryPage.css';

type LibraryTab = 'explore' | 'shelves';

// Shelf options offered in the library. "currently_reading" is a transient state;
// the read_* / interested options also feed the recommendation engine.
const SHELF_OPTIONS: { value: BookPreferenceStatus; label: string }[] = [
  { value: 'interested', label: 'Want to read' },
  { value: 'currently_reading', label: 'Currently reading' },
  { value: 'read_liked', label: 'Read · liked' },
  { value: 'read_disliked', label: 'Read · disliked' },
];

const SHELF_SECTIONS: { status: BookPreferenceStatus; label: string }[] = [
  { status: 'currently_reading', label: 'Currently reading' },
  { status: 'interested', label: 'Want to read' },
  { status: 'read_liked', label: 'Read · liked' },
  { status: 'read_disliked', label: 'Read · disliked' },
];

interface ShelfItem {
  book_id: string;
  title?: string;
  author_name?: string;
}

export default function LibraryPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<LibraryTab>('explore');

  // Explore
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Book[]>([]);
  const [loading, setLoading] = useState(false);

  // Shelf membership: book_id -> current status (drives both Explore controls and Shelves view)
  const [shelfMap, setShelfMap] = useState<Record<string, BookPreferenceStatus>>({});
  const [shelfItems, setShelfItems] = useState<Record<string, ShelfItem>>({});

  useEffect(() => {
    loadShelves();
  }, []);

  // Debounced catalog search
  useEffect(() => {
    const t = setTimeout(() => {
      loadBooks(query);
    }, 250);
    return () => clearTimeout(t);
  }, [query]);

  const loadBooks = async (q: string) => {
    setLoading(true);
    try {
      const books = await apiClient.getBooks({
        q: q.trim() || undefined,
        sort: 'title',
        order: 'asc',
        has_cover: true,
        limit: 48,
      });
      setResults(books);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
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
      const lists = await Promise.all(statuses.map((s) => apiClient.getBookStatusList(s)));
      const map: Record<string, BookPreferenceStatus> = {};
      const items: Record<string, ShelfItem> = {};
      statuses.forEach((status, i) => {
        for (const it of lists[i]) {
          map[it.book_id] = status;
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
    // Optimistic local update
    setShelfMap((m) => ({ ...m, [book.id]: status }));
    setShelfItems((m) => ({
      ...m,
      [book.id]: { book_id: book.id, title: book.title, author_name: book.author_name },
    }));

    try {
      await apiClient.setBookStatus({ book_id: book.id, status, source: 'library' });
      // Graded/interest signals also feed the recommendation engine; the transient
      // "currently_reading" state does not (the backend clears any prior signal).
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
    }
  };

  const removeFromShelf = async (bookId: string) => {
    const prev = shelfMap[bookId];
    const prevItem = shelfItems[bookId];
    // Optimistic removal
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
      // Revert on failure
      if (prev) setShelfMap((m) => ({ ...m, [bookId]: prev }));
      if (prevItem) setShelfItems((m) => ({ ...m, [bookId]: prevItem }));
    }
  };

  const renderCover = (book: Book) => {
    const src = book.cover_image_url || book.thumbnail_url;
    return src ? (
      <img src={src} alt={book.title} className="readar-lib-cover" loading="lazy" />
    ) : (
      <div className="readar-lib-cover readar-lib-cover--placeholder">
        <BookOpen size={28} strokeWidth={1.5} />
      </div>
    );
  };

  return (
    <div className="readar-library-page">
      <div className="container">
        <h1 className="readar-library-title">Library</h1>

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
                {results.map((book) => (
                  <Card key={book.id} variant="flat" className="readar-lib-card">
                    <div
                      className="readar-lib-cover-wrap"
                      onClick={() => navigate(`/book/${book.id}`)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/book/${book.id}`); }}
                    >
                      {renderCover(book)}
                    </div>
                    <div className="readar-lib-info">
                      <strong className="readar-lib-book-title">{book.title}</strong>
                      <span className="readar-lib-book-author">{book.author_name}</span>
                    </div>
                    <select
                      className="readar-lib-shelf-select"
                      value={shelfMap[book.id] ?? ''}
                      onChange={(e) => {
                        const v = e.target.value;
                        if (v === '__remove__') removeFromShelf(book.id);
                        else if (v) setShelf(book, v as BookPreferenceStatus);
                      }}
                    >
                      <option value="">+ Add to shelf</option>
                      {SHELF_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                      {shelfMap[book.id] && <option value="__remove__">Remove from shelf</option>}
                    </select>
                  </Card>
                ))}
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
