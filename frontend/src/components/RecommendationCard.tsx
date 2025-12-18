import { useNavigate } from 'react-router-dom';
import type { RecommendationItem, BookPreferenceStatus } from '../api/types';
import Card from './Card';
import Badge from './Badge';
import Button from './Button';
import GetBookCTA from './GetBookCTA';
import './BookCard.css';

interface RecommendationCardProps {
  book: RecommendationItem;
  onAction: (bookId: string, status: BookPreferenceStatus) => void;
  isTopMatch?: boolean;
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

export default function RecommendationCard({ book, onAction, isTopMatch = false }: RecommendationCardProps) {
  const navigate = useNavigate();

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
            <h3 onClick={() => navigate(`/book/${book.book_id}`)} className="readar-book-title">
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
                  margin: 0,
                  whiteSpace: isTopMatch ? 'pre-line' : 'normal'
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
              onClick={() => onAction(book.book_id, 'interested')}
              className="readar-book-action"
            >
              Save as Interested
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onAction(book.book_id, 'read_liked')}
              className="readar-book-action"
            >
              Mark as Read (Liked)
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onAction(book.book_id, 'read_disliked')}
              className="readar-book-action"
            >
              Mark as Read (Disliked)
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onAction(book.book_id, 'not_interested')}
              className="readar-book-action readar-book-action--muted"
            >
              Not for me
            </Button>
          </div>
        </div>

        <div style={{ marginTop: 'auto', paddingTop: '0.75rem' }}>
          <GetBookCTA href={ctaUrl} />
        </div>
      </Card>
    </div>
  );
}


