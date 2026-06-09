import { useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient } from '../api/client';
import RadarIcon from '../components/RadarIcon';
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

  // Skip keeps the conversation-based picks we already fetched.
  const skipToPicks = () =>
    navigate('/recommendations', { state: { prefetchedRecommendations: prefetched }, replace: true });

  // After import, re-fetch fresh so the just-imported history is reflected.
  const continueWithFreshPicks = () => navigate('/recommendations', { replace: true });

  const handleFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('Please upload a .csv file exported from Goodreads.');
      return;
    }
    setUploading(true);
    setError(null);
    try {
      await apiClient.uploadReadingHistoryCsv(file);
      continueWithFreshPicks();
    } catch (e: any) {
      setError(
        e?.response?.data?.detail ||
          'Upload failed — you can skip for now and import later from your profile.',
      );
      setUploading(false);
    }
  };

  return (
    <div className="import-page">
      <div className="import-card">
        <h1 className="import-title">Last thing.</h1>
        <p className="import-sub">
          Want me to factor in what you've <em>actually</em> read? Import your Goodreads
          history and I'll sharpen your picks around it — or skip straight to your picks.
        </p>

        <input
          ref={fileRef}
          type="file"
          accept=".csv"
          style={{ display: 'none' }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
        />

        {uploading ? (
          <div className="import-uploading">
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

        {error && <p className="import-error">{error}</p>}

        <details className="import-how">
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
        </details>
      </div>
    </div>
  );
}
