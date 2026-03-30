import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { OnboardingProfile } from '../api/types';
import Button from '../components/Button';
import Card from '../components/Card';
import Badge from '../components/Badge';
import './ProfilePage.css';

interface BookStatusItem {
  book_id: string;
  status: string;
  updated_at: string;
  title?: string;
  author_name?: string;
}

interface ReadingProfileData {
  total_books_read: number;
  avg_rating: number | null;
  reading_confidence: number;
  structured_tags: Record<string, number> | null;
  profile_summary: string | null;
  generated_at: string | null;
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<OnboardingProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [bookStatuses, setBookStatuses] = useState<{
    interested: BookStatusItem[];
    read_liked: BookStatusItem[];
    read_disliked: BookStatusItem[];
    not_for_me: BookStatusItem[];
  }>({
    interested: [],
    read_liked: [],
    read_disliked: [],
    not_for_me: [],
  });
  const [loadingBookStatuses, setLoadingBookStatuses] = useState(false);

  // Reading history / DNA
  const [readingProfile, setReadingProfile] = useState<ReadingProfileData | null>(null);
  const [uploadingCsv, setUploadingCsv] = useState(false);
  const [csvMessage, setCsvMessage] = useState<string | null>(null);
  const [csvError, setCsvError] = useState<string | null>(null);
  const csvInputRef = useRef<HTMLInputElement>(null);

  const navigate = useNavigate();

  useEffect(() => {
    loadProfile();
    loadBookStatuses();
    loadReadingProfile();
  }, []);

  const loadBookStatuses = async () => {
    try {
      setLoadingBookStatuses(true);
      const [interested, readLiked, readDisliked, notForMe] = await Promise.all([
        apiClient.getBookStatusList('interested'),
        apiClient.getBookStatusList('read_liked'),
        apiClient.getBookStatusList('read_disliked'),
        apiClient.getBookStatusList('not_for_me'),
      ]);
      
      setBookStatuses({
        interested,
        read_liked: readLiked,
        read_disliked: readDisliked,
        not_for_me: notForMe,
      });
    } catch (err: any) {
      console.warn('Failed to load book statuses:', err);
      // Don't show error to user - this is optional data
    } finally {
      setLoadingBookStatuses(false);
    }
  };

  const loadProfile = async () => {
    try {
      setLoading(true);
      const profileData = await apiClient.getOnboarding();
      setProfile(profileData);
    } catch (err: any) {
      if (err.response?.status === 404) {
        navigate('/onboarding');
      } else {
        setError(err.response?.data?.detail || 'Failed to load profile');
      }
    } finally {
      setLoading(false);
    }
  };

  const loadReadingProfile = async () => {
    try {
      const data = await apiClient.getReadingProfile();
      setReadingProfile(data);
    } catch {
      // 404 = no profile yet — that's fine
    }
  };

  const handleCsvUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setCsvError('Please upload a .csv file exported from Goodreads.');
      return;
    }
    setUploadingCsv(true);
    setCsvError(null);
    setCsvMessage(null);
    try {
      const result = await apiClient.uploadReadingHistoryCsv(file);
      setCsvMessage(
        `✓ Imported ${result.imported_count} books` +
        (result.new_books_added > 0 ? ` (${result.new_books_added} added to catalog)` : '') +
        '. Your reading profile is being updated.'
      );
      // Reload profile after short delay for background task to start
      setTimeout(() => loadReadingProfile(), 3000);
    } catch (e: any) {
      setCsvError(e?.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setUploadingCsv(false);
      if (csvInputRef.current) csvInputRef.current.value = '';
    }
  };

  const handleReRunOnboarding = () => {
    navigate('/onboarding');
  };

  if (loading) {
    return (
      <div className="readar-profile-page">
        <div className="container">
          <div className="readar-loading">Loading...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="readar-profile-page">
        <div className="container">
          <Card variant="flat" className="readar-error-card">
            Error: {error}
          </Card>
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="readar-profile-page">
        <div className="container">
          <Card variant="elevated">
            <p>No profile found. Let's get you set up.</p>
            <Button variant="primary" onClick={handleReRunOnboarding} delayMs={140} className="readar-profile-action">
              Get Started
            </Button>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="readar-profile-page">
      <div className="container">
        <h1 className="readar-profile-title">Your Profile</h1>
        <div className="readar-profile-grid">
          <Card variant="flat" className="readar-profile-section">
            <h2 className="readar-profile-section-title">Personal Information</h2>
            <div className="readar-profile-field">
              <strong>Name:</strong> {profile.full_name}
            </div>
            {profile.occupation && (
              <div className="readar-profile-field">
                <strong>Occupation:</strong> {profile.occupation}
              </div>
            )}
            {profile.location && (
              <div className="readar-profile-field">
                <strong>Location:</strong> {profile.location}
              </div>
            )}
            {profile.industry && (
              <div className="readar-profile-field">
                <strong>Industry:</strong> {profile.industry}
              </div>
            )}
          </Card>

          <Card variant="flat" className="readar-profile-section">
            <h2 className="readar-profile-section-title">Business Information</h2>
            <div className="readar-profile-field">
              <strong>Business Model:</strong> {profile.business_model}
            </div>
            <div className="readar-profile-field">
              <strong>Business Stage:</strong>{' '}
              <Badge variant="purple" size="sm">{profile.business_stage}</Badge>
            </div>
            {profile.org_size && (
              <div className="readar-profile-field">
                <strong>Organization Size:</strong> {profile.org_size}
              </div>
            )}
            {profile.business_experience && (
              <div className="readar-profile-field">
                <strong>Experience:</strong> {profile.business_experience}
              </div>
            )}
          </Card>

          {profile.areas_of_business && profile.areas_of_business.length > 0 && (
            <Card variant="flat" className="readar-profile-section">
              <h2 className="readar-profile-section-title">Areas of Focus</h2>
              <div className="readar-profile-tags">
                {profile.areas_of_business.map((area) => (
                  <Badge key={area} variant="primary" size="md">{area}</Badge>
                ))}
              </div>
            </Card>
          )}

          <Card variant="flat" className="readar-profile-section">
            <h2 className="readar-profile-section-title">Challenges & Vision</h2>
            <div className="readar-profile-field">
              <strong>Biggest Challenge:</strong>
              <p>{profile.biggest_challenge}</p>
            </div>
            {profile.vision_6_12_months && (
              <div className="readar-profile-field">
                <strong>Vision (6-12 months):</strong>
                <p>{profile.vision_6_12_months}</p>
              </div>
            )}
            {profile.blockers && (
              <div className="readar-profile-field">
                <strong>Blockers:</strong>
                <p>{profile.blockers}</p>
              </div>
            )}
          </Card>
        </div>

        <div className="readar-profile-actions">
          <Button variant="primary" onClick={handleReRunOnboarding} delayMs={140}>
            Update Profile
          </Button>
        </div>

        {/* Reading History / DNA Section */}
        <div style={{ marginTop: '2rem' }}>
          <h2 className="readar-profile-section-title" style={{ marginBottom: '1rem' }}>
            Reading History
          </h2>
          <Card variant="flat" className="readar-profile-section">
            {readingProfile ? (
              <div>
                <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                  <div>
                    <span style={{ color: 'var(--rd-muted)', fontSize: 'var(--rd-font-size-sm)' }}>Books read</span>
                    <div style={{ fontWeight: 600, fontSize: 'var(--rd-font-size-lg)' }}>
                      {readingProfile.total_books_read}
                    </div>
                  </div>
                  {readingProfile.avg_rating != null && (
                    <div>
                      <span style={{ color: 'var(--rd-muted)', fontSize: 'var(--rd-font-size-sm)' }}>Avg rating</span>
                      <div style={{ fontWeight: 600, fontSize: 'var(--rd-font-size-lg)' }}>
                        {readingProfile.avg_rating.toFixed(1)} / 5
                      </div>
                    </div>
                  )}
                  <div>
                    <span style={{ color: 'var(--rd-muted)', fontSize: 'var(--rd-font-size-sm)' }}>Reading confidence</span>
                    <div style={{ fontWeight: 600, fontSize: 'var(--rd-font-size-lg)' }}>
                      {Math.round(readingProfile.reading_confidence * 100)}%
                    </div>
                  </div>
                </div>
                {readingProfile.profile_summary && (
                  <p style={{ marginBottom: '1rem', fontStyle: 'italic', color: 'var(--rd-muted)', fontSize: 'var(--rd-font-size-sm)' }}>
                    {readingProfile.profile_summary}
                  </p>
                )}
                {readingProfile.structured_tags && Object.keys(readingProfile.structured_tags).length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '1rem' }}>
                    {Object.entries(readingProfile.structured_tags)
                      .sort(([, a], [, b]) => b - a)
                      .slice(0, 8)
                      .map(([tag]) => (
                        <Badge key={tag} variant="primary" size="sm">{tag}</Badge>
                      ))}
                  </div>
                )}
              </div>
            ) : (
              <p style={{ color: 'var(--rd-muted)', fontSize: 'var(--rd-font-size-sm)', marginBottom: '0.75rem' }}>
                No reading history imported yet. Upload a Goodreads CSV to personalise your recommendations.
              </p>
            )}

            {/* Upload control */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
              <input
                ref={csvInputRef}
                type="file"
                accept=".csv"
                style={{ display: 'none' }}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleCsvUpload(f);
                }}
              />
              <Button
                variant="secondary"
                onClick={() => csvInputRef.current?.click()}
                disabled={uploadingCsv}
                delayMs={0}
              >
                {uploadingCsv
                  ? 'Uploading...'
                  : readingProfile
                  ? 'Update Goodreads history'
                  : 'Import Goodreads history'}
              </Button>
              {csvMessage && (
                <span style={{ color: 'var(--rd-success, green)', fontSize: 'var(--rd-font-size-sm)' }}>
                  {csvMessage}
                </span>
              )}
              {csvError && (
                <span style={{ color: 'var(--rd-error, red)', fontSize: 'var(--rd-font-size-sm)' }}>
                  {csvError}
                </span>
              )}
            </div>
          </Card>
        </div>

        {/* Book Activity Section */}
        <div style={{ marginTop: '2rem' }}>
          <h2 className="readar-profile-section-title" style={{ marginBottom: '1rem' }}>
            Book Activity
          </h2>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
            {/* Interested */}
            <Card variant="flat" className="readar-profile-section">
              <h3 style={{ fontSize: 'var(--rd-font-size-lg)', fontWeight: 600, marginBottom: '0.75rem' }}>
                Interested
              </h3>
              {loadingBookStatuses ? (
                <p style={{ color: 'var(--rd-muted)', fontSize: 'var(--rd-font-size-sm)' }}>Loading...</p>
              ) : bookStatuses.interested.length === 0 ? (
                <p style={{ color: 'var(--rd-muted)', fontSize: 'var(--rd-font-size-sm)' }}>No books yet</p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {bookStatuses.interested.map((item) => (
                    <li key={item.book_id} style={{ marginBottom: '0.5rem', fontSize: 'var(--rd-font-size-sm)' }}>
                      {item.title ? (
                        <>
                          <strong>{item.title}</strong>
                          {item.author_name && <span style={{ color: 'var(--rd-muted)' }}> by {item.author_name}</span>}
                        </>
                      ) : (
                        <span style={{ color: 'var(--rd-muted)' }}>{item.book_id}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            {/* Read (Liked) */}
            <Card variant="flat" className="readar-profile-section">
              <h3 style={{ fontSize: 'var(--rd-font-size-lg)', fontWeight: 600, marginBottom: '0.75rem' }}>
                Read (Liked)
              </h3>
              {loadingBookStatuses ? (
                <p style={{ color: 'var(--rd-muted)', fontSize: 'var(--rd-font-size-sm)' }}>Loading...</p>
              ) : bookStatuses.read_liked.length === 0 ? (
                <p style={{ color: 'var(--rd-muted)', fontSize: 'var(--rd-font-size-sm)' }}>No books yet</p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {bookStatuses.read_liked.map((item) => (
                    <li key={item.book_id} style={{ marginBottom: '0.5rem', fontSize: 'var(--rd-font-size-sm)' }}>
                      {item.title ? (
                        <>
                          <strong>{item.title}</strong>
                          {item.author_name && <span style={{ color: 'var(--rd-muted)' }}> by {item.author_name}</span>}
                        </>
                      ) : (
                        <span style={{ color: 'var(--rd-muted)' }}>{item.book_id}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            {/* Read (Disliked) */}
            <Card variant="flat" className="readar-profile-section">
              <h3 style={{ fontSize: 'var(--rd-font-size-lg)', fontWeight: 600, marginBottom: '0.75rem' }}>
                Read (Disliked)
              </h3>
              {loadingBookStatuses ? (
                <p style={{ color: 'var(--rd-muted)', fontSize: 'var(--rd-font-size-sm)' }}>Loading...</p>
              ) : bookStatuses.read_disliked.length === 0 ? (
                <p style={{ color: 'var(--rd-muted)', fontSize: 'var(--rd-font-size-sm)' }}>No books yet</p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {bookStatuses.read_disliked.map((item) => (
                    <li key={item.book_id} style={{ marginBottom: '0.5rem', fontSize: 'var(--rd-font-size-sm)' }}>
                      {item.title ? (
                        <>
                          <strong>{item.title}</strong>
                          {item.author_name && <span style={{ color: 'var(--rd-muted)' }}> by {item.author_name}</span>}
                        </>
                      ) : (
                        <span style={{ color: 'var(--rd-muted)' }}>{item.book_id}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            {/* Not for me */}
            <Card variant="flat" className="readar-profile-section">
              <h3 style={{ fontSize: 'var(--rd-font-size-lg)', fontWeight: 600, marginBottom: '0.75rem' }}>
                Not for me
              </h3>
              {loadingBookStatuses ? (
                <p style={{ color: 'var(--rd-muted)', fontSize: 'var(--rd-font-size-sm)' }}>Loading...</p>
              ) : bookStatuses.not_for_me.length === 0 ? (
                <p style={{ color: 'var(--rd-muted)', fontSize: 'var(--rd-font-size-sm)' }}>No books yet</p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {bookStatuses.not_for_me.map((item) => (
                    <li key={item.book_id} style={{ marginBottom: '0.5rem', fontSize: 'var(--rd-font-size-sm)' }}>
                      {item.title ? (
                        <>
                          <strong>{item.title}</strong>
                          {item.author_name && <span style={{ color: 'var(--rd-muted)' }}> by {item.author_name}</span>}
                        </>
                      ) : (
                        <span style={{ color: 'var(--rd-muted)' }}>{item.book_id}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

