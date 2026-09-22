import { amazonBookUrl } from '../utils/amazonBookUrl';

export interface BookSelectionReceipt {
  bookId: string;
  title: string;
  status: string;
  amazonUrl: string | null;
  amazonOpened: boolean;
}

/** Navigation receipt only; the reading list itself is always loaded from the account. */
export default function BookSelectionNotice({ receipt }: { receipt?: BookSelectionReceipt }) {
  if (!receipt || typeof receipt.title !== 'string') return null;
  const url = amazonBookUrl(receipt.amazonUrl);
  return <section className="reading-selection-notice" aria-label="Book saved">
    <div role="status">
      <h2>{receipt.title} is saved to Reading.</h2>
      <p>{receipt.status === 'currently_reading' ? 'Your existing reading progress is unchanged.'
        : receipt.status === 'waiting_for_book' ? 'Your choice is waiting below. Select Start reading when your copy is ready.'
        : 'Your book is in Up next below. Select Start reading when you’re ready.'}</p>
      {url && <p>{receipt.amazonOpened ? 'Amazon opened in a new tab.' : 'Amazon didn’t open automatically. Your choice is still saved.'}</p>}
    </div>
    {url && <a className="reading-text-link" href={url} target="_blank" rel="noopener noreferrer">Open Amazon ↗</a>}
  </section>;
}
