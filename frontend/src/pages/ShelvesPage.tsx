import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { BookPreferenceStatus } from '../api/types';
import Card from '../components/Card';
import './ShelvesPage.css';

const SHELF_SECTIONS: { status: BookPreferenceStatus | 'not_for_me'; label: string; description: string }[] = [
  { status: 'currently_reading', label: 'Currently reading', description: 'Books you\'re actively reading.' },
  { status: 'interested', label: 'Want to read', description: 'Books saved for later.' },
  { status: 'read_liked', label: 'Read · liked', description: 'Books you\'ve read and enjoyed.' },
  { status: 'read_disliked', label: 'Read · disliked', description: 'Books you\'ve read but didn\'t enjoy.' },
];

interface ShelfItem {
  book_id: string;
  title?: string;
  author_name?: string;
}

export default function ShelvesPage() {
  const navigate = useNavigate();
  const [shelfMap, setShelfMap] = useState<Record<string, BookPreferenceStatus>>({});
  const [shelfItems, setShelfItems] = useState<Record<string, ShelfItem>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadShelves();
  }, []);

  const loadShelves = async () => {
    try {
      const statuses: (BookPreferenceStatus | 'not_for_me')[] = [
        'currently_reading', 'interested', 'read_liked', 'read_disliked',
      ];
      const lists = await Promise.all(statuses.map((s) => apiClient.getBookStatusList(s)));
      const map: Record<string, BookPreferenceStatus> = {};
      const items: Record<string, ShelfItem> = {};
      statuses.forEach((status, i) => {
        for (const it of lists[i]) {
          map[it.book_id] = status as BookPreferenceStatus;
          items[it.book_id] = { book_id: it.book_id, title: it.title, author_name: it.author_name };
        }
      });
      setShelfMap(map);
      setShelfItems(items);
    } catch {
      // non-fatal
    } finally {
      setLoading(false);
    }
  };

  const removeFromShelf = async (bookId: string) => {
    const prev = shelfMap[bookId];
    const prevItem = shelfItems[bookId];
    setShelfMap((m) => { const next = { ...m }; delete next[bookId]; return next; });
    setShelfItems((m) => { const next = { ...m }; delete next[bookId]; return next; });
    try {
      await apiClient.deleteBookStatus(bookId);
    } catch {
      if (prev) setShelfMap((m) => ({ ...m, [bookId]: prev }));
      if (prevItem) setShelfItems((m) => ({ ...m, [bookId]: prevItem }));
    }
  };

  const totalBooks = Object.keys(shelfItems).length;

  return (
    <div className="readar-shelves-page">
      <div className="container">
        <h1 className="readar-shelves-title">My Shelves</h1>
        <p className="readar-shelves-subtitle">
          {totalBooks > 0
            ? `${totalBooks} ${totalBooks === 1 ? 'book' : 'books'} across your shelves`
            : 'Save books from the Library or Recommendations to build your shelves.'}
        </p>

        {loading ? (
          <p className="readar-shelves-muted">Loading your shelves…</p>
        ) : (
          <div className="readar-shelves-sections">
            {SHELF_SECTIONS.map((section) => {
              const items = Object.values(shelfItems).filter(
                (it) => shelfMap[it.book_id] === section.status,
              );
              return (
                <Card key={section.status} variant="flat" className="readar-shelf-card">
                  <div className="readar-shelf-header">
                    <div>
                      <h2 className="readar-shelf-heading">{section.label}</h2>
                      <p className="readar-shelves-muted">{section.description}</p>
                    </div>
                    <span className="readar-shelf-count">{items.length}</span>
                  </div>

                  {items.length === 0 ? (
                    <p className="readar-shelves-empty">
                      Nothing here yet.{' '}
                      <button className="readar-shelves-link" onClick={() => navigate('/library')}>
                        Browse the Library →
                      </button>
                    </p>
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
                            {it.title
                              ? <><strong>{it.title}</strong>{it.author_name && <span className="readar-shelves-muted"> by {it.author_name}</span>}</>
                              : <span className="readar-shelves-muted">{it.book_id}</span>
                            }
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
