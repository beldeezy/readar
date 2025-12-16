import { useEffect, useState, useCallback, useMemo } from 'react';
import { apiClient } from '../../api/client';
import type { Book } from '../../api/types';
import Button from '../../components/Button';
import './Books.css';

type InsightStatus = 'complete' | 'incomplete';

interface BookWithStatus extends Book {
  insightStatus: InsightStatus;
  missingInsights: string[];
}

type SortField = 'title' | 'author_name' | 'published_year' | 'page_count';
type SortOrder = 'asc' | 'desc';
type CoverFilter = 'all' | 'has_cover' | 'no_cover';

export default function Books() {
  const [books, setBooks] = useState<BookWithStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Query params state
  const [q, setQ] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const [sort, setSort] = useState<SortField>('title');
  const [order, setOrder] = useState<SortOrder>('asc');
  const [yearMin, setYearMin] = useState<string>('');
  const [yearMax, setYearMax] = useState<string>('');
  const [hasCover, setHasCover] = useState<CoverFilter>('all');
  const [limit, setLimit] = useState(100);
  const [offset, setOffset] = useState(0);
  
  // Diagnostics (dev-only)
  const [lastRequestUrl, setLastRequestUrl] = useState<string>('');
  const [lastResponseCount, setLastResponseCount] = useState<number>(0);
  const [lastErrorTimestamp, setLastErrorTimestamp] = useState<number | null>(null);
  const [showDiagnostics, setShowDiagnostics] = useState(false);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQ(q);
      setOffset(0); // Reset offset when search changes
    }, 300);
    return () => clearTimeout(timer);
  }, [q]);

  // Check if a book has all insight fields populated
  const checkInsightCompleteness = (book: Book): { status: InsightStatus; missing: string[] } => {
    const insightFields = [
      { key: 'promise', value: book.promise },
      { key: 'best_for', value: book.best_for },
      { key: 'core_frameworks', value: book.core_frameworks },
      { key: 'anti_patterns', value: book.anti_patterns },
      { key: 'outcomes', value: book.outcomes },
    ];

    const missing = insightFields
      .filter((field) => {
        if (!field.value) return true;
        if (Array.isArray(field.value)) {
          return field.value.length === 0;
        }
        if (typeof field.value === 'string') {
          return field.value.trim().length === 0;
        }
        return false;
      })
      .map((field) => field.key.replace('_', ' '));

    return {
      status: missing.length === 0 ? 'complete' : 'incomplete',
      missing,
    };
  };

  // Fetch books
  const fetchBooks = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const params: any = {
        limit,
        offset,
        sort,
        order,
      };

      if (debouncedQ.trim()) {
        params.q = debouncedQ.trim();
      }

      if (yearMin) {
        const year = parseInt(yearMin, 10);
        if (!isNaN(year)) {
          params.year_min = year;
        }
      }

      if (yearMax) {
        const year = parseInt(yearMax, 10);
        if (!isNaN(year)) {
          params.year_max = year;
        }
      }

      if (hasCover === 'has_cover') {
        params.has_cover = true;
      } else if (hasCover === 'no_cover') {
        params.has_cover = false;
      }

      // Build request URL for diagnostics
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          searchParams.append(key, String(value));
        }
      });
      const requestUrl = `/api/books?${searchParams.toString()}`;
      setLastRequestUrl(requestUrl);

      const fetchedBooks = await apiClient.getBooks(params);
      
      // Add insight status to each book
      const booksWithStatus: BookWithStatus[] = fetchedBooks.map((book) => {
        const { status, missing } = checkInsightCompleteness(book);
        return {
          ...book,
          insightStatus: status,
          missingInsights: missing,
        };
      });

      setBooks(booksWithStatus);
      setLastResponseCount(booksWithStatus.length);
      setLastErrorTimestamp(null);
    } catch (err: any) {
      console.error('Failed to fetch books', err);
      const errorMessage = err?.response?.data?.detail || err?.message || 'Failed to fetch books';
      setError(errorMessage);
      setLastErrorTimestamp(Date.now());
      setBooks([]);
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, sort, order, yearMin, yearMax, hasCover, limit, offset]);

  // Fetch when params change
  useEffect(() => {
    fetchBooks();
  }, [fetchBooks]);

  // Reset filters
  const handleReset = () => {
    setQ('');
    setDebouncedQ('');
    setSort('title');
    setOrder('asc');
    setYearMin('');
    setYearMax('');
    setHasCover('all');
    setOffset(0);
  };

  // Pagination handlers
  const handlePrev = () => {
    if (offset >= limit) {
      setOffset(offset - limit);
    }
  };

  const handleNext = () => {
    if (books.length === limit) {
      setOffset(offset + limit);
    }
  };

  const getInsightStatusBadge = (book: BookWithStatus) => {
    if (book.insightStatus === 'complete') {
      return (
        <span className="readar-insight-badge readar-insight-badge--complete">
          ✅ Complete
        </span>
      );
    }

    const missingCount = book.missingInsights.length;
    let badgeClass = 'readar-insight-badge--incomplete';
    if (missingCount >= 4) {
      badgeClass = 'readar-insight-badge--critical';
    } else if (missingCount >= 2) {
      badgeClass = 'readar-insight-badge--warning';
    }

    return (
      <span className={`readar-insight-badge ${badgeClass}`}>
        ⚠️ Incomplete ({missingCount} missing)
      </span>
    );
  };

  const getDifficultyBadge = (difficulty?: string) => {
    if (!difficulty) return <span className="readar-difficulty-badge">—</span>;
    
    const difficultyMap: Record<string, { label: string; class: string }> = {
      light: { label: 'Light', class: 'readar-difficulty-badge--light' },
      medium: { label: 'Medium', class: 'readar-difficulty-badge--medium' },
      deep: { label: 'Deep', class: 'readar-difficulty-badge--deep' },
    };

    const config = difficultyMap[difficulty] || { label: difficulty, class: '' };
    return (
      <span className={`readar-difficulty-badge ${config.class}`}>
        {config.label}
      </span>
    );
  };

  const currentPage = Math.floor(offset / limit) + 1;
  const hasMore = books.length === limit;
  const canGoPrev = offset > 0;

  // Loading skeleton
  if (loading && books.length === 0) {
    return (
      <div className="readar-books-page">
        <div className="readar-books-header">
          <h1 className="readar-admin-page-title">📚 Book Management</h1>
          <p className="readar-admin-page-subtitle">
            Manage books and track insight completeness
          </p>
        </div>
        <div className="readar-books-loading-skeleton">
          <div className="readar-skeleton-row"></div>
          <div className="readar-skeleton-row"></div>
          <div className="readar-skeleton-row"></div>
          <div className="readar-skeleton-row"></div>
          <div className="readar-skeleton-row"></div>
        </div>
      </div>
    );
  }

  // Error state
  if (error && books.length === 0) {
    return (
      <div className="readar-books-page">
        <div className="readar-books-header">
          <h1 className="readar-admin-page-title">📚 Book Management</h1>
          <p className="readar-admin-page-subtitle">
            Manage books and track insight completeness
          </p>
        </div>
        <div className="readar-books-error-panel">
          <h3>Couldn't load books.</h3>
          <p>{error}</p>
          <Button onClick={fetchBooks} variant="primary">
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="readar-books-page">
      <div className="readar-books-header">
        <h1 className="readar-admin-page-title">📚 Book Management</h1>
        <p className="readar-admin-page-subtitle">
          Manage books and track insight completeness
        </p>
      </div>

      {/* Controls Row */}
      <div className="readar-books-controls-panel">
        <div className="readar-books-controls-row">
          {/* Search */}
          <div className="readar-books-control-group">
            <label htmlFor="search-input" className="readar-books-control-label">
              Search
            </label>
            <input
              id="search-input"
              type="text"
              className="readar-books-input"
              placeholder="Title or author..."
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>

          {/* Sort */}
          <div className="readar-books-control-group">
            <label htmlFor="sort-select" className="readar-books-control-label">
              Sort by
            </label>
            <select
              id="sort-select"
              className="readar-books-select"
              value={sort}
              onChange={(e) => setSort(e.target.value as SortField)}
            >
              <option value="title">Title</option>
              <option value="author_name">Author</option>
              <option value="published_year">Year</option>
              <option value="page_count">Page Count</option>
            </select>
          </div>

          {/* Order */}
          <div className="readar-books-control-group">
            <label htmlFor="order-select" className="readar-books-control-label">
              Order
            </label>
            <select
              id="order-select"
              className="readar-books-select"
              value={order}
              onChange={(e) => setOrder(e.target.value as SortOrder)}
            >
              <option value="asc">Asc</option>
              <option value="desc">Desc</option>
            </select>
          </div>

          {/* Year Min */}
          <div className="readar-books-control-group">
            <label htmlFor="year-min-input" className="readar-books-control-label">
              Year Min
            </label>
            <input
              id="year-min-input"
              type="number"
              className="readar-books-input readar-books-input--small"
              placeholder="1900"
              value={yearMin}
              onChange={(e) => setYearMin(e.target.value)}
            />
          </div>

          {/* Year Max */}
          <div className="readar-books-control-group">
            <label htmlFor="year-max-input" className="readar-books-control-label">
              Year Max
            </label>
            <input
              id="year-max-input"
              type="number"
              className="readar-books-input readar-books-input--small"
              placeholder="2024"
              value={yearMax}
              onChange={(e) => setYearMax(e.target.value)}
            />
          </div>

          {/* Cover Filter */}
          <div className="readar-books-control-group">
            <label htmlFor="cover-select" className="readar-books-control-label">
              Cover
            </label>
            <select
              id="cover-select"
              className="readar-books-select"
              value={hasCover}
              onChange={(e) => setHasCover(e.target.value as CoverFilter)}
            >
              <option value="all">All</option>
              <option value="has_cover">Has cover</option>
              <option value="no_cover">No cover</option>
            </select>
          </div>

          {/* Reset Button */}
          <div className="readar-books-control-group">
            <Button onClick={handleReset} variant="secondary" size="sm">
              Reset
            </Button>
          </div>
        </div>

        {/* Result Count */}
        <div className="readar-books-result-count">
          Showing {books.length} {books.length === 1 ? 'book' : 'books'}
          {error && books.length > 0 && ' (error occurred)'}
        </div>
      </div>

      {/* Error Banner (if error but we have some books) */}
      {error && books.length > 0 && (
        <div className="readar-books-error-banner">
          <span>⚠️ {error}</span>
          <Button onClick={fetchBooks} variant="ghost" size="sm">
            Retry
          </Button>
        </div>
      )}

      {/* Empty State */}
      {!loading && books.length === 0 && !error && (
        <div className="readar-books-empty">
          <h3>No books found</h3>
          <p>Try clearing filters or searching something else</p>
          <Button onClick={handleReset} variant="primary">
            Reset filters
          </Button>
        </div>
      )}

      {/* Books Table */}
      {books.length > 0 && (
        <>
          <div className="readar-books-table-container">
            <table className="readar-books-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Author</th>
                  <th>Year</th>
                  <th>Difficulty</th>
                  <th>Insight Status</th>
                  <th>Missing Fields</th>
                </tr>
              </thead>
              <tbody>
                {books.map((book) => (
                  <tr
                    key={book.id}
                    className={
                      book.insightStatus === 'incomplete'
                        ? 'readar-books-row--incomplete'
                        : ''
                    }
                  >
                    <td className="readar-books-title-cell">{book.title}</td>
                    <td>{book.author_name}</td>
                    <td>{book.published_year || '—'}</td>
                    <td>{getDifficultyBadge(book.difficulty)}</td>
                    <td>{getInsightStatusBadge(book)}</td>
                    <td className="readar-books-missing-cell">
                      {book.missingInsights.length > 0
                        ? book.missingInsights.join(', ')
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="readar-books-pagination">
            <Button
              onClick={handlePrev}
              variant="secondary"
              size="sm"
              disabled={!canGoPrev}
            >
              Prev
            </Button>
            <span className="readar-books-pagination-info">
              Page {currentPage} (Offset {offset})
            </span>
            <Button
              onClick={handleNext}
              variant="secondary"
              size="sm"
              disabled={!hasMore}
            >
              Next
            </Button>
          </div>
        </>
      )}

      {/* Dev Diagnostics Panel */}
      {import.meta.env.DEV && (
        <div className="readar-books-diagnostics">
          <button
            className="readar-books-diagnostics-toggle"
            onClick={() => setShowDiagnostics(!showDiagnostics)}
          >
            {showDiagnostics ? '▼' : '▶'} Diagnostics (Dev Only)
          </button>
          {showDiagnostics && (
            <div className="readar-books-diagnostics-content">
              <div className="readar-books-diagnostics-item">
                <strong>Last Request URL:</strong>
                <code>{lastRequestUrl || '—'}</code>
              </div>
              <div className="readar-books-diagnostics-item">
                <strong>Last Response Count:</strong>
                <span>{lastResponseCount}</span>
              </div>
              {lastErrorTimestamp && (
                <div className="readar-books-diagnostics-item">
                  <strong>Last Error:</strong>
                  <span>{new Date(lastErrorTimestamp).toLocaleString()}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
