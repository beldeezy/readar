import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import type { RecommendationItem, BookPreferenceStatus } from '../api/types';
import { logRecommendationClick, apiClient } from '../api/client';
import { submitFeedback } from '../services/feedbackApi';
import Card from './Card';
import Badge from './Badge';
import Button from './Button';
import ChooseBookButton from './ChooseBookButton';
import './BookCard.css';

interface RecommendationCardProps {
  book: RecommendationItem;
  onAction: (bookId: string, status: BookPreferenceStatus) => void;
  isTopMatch?: boolean;
  requestId?: string;
  position?: number;
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
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [actionError, setActionError] = useState('');

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

  const handleStatusClick = async (status: BookPreferenceStatus) => {
    // Prevent spam clicks
    if (savingStatus) return;
    
    setSavingStatus(status);
    setActionError('');
    
    // Map status to feedback action
    const actionMap: Record<BookPreferenceStatus, string> = {
      'interested': 'save_interested',
      'currently_reading': 'currently_reading',
      'read_liked': 'read_liked',
      'read_disliked': 'read_disliked',
      'not_interested': 'not_for_me',
    };
    const feedbackAction = actionMap[status];
    
    try {
      // Shelf persistence is required before confirmation or advancing the deck.
      await apiClient.setBookStatus({
          book_id: book.book_id,
          status: status,
          request_id: requestId || undefined,
          position: position,
          source: 'recommendations',
      });
      void submitFeedback(book.book_id, feedbackAction, requestId).catch((err) => {
        console.warn('Optional recommendation feedback failed:', err);
      });
      
      // Also call the existing onAction callback for backward compatibility
      if (onAction) {
        onAction(book.book_id, status);
      }
      
      // Show confirmation message
      setShowConfirmation(true);
      setTimeout(() => {
        setShowConfirmation(false);
      }, 2000);
      
      // Keep button disabled after success
      // Don't reset savingStatus to keep button disabled
    } catch (err: any) {
      console.warn('Failed to submit feedback:', err);
      // Re-enable buttons on error
      setSavingStatus(null);
      setActionError("We couldn't save that change. Please try again.");
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Card variant="default" className="readar-book-card rd-signal-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div>
          <div className="readar-book-header">
            {isTopMatch && (
              <Badge variant="signal" size="sm">
                First suggestion
              </Badge>
            )}
          </div>
          {(book.cover_image_url || book.thumbnail_url) && (
            <div className="readar-book-cover-wrap">
              <img
                src={book.cover_image_url || book.thumbnail_url}
                alt={book.title}
                className="readar-book-cover"
                loading="lazy"
                referrerPolicy="no-referrer"
                onClick={handleClick}
              />
            </div>
          )}
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

            <section className="readar-book-fit" aria-label="Why this book">
              {book.fit ? (
                <>
                  {book.fit.priority && (
                    <div className="readar-book-fit__priority">
                      <h4>{book.fit.priority_label}</h4>
                      <p>“{book.fit.priority}”</p>
                    </div>
                  )}
                  <div>
                    <h4>Why this book</h4>
                    <p>{book.fit.reason}</p>
                    {book.fit.evidence && (
                      <p className="readar-book-fit__evidence">
                        <span>From the book details: </span>“{book.fit.evidence}”
                      </p>
                    )}
                  </div>
                  <div>
                    <h4>As you read</h4>
                    <p>{book.fit.reading_focus}</p>
                  </div>
                </>
              ) : (
                <div>
                  <h4>Why this book</h4>
                  <p>A personal explanation isn't available for this suggestion yet. Check the book details to see whether it speaks to your priority.</p>
                </div>
              )}
            </section>
          </div>

          <div className="readar-book-actions">
            <ChooseBookButton
              key={book.book_id}
              bookId={book.book_id}
              title={book.title}
              author={book.author_name}
              purchaseUrl={book.purchase_url}
              requestId={requestId}
              position={position}
              disabled={savingStatus !== null}
              onBusyChange={(busy) => setSavingStatus(busy ? 'reading_next' : null)}
            />
            {actionError && <p role="alert" className="readar-action-error">{actionError}</p>}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleStatusClick('interested')}
              disabled={savingStatus === 'interested' || savingStatus !== null}
              className="readar-book-action"
            >
              {savingStatus === 'interested' ? 'Saved' : 'Save as Interested'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleStatusClick('read_liked')}
              disabled={savingStatus === 'read_liked' || savingStatus !== null}
              className="readar-book-action"
            >
              {savingStatus === 'read_liked' ? 'Saved' : 'Mark as Read (Liked)'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleStatusClick('read_disliked')}
              disabled={savingStatus === 'read_disliked' || savingStatus !== null}
              className="readar-book-action"
            >
              {savingStatus === 'read_disliked' ? 'Saved' : 'Mark as Read (Disliked)'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleStatusClick('not_interested')}
              disabled={savingStatus === 'not_interested' || savingStatus !== null}
              className="readar-book-action readar-book-action--muted"
            >
              {savingStatus === 'not_interested' ? 'Noted' : 'Not for me'}
            </Button>
            {showConfirmation && (
              <p style={{
                fontSize: '0.75rem',
                color: 'var(--rd-muted)',
                marginTop: '0.5rem',
                marginBottom: 0,
                opacity: showConfirmation ? 1 : 0,
                transition: 'opacity 0.3s ease-out',
              }}>
                Got it — this helps refine future recommendations.
              </p>
            )}
          </div>
        </div>

      </Card>
    </div>
  );
}
