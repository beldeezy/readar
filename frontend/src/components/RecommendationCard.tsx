import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import type { RecommendationItem, BookPreferenceStatus } from '../api/types';
import { logRecommendationClick, apiClient } from '../api/client';
import Card from './Card';
import Badge from './Badge';
import Button from './Button';
import GetBookCTA from './GetBookCTA';
import './BookCard.css';

interface RecommendationCardProps {
  book: RecommendationItem;
  onAction: (bookId: string, status: BookPreferenceStatus) => void;
  isTopMatch?: boolean;
  requestId?: string;
  position?: number;
}

/**
 * Build an Amazon search URL from book title and author.
 * Uses encodeURIComponent (same style as backend's quote_plus).
 */
function buildAmazonSearchUrl(title: string, author?: string): string {
  const searchQuery = author ? `${title} ${author}`.trim() : title.trim();
  const encodedQuery = encodeURIComponent(searchQuery);
  return `https://www.amazon.com/s?k=${encodedQuery}`;
}

export default function RecommendationCard({ 
  book, 
  onAction, 
  isTopMatch = false,
  requestId,
  position = 0,
}: RecommendationCardProps) {
  const navigate = useNavigate();
  const [savingStatus, setSavingStatus] = useState<string | null>(null);

  const handleClick = (e: React.MouseEvent) => {
    // Log click event (best-effort, non-blocking)
    if (requestId) {
      logRecommendationClick({
        book_id: book.book_id,
        request_id: requestId,
        position: position,
      });
    }
    // Navigate as normal
    navigate(`/book/${book.book_id}`);
  };

  const handleCtaClick = (e: React.MouseEvent) => {
    // Log click event (best-effort, non-blocking)
    if (requestId) {
      logRecommendationClick({
        book_id: book.book_id,
        request_id: requestId,
        position: position,
      });
    }
    // Let the link navigate normally
  };

  const handleStatusClick = async (status: BookPreferenceStatus) => {
    // Prevent spam clicks
    if (savingStatus) return;
    
    setSavingStatus(status);
    
    try {
      // Call the new setBookStatus API
      await apiClient.setBookStatus({
        book_id: book.book_id,
        status: status,
        request_id: requestId || undefined,
        position: position,
        source: 'recommendations',
      });
      
      // Also call the existing onAction callback for backward compatibility
      if (onAction) {
        onAction(book.book_id, status);
      }
      
      // Show brief "saved" state
      setTimeout(() => {
        setSavingStatus(null);
      }, 1000);
    } catch (err: any) {
      console.warn('Failed to save book status:', err);
      // Re-enable buttons on error
      setSavingStatus(null);
      // Show non-blocking error (optional - could add toast here)
    }
  };

  // Build metadata line (year • pages • rating)
  const metaParts: string[] = [];
  if (book.published_year) {
    metaParts.push(String(book.published_year));
  }
  if (book.page_count) {
    metaParts.push(`${book.page_count} pages`);
  }
  if (book.average_rating && book.ratings_count) {
    metaParts.push(
      `${book.average_rating.toFixed(1)} ★ (${book.ratings_count.toLocaleString()} ratings)`
    );
  }
  const meta = metaParts.join(" • ");

  // Build CTA URL
  const ctaUrl = book.purchase_url || buildAmazonSearchUrl(book.title, book.author_name);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Card variant="default" className="readar-book-card" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div>
          <div className="readar-book-header">
            {isTopMatch && (
              <Badge variant="primary" size="sm">
                Great Match
              </Badge>
            )}
          </div>
          <div className="readar-book-content">
            <h3 onClick={handleClick} className="readar-book-title" style={{ cursor: 'pointer' }}>
              {book.title}
            </h3>
            {book.subtitle && <p className="readar-book-subtitle">{book.subtitle}</p>}
            {book.author_name && <p className="readar-book-author">by {book.author_name}</p>}

            {/* Metadata line */}
            {meta && (
              <p className="mt-1 text-sm text-muted-foreground" style={{
                color: 'var(--rd-muted)',
                fontSize: 'var(--rd-font-size-sm)',
                marginTop: '0.5rem',
              }}>
                {meta}
              </p>
            )}

            {/* Why this book section */}
            {book.why_this_book && (
              <div className="mt-3 text-sm" style={{ marginTop: '1rem' }}>
                <p className="font-medium mb-1" style={{ fontWeight: 600, marginBottom: '0.25rem', fontSize: '0.875rem' }}>
                  Why this book:
                </p>
                <p className="text-muted-foreground" style={{ 
                  color: 'var(--rd-muted)', 
                  fontSize: '0.875rem',
                  lineHeight: '1.5',
                  margin: 0
                }}>
                  {book.why_this_book}
                </p>
              </div>
            )}
          </div>

          <div className="readar-book-actions">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleStatusClick('interested')}
              disabled={savingStatus !== null}
              className="readar-book-action"
            >
              {savingStatus === 'interested' ? 'Saved' : 'Save as Interested'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleStatusClick('read_liked')}
              disabled={savingStatus !== null}
              className="readar-book-action"
            >
              {savingStatus === 'read_liked' ? 'Saved' : 'Mark as Read (Liked)'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleStatusClick('read_disliked')}
              disabled={savingStatus !== null}
              className="readar-book-action"
            >
              {savingStatus === 'read_disliked' ? 'Saved' : 'Mark as Read (Disliked)'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleStatusClick('not_interested')}
              disabled={savingStatus !== null}
              className="readar-book-action readar-book-action--muted"
            >
              {savingStatus === 'not_interested' ? 'Noted' : 'Not for me'}
            </Button>
          </div>
        </div>

        <div style={{ marginTop: 'auto', paddingTop: '0.75rem' }}>
          <GetBookCTA href={ctaUrl} onBeforeClick={handleCtaClick} />
        </div>
      </Card>
    </div>
  );
}


