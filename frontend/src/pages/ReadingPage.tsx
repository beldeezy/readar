import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { apiClient } from '../api/client';
import type { Book } from '../api/types';
import EmptyState from '../components/EmptyState';
import { BookSignalArt } from '../components/illustrations';
import './ReadingPage.css';

interface CurrentItem {
  book_id: string;
  title?: string;
  author_name?: string;
}

/**
 * /reading — the user's "currently reading" hub. Quick-add by search plus
 * the list of books in progress. Built to grow (progress, notes, etc.).
 */
export default function ReadingPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Book[]>([]);
  const [current, setCurrent] = useState<CurrentItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadCurrent(); }, []);

  useEffect(() => {
    const t = setTimeout(() => runSearch(query), 250);
    return () => clearTimeout(t);
  }, [query]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadCurrent = async () => {
    try {
      setCurrent(await apiClient.getBookStatusList('currently_reading'));
    } catch {
      /* non-fatal */
    } finally {
      setLoading(false);
    }
  };

  const runSearch = async (q: string) => {
    if (q.trim().length < 2) { setResults([]); return; }
    try {
      const books = await apiClient.getBooks({ q: q.trim(), curated: true, limit: 8 });
      const currentIds = new Set(current.map((c) => c.book_id));
      setResults(books.filter((b) => !currentIds.has(b.id)));
    } catch {
      setResults([]);
    }
  };

  const addReading = async (book: Book) => {
    // Optimistic
    setCurrent((c) => [{ book_id: book.id, title: book.title, author_name: book.author_name }, ...c]);
    setQuery('');
    setResults([]);
    try {
      await apiClient.setBookStatus({ book_id: book.id, status: 'currently_reading', source: 'reading_page' });
    } catch {
      setCurrent((c) => c.filter((x) => x.book_id !== book.id));
    }
  };

  const removeReading = async (bookId: string) => {
    const prev = current;
    setCurrent((c) => c.filter((x) => x.book_id !== bookId));
    try {
      await apiClient.deleteBookStatus(bookId);
    } catch {
      setCurrent(prev);
    }
  };

  return (
    <div className="reading-page rd-scan-bg">
      <div className="container">
        <h1 className="reading-title">Reading</h1>
        <p className="reading-sub rd-tech">What you're reading now</p>

        {/* Quick add */}
        <div className="reading-add">
          <div className="reading-search">
            <Search size={18} strokeWidth={2} className="reading-search-icon" />
            <input
              className="reading-search-input"
              placeholder="Search a book you're reading…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          {results.length > 0 && (
            <ul className="reading-results">
              {results.map((b) => (
                <li key={b.id} className="reading-result" onClick={() => addReading(b)}>
                  <span className="reading-result-add">+</span>
                  <span>
                    <strong>{b.title}</strong>
                    {b.author_name && <span className="reading-muted"> by {b.author_name}</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Current list */}
        {loading ? (
          <p className="reading-muted">Loading…</p>
        ) : current.length === 0 ? (
          <EmptyState
            art={<BookSignalArt />}
            title="Nothing on your nightstand"
            message="Search above to add a book you're currently reading and track it here."
          />
        ) : (
          <ul className="reading-list">
            {current.map((it) => (
              <li key={it.book_id} className="reading-item">
                <span
                  className="reading-item-link"
                  onClick={() => navigate(`/book/${it.book_id}`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/book/${it.book_id}`); }}
                >
                  {it.title
                    ? <><strong>{it.title}</strong>{it.author_name && <span className="reading-muted"> by {it.author_name}</span>}</>
                    : <span className="reading-muted">{it.book_id}</span>}
                </span>
                <button className="reading-remove" onClick={() => removeReading(it.book_id)} aria-label="Remove">
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
