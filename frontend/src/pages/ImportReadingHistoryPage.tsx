import { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient, logEvent } from '../api/client';
import RadarIcon from '../components/RadarIcon';
import ReadarBrand from '../components/ReadarBrand';
import './ImportReadingHistoryPage.css';

const GOODREADS_EXPORT_URL = 'https://www.goodreads.com/review/import';

/**
 * Dedicated post-auth, pre-recommendations step.
 * Offers an optional Goodreads import at peak buy-in, with a prominent skip.
 */
export default function ImportReadingHistoryPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const prefetched = (location.state as any)?.prefetchedRecommendations;
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);
  const mounted = useRef(false);
  const navigated = useRef(false);
  type Receipt = { imported_count: number; skipped_count: number };
  const receipt = (location.state as { importReceipt?: Receipt } | null)?.importReceipt;
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  useEffect(() => {
    void logEvent('onboarding_import_shown');
  }, []);

  // Skip keeps the conversation-based picks we already fetched.
  const skipToPicks = () => {
    void logEvent('onboarding_import_skipped');
    navigate('/recommendations', { state: { prefetchedRecommendations: prefetched }, replace: true });
  };

  // After import, re-fetch fresh so the just-imported history is reflected.
  function continueWithFreshPicks() {
    if (pending.current || navigated.current) return;
    navigated.current = true;
    // Keep this receipt in browser history so Back restores it without re-upload.
    // Never fall back to picks prepared before this import if the fresh fetch fails.
    navigate('/recommendations', { state: { requireFreshRecommendations: true } });
  }

  const handleFile = async (file: File) => {
    if (pending.current) return;
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('Please upload a .csv file exported from Goodreads.');
      return;
    }
    pending.current = true;
    setUploading(true);
    setError(null);
    try {
      const result = await apiClient.uploadReadingHistoryCsv(file);
      if (!mounted.current) return;
      if (![result?.imported_count, result?.skipped_count].every(n => Number.isInteger(n) && n >= 0)) {
        throw new Error('The import response could not be confirmed. Check your library before trying again.');
      }
      void logEvent('onboarding_import_completed', { imported_count: result.imported_count, skipped_count: result.skipped_count });
      // A receipt belongs to this history entry; refreshing never resubmits a file.
      navigate(location.pathname, { replace: true, state: { importReceipt: {
        imported_count: result.imported_count, skipped_count: result.skipped_count,
      } } });
    } catch (e: any) {
      if (!mounted.current) return;
      setError(
        e?.response?.data?.detail ||
          e?.message || 'Upload failed — you can skip for now and import later from your profile.',
      );
    } finally {
      pending.current = false;
      if (mounted.current) setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  return (
    <div className="import-page rd-scan-bg">
      <div className="import-card">
        <ReadarBrand />
        <h1 className="import-title">{receipt ? receipt.imported_count ? "Your reading history is saved." : "No entries were imported." : "Make these picks yours."}</h1>
        {!receipt && <p className="import-sub">
          Want me to factor in what you've <em>actually</em> read? Import your Goodreads
          history and I'll sharpen your picks around it — or skip straight to your picks.
        </p>}

        <input
          ref={fileRef}
          type="file"
          accept=".csv"
          aria-label="Goodreads CSV file"
          disabled={uploading}
          style={{ display: 'none' }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
        />

        {receipt ? <section className="import-success" aria-label="Import confirmation">
          <p role="status" aria-live="polite" aria-atomic="true">
            {receipt.imported_count} {receipt.imported_count === 1 ? 'entry' : 'entries'} saved to your library.
            {receipt.skipped_count > 0 && ` ${receipt.skipped_count} ${receipt.skipped_count === 1 ? 'row was' : 'rows were'} skipped.`}
          </p>
          <p className="import-sub">{receipt.imported_count ? 'Your next picks will take your saved reading history into account. Continue whenever you’re ready.' : 'Check that your CSV includes book titles, or continue using your existing profile and reading history.'}</p>
          <button className="import-btn-primary" disabled={uploading} onClick={continueWithFreshPicks}>Continue to my recommendations →</button>
          <button className="import-skip" disabled={uploading} onClick={() => fileRef.current?.click()}>Choose another CSV</button>
          <p className="import-sub">Another import adds to your library; it doesn’t remove previously saved books.</p>
          {uploading && <p role="status">Importing your reading history…</p>}
        </section> : uploading ? (
          <div className="import-uploading" role="status">
            <RadarIcon size={88} animationDuration={6} />
            <p>Importing your reading history…</p>
          </div>
        ) : (
          <>
            <button className="import-btn-primary" onClick={() => fileRef.current?.click()}>
              Import Goodreads history
            </button>
            <button className="import-skip" onClick={skipToPicks}>
              Skip to your picks →
            </button>
          </>
        )}

        {error && <p className="import-error" role="alert">{error}</p>}

        {!receipt && <details className="import-how">
          <summary>How do I export from Goodreads?</summary>
          <ol>
            <li>
              Open your{' '}
              <a className="import-link" href={GOODREADS_EXPORT_URL} target="_blank" rel="noopener noreferrer">
                Goodreads Import/Export page ↗
              </a>
            </li>
            <li>Click <strong>Export Library</strong> and download the CSV</li>
            <li>Come back here and upload that file</li>
          </ol>
        </details>}
      </div>
    </div>
  );
}
