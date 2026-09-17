import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import Button from './Button';

interface Props {
  bookId: string;
  requestId?: string;
  position?: number;
  disabled?: boolean;
  onBusyChange?: (busy: boolean) => void;
}

/** Save first, then open the hub. Re-selecting never downgrades a started book. */
export default function ChooseBookButton({ bookId, requestId, position, disabled, onBusyChange }: Props) {
  const navigate = useNavigate();
  const pending = useRef(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const choose = async () => {
    if (pending.current || disabled) return;
    pending.current = true;
    setSaving(true);
    setError('');
    onBusyChange?.(true);
    try {
      await apiClient.selectBookForReading({ book_id: bookId, request_id: requestId, position });
      navigate('/reading');
    } catch {
      setError("We couldn't save your choice. Please try again.");
    } finally {
      pending.current = false;
      setSaving(false);
      onBusyChange?.(false);
    }
  };

  return (
    <div>
      <Button variant="primary" onClick={choose} disabled={disabled || saving} aria-busy={saving}>
        {saving ? 'Saving your choice…' : 'Choose this book'}
      </Button>
      {error && <p role="alert" className="readar-action-error">{error}</p>}
    </div>
  );
}
