import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import Button from './Button';
import { amazonBookUrl } from '../utils/amazonBookUrl';
import './ChooseBookButton.css';

interface Props {
  bookId: string;
  title?: string;
  author?: string;
  purchaseUrl?: string | null;
  requestId?: string;
  position?: number;
  disabled?: boolean;
  onBusyChange?: (busy: boolean) => void;
}

/** Reserve a tab in the click gesture; visit Amazon only after persistence. */
export default function ChooseBookButton({ bookId, title, author, purchaseUrl, requestId, position, disabled, onBusyChange }: Props) {
  const navigate = useNavigate();
  const pending = useRef(false);
  const generation = useRef(0);
  const reservedTab = useRef<Window | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const url = amazonBookUrl(purchaseUrl, title, author);

  useEffect(() => () => {
    generation.current += 1;
    // Close only a still-pending blank tab, never an opened retailer page.
    try { reservedTab.current?.close(); } catch { /* already closed */ }
    reservedTab.current = null;
  }, []);

  const choose = async (getBook: boolean) => {
    if (pending.current || disabled) return;
    pending.current = true;
    const requestGeneration = generation.current;
    setSaving(true);
    setError('');
    onBusyChange?.(true);
    let tab: Window | null = null;
    if (getBook && url) {
      try {
        tab = window.open('about:blank', '_blank');
        if (tab) {
          tab.opener = null;
          reservedTab.current = tab;
          tab.document.title = 'Saving your book — Readar';
          tab.document.body.textContent = 'Saving your book to Reading. Amazon will open once your choice is saved…';
        }
      } catch {
        try { tab?.close(); } catch { /* already closed */ }
        tab = null;
        reservedTab.current = null;
      }
    }
    try {
      const saved = await apiClient.selectBookForReading({
        book_id: bookId, request_id: requestId, position, intent: getBook ? 'get_book' : 'choose',
      });
      if (!saved?.ok || !['reading_next', 'waiting_for_book', 'currently_reading'].includes(saved.status)) {
        throw new Error('Selection was not confirmed');
      }
      if (generation.current !== requestGeneration) return;
      let amazonOpened = false;
      if (getBook && url && tab && !tab.closed) {
        try {
          tab.location.replace(url);
          amazonOpened = true;
        } catch { try { tab.close(); } catch { /* offer the direct link */ } }
      }
      reservedTab.current = null;
      navigate('/reading', { state: { bookSelection: {
        bookId, title: title || 'Your book', status: saved.status,
        amazonUrl: getBook ? url : null, amazonOpened,
      } } });
    } catch {
      try { tab?.close(); } catch { /* already closed */ }
      reservedTab.current = null;
      if (generation.current === requestGeneration) setError("We couldn't confirm your saved choice. Please try again.");
    } finally {
      if (generation.current === requestGeneration) {
        pending.current = false;
        setSaving(false);
        onBusyChange?.(false);
      }
    }
  };

  return (
    <div className="readar-choose-book">
      <Button variant="primary" onClick={() => choose(!!url)} disabled={disabled || saving} aria-busy={saving}>
        {saving ? 'Saving your choice…' : url ? 'Get book + add to Reading' : 'Add to Reading'}
      </Button>
      <p className="readar-book-handoff-hint">{url ? 'Opens Amazon in a new tab. Your choice stays in Reading while you wait for your copy.' : 'An Amazon link isn’t available. You can still save this book to Reading.'}</p>
      {url && <button type="button" className="readar-owned-book" onClick={() => choose(false)} disabled={disabled || saving}>
        I already have this book
      </button>}
      {error && <p role="alert" className="readar-action-error">{error}</p>}
    </div>
  );
}
