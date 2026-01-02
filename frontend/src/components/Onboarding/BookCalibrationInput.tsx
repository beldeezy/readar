import React, { useState } from 'react';
import { CALIBRATION_BOOKS, BOOK_STATUS_OPTIONS } from '../../config/chatOnboarding';
import './BookCalibrationInput.css';

interface BookCalibrationInputProps {
  onAnswer: (questionId: string, answer: any, displayText?: string) => void;
  questionId: string;
}

const BookCalibrationInput: React.FC<BookCalibrationInputProps> = ({ onAnswer, questionId }) => {
  const [bookStatuses, setBookStatuses] = useState<Record<string, string>>({});

  const handleBookStatus = (externalId: string, status: string) => {
    const newStatuses = {
      ...bookStatuses,
      [externalId]: status,
    };
    setBookStatuses(newStatuses);
  };

  const handleSubmit = () => {
    const count = Object.keys(bookStatuses).length;
    if (count < 4) {
      alert('Please rate at least 4 books!');
      return;
    }

    const displayText = `Rated ${count} books`;
    onAnswer(questionId, bookStatuses, displayText);
  };

  const getStatusEmoji = (externalId: string): string => {
    const status = bookStatuses[externalId];
    if (!status) return '';

    const option = BOOK_STATUS_OPTIONS.find((opt) => opt.value === status);
    return option?.emoji || '';
  };

  const ratedCount = Object.keys(bookStatuses).length;

  return (
    <div className="book-calibration-input">
      <div className="books-list">
        {CALIBRATION_BOOKS.map((book) => (
          <div key={book.id} className="book-item">
            <div className="book-info">
              <span className="book-title">{book.title}</span>
              <span className="book-author">by {book.author}</span>
              {bookStatuses[book.externalId] && (
                <span className="book-status-emoji">{getStatusEmoji(book.externalId)}</span>
              )}
            </div>
            <div className="book-status-buttons">
              {BOOK_STATUS_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  className={`status-button ${
                    bookStatuses[book.externalId] === option.value ? 'active' : ''
                  }`}
                  onClick={() => handleBookStatus(book.externalId, option.value)}
                  title={option.label}
                >
                  {option.emoji}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="calibration-footer">
        <p className="rating-count">
          {ratedCount} of 6 books rated {ratedCount >= 4 && '✓'}
        </p>
        <button className="submit-button" onClick={handleSubmit} disabled={ratedCount < 4}>
          Continue
        </button>
      </div>
    </div>
  );
};

export default BookCalibrationInput;
