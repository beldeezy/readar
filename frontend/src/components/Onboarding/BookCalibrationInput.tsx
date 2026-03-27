import React, { useState } from 'react';
import { CALIBRATION_BOOKS, BOOK_STATUS_OPTIONS } from '../../config/chatOnboarding';
import './BookCalibrationInput.css';

interface BookCalibrationInputProps {
  onAnswer: (questionId: string, answer: any, displayText?: string) => void;
  questionId: string;
}

const STATUS_ICONS: Record<string, React.ReactElement> = {
  read_disliked: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/>
      <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
    </svg>
  ),
  not_interested: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="8" y1="12" x2="16" y2="12"/>
    </svg>
  ),
  interested: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
    </svg>
  ),
  read_liked: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/>
      <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
    </svg>
  ),
};

const BookCalibrationInput: React.FC<BookCalibrationInputProps> = ({ onAnswer, questionId }) => {
  const [bookStatuses, setBookStatuses] = useState<Record<string, string>>({});

  const handleBookStatus = (externalId: string, status: string) => {
    const current = bookStatuses[externalId];
    const newStatuses = {
      ...bookStatuses,
      // Clicking the active segment again deselects it (skip/no-rating)
      [externalId]: current === status ? '' : status,
    };
    // Remove the key entirely if deselected so it doesn't count
    if (newStatuses[externalId] === '') delete newStatuses[externalId];
    setBookStatuses(newStatuses);
  };

  const handleSubmit = () => {
    const count = Object.keys(bookStatuses).length;
    if (count < 4) {
      alert('Please rate at least 4 books!');
      return;
    }
    onAnswer(questionId, bookStatuses, `Rated ${count} books`);
  };

  const ratedCount = Object.keys(bookStatuses).length;

  return (
    <div className="book-calibration-input">
      <div className="books-list">
        {CALIBRATION_BOOKS.map((book) => (
          <div key={book.id} className="book-item">
            <div className="book-info">
              <div className="book-title-row">
                <span className="book-title">{book.title}</span>
                <div className="book-info-icon" data-tooltip={book.description}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                </div>
              </div>
              <span className="book-author">by {book.author}</span>
            </div>
            <div className="book-status-selector">
              {BOOK_STATUS_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  className={`selector-segment ${bookStatuses[book.externalId] === option.value ? 'active' : ''}`}
                  onClick={() => handleBookStatus(book.externalId, option.value)}
                  aria-pressed={bookStatuses[book.externalId] === option.value}
                >
                  {STATUS_ICONS[option.value]}
                  <span>{option.label}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="calibration-footer">
        <p className="rating-count">
          {ratedCount} of {CALIBRATION_BOOKS.length} rated{ratedCount >= 4 ? ' ✓' : ''}
        </p>
        <button className="submit-button" onClick={handleSubmit} disabled={ratedCount < 4}>
          Continue
        </button>
      </div>
    </div>
  );
};

export default BookCalibrationInput;
