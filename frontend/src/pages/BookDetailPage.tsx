import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { Book, BookPreferenceStatus } from '../api/types';
import Button from '../components/Button';
import Card from '../components/Card';
import Badge from '../components/Badge';
import './BookDetailPage.css';

export default function BookDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [book, setBook] = useState<Book | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (id) {
      loadBook(id);
    }
  }, [id]);

  const loadBook = async (bookId: string) => {
    try {
      setLoading(true);
      const bookData = await apiClient.getBook(bookId);
      setBook(bookData);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load book');
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (status: BookPreferenceStatus) => {
    if (!id) return;
    try {
      await apiClient.updateUserBook(id, status);
      navigate('/recommendations');
    } catch (err) {
      console.error('Failed to update book status:', err);
    }
  };

  if (loading) {
    return (
      <div className="readar-book-detail-page">
        <div className="container">
          <div className="readar-loading">Loading...</div>
        </div>
      </div>
    );
  }

  if (error || !book) {
    return (
      <div className="readar-book-detail-page">
        <div className="container">
          <Card variant="flat" className="readar-error-card">
            Error: {error || 'Book not found'}
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="readar-book-detail-page">
      <div className="container">
        <Button variant="ghost" onClick={() => navigate(-1)} delayMs={140} className="readar-back-button">
          ← Back
        </Button>
        <Card variant="elevated" className="readar-book-detail-card">
          <div className="readar-book-detail-header">
            <h1 className="readar-book-detail-title">{book.title}</h1>
            {book.subtitle && <h2 className="readar-book-detail-subtitle">{book.subtitle}</h2>}
            <p className="readar-book-detail-author">by {book.author_name}</p>
            <div className="readar-book-detail-meta">
              {book.published_year && (
                <Badge variant="dark" size="sm">Published {book.published_year}</Badge>
              )}
              {book.page_count && (
                <Badge variant="dark" size="sm">{book.page_count} pages</Badge>
              )}
              {book.difficulty && (
                <Badge variant="secondary" size="sm">{book.difficulty}</Badge>
              )}
            </div>
          </div>
          
          <div className="readar-book-detail-description">
            <h3>Description</h3>
            <p>{book.description}</p>
          </div>
          
          {(book.categories || book.business_stage_tags || book.functional_tags) && (
            <div className="readar-book-detail-tags">
              {book.categories && book.categories.length > 0 && (
                <div className="readar-tag-group">
                  <strong>Categories:</strong>
                  <div className="readar-tag-list">
                    {book.categories.map((cat) => (
                      <Badge key={cat} variant="primary" size="sm">{cat}</Badge>
                    ))}
                  </div>
                </div>
              )}
              {book.business_stage_tags && book.business_stage_tags.length > 0 && (
                <div className="readar-tag-group">
                  <strong>Business Stages:</strong>
                  <div className="readar-tag-list">
                    {book.business_stage_tags.map((tag) => (
                      <Badge key={tag} variant="purple" size="sm">{tag}</Badge>
                    ))}
                  </div>
                </div>
              )}
              {book.functional_tags && book.functional_tags.length > 0 && (
                <div className="readar-tag-group">
                  <strong>Focus Areas:</strong>
                  <div className="readar-tag-list">
                    {book.functional_tags.map((tag) => (
                      <Badge key={tag} variant="warm" size="sm">{tag}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          
          <div className="readar-book-detail-actions">
            <Button variant="primary" onClick={() => handleAction('interested')} delayMs={140}>
              Save as Interested
            </Button>
            <Button variant="secondary" onClick={() => handleAction('read_liked')} delayMs={140}>
              Mark as Read (Liked)
            </Button>
            <Button variant="ghost" onClick={() => handleAction('read_disliked')} delayMs={140}>
              Mark as Read (Disliked)
            </Button>
            <Button variant="ghost" onClick={() => handleAction('not_interested')} delayMs={140}>
              Not for me
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}

