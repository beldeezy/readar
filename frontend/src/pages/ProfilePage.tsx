import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Library, BookMarked, LogOut, Zap, Settings } from 'lucide-react';
import { apiClient } from '../api/client';
import { useAuth } from '../auth/AuthProvider';
import type { OnboardingProfile, KnowledgeMap, NotificationPreferences } from '../api/types';
import Button from '../components/Button';
import Card from '../components/Card';
import Badge from '../components/Badge';
import FounderKnowledgeMap from '../components/FounderKnowledgeMap';
import Gauge from '../components/Gauge';
import SegmentReadout from '../components/SegmentReadout';
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

type ActivityTab = 'interested' | 'read_liked' | 'read_disliked' | 'not_for_me';

const STAGE_OPTIONS: { value: OnboardingProfile['business_stage']; label: string }[] = [
  { value: 'idea', label: 'Idea' },
  { value: 'pre-revenue', label: 'Pre-revenue' },
  { value: 'early-revenue', label: 'Early revenue' },
  { value: 'scaling', label: 'Scaling' },
];

const ACTIVITY_TABS: { key: ActivityTab; label: string }[] = [
  { key: 'interested', label: 'Interested' },
  { key: 'read_liked', label: 'Read · Liked' },
  { key: 'read_disliked', label: 'Read · Disliked' },
  { key: 'not_for_me', label: 'Not for me' },
];

// Fields that meaningfully sharpen recommendations. Used for the completeness pathway.
const COMPLETENESS_FIELDS: { key: keyof OnboardingProfile; label: string }[] = [
  { key: 'full_name', label: 'Name' },
  { key: 'biggest_challenge', label: 'Biggest challenge' },
  { key: 'business_stage', label: 'Business stage' },
  { key: 'vision_6_12_months', label: 'Vision (6–12 months)' },
  { key: 'industry', label: 'Industry' },
  { key: 'business_model', label: 'Business model' },
  { key: 'occupation', label: 'Occupation' },
  { key: 'areas_of_business', label: 'Areas of business' },
];

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function hasValue(v: unknown): boolean {
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === 'string') return v.trim().length > 0;
  return v != null;
}

interface Completeness {
  pct: number;
  missing: { key: keyof OnboardingProfile; label: string }[];
}

function computeCompleteness(profile: OnboardingProfile): Completeness {
  const missing = COMPLETENESS_FIELDS.filter((f) => !hasValue(profile[f.key]));
  const filled = COMPLETENESS_FIELDS.length - missing.length;
  return { pct: Math.round((filled / COMPLETENESS_FIELDS.length) * 100), missing };
}

// Largest gap between the ideal and the user's current coverage → the highest-leverage domain to read into.
function weakestDomain(map: KnowledgeMap | null): { label: string; gap: number } | null {
  if (!map?.domains?.length || !map?.ideal?.length) return null;
  const idealByKey = new Map(map.ideal.map((d) => [d.key, d.score]));
  let best: { label: string; gap: number } | null = null;
  for (const d of map.domains) {
    const ideal = idealByKey.get(d.key) ?? 0;
    const gap = ideal - d.score;
    if (gap > 0 && (!best || gap > best.gap)) best = { label: d.label, gap };
  }
  return best;
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<OnboardingProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [bookStatuses, setBookStatuses] = useState<Record<ActivityTab, BookStatusItem[]>>({
    interested: [],
    read_liked: [],
    read_disliked: [],
    not_for_me: [],
  });
  const [loadingBookStatuses, setLoadingBookStatuses] = useState(false);
  const [activityTab, setActivityTab] = useState<ActivityTab>('interested');
  const [currentlyReading, setCurrentlyReading] = useState<BookStatusItem[]>([]);

  // Notification preferences
  const [notifPrefs, setNotifPrefs] = useState<NotificationPreferences | null>(null);
  const [savingNotifKey, setSavingNotifKey] = useState<keyof NotificationPreferences | null>(null);

  // Reading history / DNA
  const [readingProfile, setReadingProfile] = useState<ReadingProfileData | null>(null);
  const [uploadingCsv, setUploadingCsv] = useState(false);
  const [csvMessage, setCsvMessage] = useState<string | null>(null);
  const [csvError, setCsvError] = useState<string | null>(null);
  const csvInputRef = useRef<HTMLInputElement>(null);

  // Founder Knowledge Map
  const [knowledgeMap, setKnowledgeMap] = useState<KnowledgeMap | null>(null);
  const [knowledgeMapLoading, setKnowledgeMapLoading] = useState(true);

  // Inline editing of high-signal "focus" fields
  const [editingFocus, setEditingFocus] = useState(false);
  const [focusDraft, setFocusDraft] = useState<{
    biggest_challenge: string;
    business_stage: OnboardingProfile['business_stage'];
    vision_6_12_months: string;
  }>({ biggest_challenge: '', business_stage: 'idea', vision_6_12_months: '' });
  const [savingFocus, setSavingFocus] = useState(false);
  const [focusError, setFocusError] = useState<string | null>(null);

  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  useEffect(() => {
    loadProfile();
    loadBookStatuses();
    loadReadingProfile();
    loadKnowledgeMap();
    loadNotifPrefs();
  }, []);

  const loadNotifPrefs = async () => {
    try {
      const prefs = await apiClient.getNotificationPreferences();
      setNotifPrefs(prefs);
    } catch {
      // Non-fatal — section simply won't render
    }
  };

  const toggleNotif = async (key: keyof NotificationPreferences) => {
    if (!notifPrefs) return;
    const next = !notifPrefs[key];
    setNotifPrefs({ ...notifPrefs, [key]: next }); // optimistic
    setSavingNotifKey(key);
    try {
      await apiClient.updateNotificationPreferences({ [key]: next });
    } catch {
      setNotifPrefs({ ...notifPrefs, [key]: !next }); // revert on failure
    } finally {
      setSavingNotifKey(null);
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

  const loadBookStatuses = async () => {
    try {
      setLoadingBookStatuses(true);
      const [interested, readLiked, readDisliked, notForMe, reading] = await Promise.all([
        apiClient.getBookStatusList('interested'),
        apiClient.getBookStatusList('read_liked'),
        apiClient.getBookStatusList('read_disliked'),
        apiClient.getBookStatusList('not_for_me'),
        apiClient.getBookStatusList('currently_reading'),
      ]);
      setBookStatuses({
        interested,
        read_liked: readLiked,
        read_disliked: readDisliked,
        not_for_me: notForMe,
      });
      setCurrentlyReading(reading);
    } catch (err: any) {
      console.warn('Failed to load book statuses:', err);
    } finally {
      setLoadingBookStatuses(false);
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

  const loadKnowledgeMap = async () => {
    try {
      setKnowledgeMapLoading(true);
      const data = await apiClient.getKnowledgeMap();
      setKnowledgeMap(data);
    } catch {
      // Non-fatal — show empty state
    } finally {
      setKnowledgeMapLoading(false);
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
          '. Your reading profile is being updated.',
      );
      // Reload derived data after background task starts
      setTimeout(() => {
        loadReadingProfile();
        loadKnowledgeMap();
      }, 3000);
    } catch (e: any) {
      setCsvError(e?.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setUploadingCsv(false);
      if (csvInputRef.current) csvInputRef.current.value = '';
    }
  };

  const startEditFocus = () => {
    if (!profile) return;
    setFocusDraft({
      biggest_challenge: profile.biggest_challenge || '',
      business_stage: profile.business_stage,
      vision_6_12_months: profile.vision_6_12_months || '',
    });
    setFocusError(null);
    setEditingFocus(true);
  };

  const saveFocus = async () => {
    if (!profile) return;
    if (!focusDraft.biggest_challenge.trim()) {
      setFocusError('Biggest challenge cannot be empty.');
      return;
    }
    setSavingFocus(true);
    setFocusError(null);
    try {
      await apiClient.patchOnboarding({
        biggest_challenge: focusDraft.biggest_challenge.trim(),
        business_stage: focusDraft.business_stage,
        vision_6_12_months: focusDraft.vision_6_12_months.trim() || undefined,
      });
      setProfile({ ...profile, ...focusDraft });
      setEditingFocus(false);
      // Stage / challenge changed → ideal target shifts, so refresh the map
      loadKnowledgeMap();
    } catch (e: any) {
      setFocusError(e?.message || 'Failed to save. Please try again.');
    } finally {
      setSavingFocus(false);
    }
  };

  if (loading) {
    return (
      <div className="readar-profile-page rd-scan-bg">
        <div className="container">
          <div className="readar-loading">Loading...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="readar-profile-page rd-scan-bg">
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
      <div className="readar-profile-page rd-scan-bg">
        <div className="container">
          <Card variant="elevated">
            <p>No profile found. Let's get you set up.</p>
            <Button variant="primary" onClick={() => navigate('/onboarding')} delayMs={140} className="readar-profile-action">
              Get Started
            </Button>
          </Card>
        </div>
      </div>
    );
  }

  const activeList = bookStatuses[activityTab];

  // ── Derived signals (identity, momentum, completeness) ──────────────────
  const stageLabel =
    STAGE_OPTIONS.find((s) => s.value === profile.business_stage)?.label ?? profile.business_stage;
  const completeness = computeCompleteness(profile);
  const weakest = weakestDomain(knowledgeMap);
  const booksReadCount = bookStatuses.read_liked.length + bookStatuses.read_disliked.length;
  const interestedCount = bookStatuses.interested.length;
  // Living momentum line: reflect what's in flight, then nudge toward the highest-leverage next read.
  const momentumText = currentlyReading.length > 0
    ? `Currently reading ${currentlyReading.length} ${currentlyReading.length === 1 ? 'book' : 'books'}` +
      (weakest ? ` · biggest gap: ${weakest.label}.` : '.')
    : weakest
      ? `Your biggest knowledge gap is ${weakest.label} — your next read can close it.`
      : booksReadCount === 0
        ? 'Mark a book as read to start building your Knowledge Map.'
        : `${booksReadCount} ${booksReadCount === 1 ? 'book' : 'books'} logged${
            interestedCount > 0 ? ` · ${interestedCount} on your interested list` : ''
          }.`;

  return (
    <div className="readar-profile-page rd-scan-bg">
      <div className="container">
        {/* ── Identity + momentum + primary action (above the fold) ───────── */}
        <Card variant="flat" className="readar-profile-section readar-identity">
          <div className="readar-identity-main">
            <div className="readar-avatar" aria-hidden="true">{getInitials(profile.full_name)}</div>
            <div className="readar-identity-info">
              <h1 className="readar-identity-name">{profile.full_name}</h1>
              <div className="readar-identity-meta">
                <Badge variant="purple" size="sm">{stageLabel}</Badge>
                {profile.occupation && <span className="readar-identity-occ">{profile.occupation}</span>}
              </div>
              <p className="readar-identity-momentum">{momentumText}</p>
            </div>
          </div>
          <div className="readar-identity-actions">
            <Button variant="primary" onClick={() => navigate('/recommendations')} delayMs={0}>
              <BookOpen size={18} strokeWidth={2} style={{ marginRight: '0.4rem', verticalAlign: 'text-bottom' }} />
              See your recommendations
            </Button>
            <Button variant="secondary" onClick={() => navigate('/library')} delayMs={0}>
              <Library size={18} strokeWidth={2} style={{ marginRight: '0.4rem', verticalAlign: 'text-bottom' }} />
              Browse library
            </Button>
            <Button variant="secondary" onClick={() => navigate('/shelves')} delayMs={0}>
              <BookMarked size={18} strokeWidth={2} style={{ marginRight: '0.4rem', verticalAlign: 'text-bottom' }} />
              My Shelves
            </Button>
          </div>
        </Card>

        {/* ── Profile completeness pathway (utility-led) ──────────────── */}
        {completeness.pct < 100 && (
          <Card variant="flat" className="readar-profile-section readar-completeness">
            <div className="readar-completeness-head">
              <span className="readar-completeness-label">
                Profile {completeness.pct}% complete
              </span>
              <button className="readar-link-button" onClick={startEditFocus}>
                Sharpen recommendations
              </button>
            </div>
            <div className="readar-completeness-bar">
              <div className="readar-completeness-fill" style={{ width: `${completeness.pct}%` }} />
            </div>
            <p className="readar-completeness-hint">
              Add {completeness.missing.slice(0, 3).map((m) => m.label).join(', ')}
              {completeness.missing.length > 3 ? ' and more' : ''} so Readar can match books more precisely.
            </p>
          </Card>
        )}

        {/* ── Hero: Founder Knowledge Map ─────────────────────────────── */}
        <Card variant="flat" className="readar-profile-section fkm-hero">
          <div className="fkm-hero-head">
            <h2 className="readar-profile-section-title" style={{ border: 'none', marginBottom: 0, paddingBottom: 0 }}>
              Founder Knowledge Map
            </h2>
            <p className="fkm-hero-sub">
              Where your reading has built knowledge across the six domains of an
              entrepreneur — measured against the ideal for
              {' '}
              {STAGE_OPTIONS.find((s) => s.value === profile.business_stage)?.label.toLowerCase() ?? 'your'} stage.
            </p>
          </div>
          {knowledgeMapLoading ? (
            <p className="readar-profile-muted">Building your map…</p>
          ) : knowledgeMap ? (
            <FounderKnowledgeMap data={knowledgeMap} />
          ) : (
            <p className="readar-profile-muted">
              We couldn't build your map yet. Mark books as read or import your
              Goodreads history below.
            </p>
          )}
        </Card>

        {/* ── Currently reading ───────────────────────────────────────── */}
        {currentlyReading.length > 0 && (
          <Card variant="flat" className="readar-profile-section">
            <div className="readar-profile-section-head">
              <h2 className="readar-profile-section-title" style={{ border: 'none', marginBottom: 0, paddingBottom: 0 }}>
                <BookOpen size={18} strokeWidth={2} style={{ marginRight: '0.45rem', verticalAlign: 'text-bottom' }} />
                Currently reading
              </h2>
              <button className="readar-link-button" onClick={() => navigate('/shelves')}>
                Manage in Shelves →
              </button>
            </div>
            <ul className="readar-reading-now-list" style={{ marginTop: '1rem' }}>
              {currentlyReading.map((item) => (
                <li
                  key={item.book_id}
                  className="readar-reading-now-item"
                  onClick={() => navigate(`/book/${item.book_id}`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/book/${item.book_id}`); }}
                >
                  <div className="readar-reading-now-info">
                    {item.title ? (
                      <>
                        <strong>{item.title}</strong>
                        {item.author_name && <span className="readar-profile-muted"> by {item.author_name}</span>}
                      </>
                    ) : (
                      <span className="readar-profile-muted">{item.book_id}</span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {/* ── Your focus (editable, high-signal) ──────────────────────── */}
        <Card variant="flat" className="readar-profile-section">
          <div className="readar-profile-section-head">
            <h2 className="readar-profile-section-title" style={{ border: 'none', marginBottom: 0, paddingBottom: 0 }}>
              Your focus
            </h2>
            {!editingFocus && (
              <button className="readar-link-button" onClick={startEditFocus}>Edit</button>
            )}
          </div>
          <p className="readar-profile-help">These directly shape the books Readar recommends.</p>

          {editingFocus ? (
            <div className="readar-focus-form">
              <label className="readar-field">
                <span className="readar-field-label">Biggest challenge</span>
                <textarea
                  className="readar-textarea"
                  value={focusDraft.biggest_challenge}
                  onChange={(e) => setFocusDraft({ ...focusDraft, biggest_challenge: e.target.value })}
                  rows={3}
                />
              </label>
              <label className="readar-field">
                <span className="readar-field-label">Business stage</span>
                <select
                  className="readar-select"
                  value={focusDraft.business_stage}
                  onChange={(e) => setFocusDraft({ ...focusDraft, business_stage: e.target.value as OnboardingProfile['business_stage'] })}
                >
                  {STAGE_OPTIONS.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </label>
              <label className="readar-field">
                <span className="readar-field-label">Vision (6–12 months)</span>
                <textarea
                  className="readar-textarea"
                  value={focusDraft.vision_6_12_months}
                  onChange={(e) => setFocusDraft({ ...focusDraft, vision_6_12_months: e.target.value })}
                  rows={3}
                />
              </label>
              {focusError && <p className="readar-field-error">{focusError}</p>}
              <div className="readar-focus-actions">
                <Button variant="primary" size="sm" onClick={saveFocus} disabled={savingFocus} delayMs={0}>
                  {savingFocus ? 'Saving…' : 'Save'}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setEditingFocus(false)} disabled={savingFocus}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <>
              <div className="readar-profile-field">
                <strong>Biggest Challenge:</strong>
                <p>{profile.biggest_challenge}</p>
              </div>
              <div className="readar-profile-field">
                <strong>Business Stage:</strong>{' '}
                <Badge variant="purple" size="sm">
                  {STAGE_OPTIONS.find((s) => s.value === profile.business_stage)?.label ?? profile.business_stage}
                </Badge>
              </div>
              {profile.vision_6_12_months && (
                <div className="readar-profile-field">
                  <strong>Vision (6–12 months):</strong>
                  <p>{profile.vision_6_12_months}</p>
                </div>
              )}
              {profile.blockers && (
                <div className="readar-profile-field">
                  <strong>Blockers:</strong>
                  <p>{profile.blockers}</p>
                </div>
              )}
            </>
          )}
        </Card>

        {/* ── Reading History (stats + DNA tags + import) ──────────────── */}
        <Card variant="flat" className="readar-profile-section">
          <h2 className="readar-profile-section-title">Reading History</h2>
          {readingProfile ? (
            <div>
              <div className="readar-reading-instruments">
                <SegmentReadout value={readingProfile.total_books_read} label="Books read" />
                {readingProfile.avg_rating != null && (
                  <SegmentReadout value={readingProfile.avg_rating.toFixed(1)} label="Avg rating" />
                )}
                <Gauge
                  value={Math.round(readingProfile.reading_confidence * 100)}
                  max={100}
                  displayValue={`${Math.round(readingProfile.reading_confidence * 100)}%`}
                  label="Confidence"
                  size={150}
                />
              </div>
              <p className="readar-stat-caption">
                {readingProfile.reading_confidence >= 0.7
                  ? 'Readar has a strong read on your taste — recommendations are well-tuned.'
                  : 'Log or import a few more books to sharpen how well recommendations fit you.'}
              </p>
              {readingProfile.profile_summary && (
                <p className="readar-reading-summary">{readingProfile.profile_summary}</p>
              )}
              {readingProfile.structured_tags && Object.keys(readingProfile.structured_tags).length > 0 && (
                <div className="readar-profile-tags" style={{ marginBottom: '1rem' }}>
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
            <p className="readar-profile-muted" style={{ marginBottom: '0.75rem' }}>
              No reading history imported yet. Upload a Goodreads CSV to personalise
              your recommendations and build your knowledge map.
            </p>
          )}

          <div className="readar-csv-row">
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
              {uploadingCsv ? 'Uploading...' : readingProfile ? 'Update Goodreads history' : 'Import Goodreads history'}
            </Button>
            {csvMessage && <span className="readar-csv-success">{csvMessage}</span>}
            {csvError && <span className="readar-csv-error">{csvError}</span>}
          </div>
        </Card>

        {/* ── Book Activity (tabbed, condensed) ───────────────────────── */}
        <Card variant="flat" className="readar-profile-section">
          <h2 className="readar-profile-section-title">Book Activity</h2>
          <div className="readar-activity-tabs">
            {ACTIVITY_TABS.map((t) => (
              <button
                key={t.key}
                className={`readar-activity-tab${activityTab === t.key ? ' readar-activity-tab--active' : ''}`}
                onClick={() => setActivityTab(t.key)}
              >
                {t.label}
                <span className="readar-activity-count">{bookStatuses[t.key].length}</span>
              </button>
            ))}
          </div>
          <div className="readar-activity-body">
            {loadingBookStatuses ? (
              <p className="readar-profile-muted">Loading...</p>
            ) : activeList.length === 0 ? (
              <p className="readar-profile-muted">No books here yet.</p>
            ) : (
              <ul className="readar-activity-list">
                {activeList.map((item) => (
                  <li key={item.book_id} className="readar-activity-item">
                    {item.title ? (
                      <>
                        <strong>{item.title}</strong>
                        {item.author_name && <span className="readar-profile-muted"> by {item.author_name}</span>}
                      </>
                    ) : (
                      <span className="readar-profile-muted">{item.book_id}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>

        {/* ── Account & settings ──────────────────────────────────────── */}
        <Card variant="flat" className="readar-profile-section">
          <h2 className="readar-profile-section-title">
            <Settings size={18} strokeWidth={2} style={{ marginRight: '0.45rem', verticalAlign: 'text-bottom' }} />
            Account &amp; settings
          </h2>
          {user?.email && (
            <p className="readar-profile-muted" style={{ marginBottom: '1.25rem' }}>
              Signed in as {user.email}
              {user.subscription_status === 'active' && (
                <Badge variant="warm" size="sm" style={{ marginLeft: '0.5rem' }}>Premium</Badge>
              )}
            </p>
          )}
          <div className="readar-account-grid">
            <div className="readar-profile-field"><strong>Name:</strong> {profile.full_name}</div>
            {profile.occupation && <div className="readar-profile-field"><strong>Occupation:</strong> {profile.occupation}</div>}
            {profile.location && <div className="readar-profile-field"><strong>Location:</strong> {profile.location}</div>}
            {profile.industry && <div className="readar-profile-field"><strong>Industry:</strong> {profile.industry}</div>}
            {profile.business_model && <div className="readar-profile-field"><strong>Business Model:</strong> {profile.business_model}</div>}
            {profile.org_size && <div className="readar-profile-field"><strong>Organization Size:</strong> {profile.org_size}</div>}
            {profile.business_experience && <div className="readar-profile-field"><strong>Experience:</strong> {profile.business_experience}</div>}
          </div>
          {profile.areas_of_business && profile.areas_of_business.length > 0 && (
            <div className="readar-profile-tags" style={{ marginTop: '1rem' }}>
              {profile.areas_of_business.map((area) => (
                <Badge key={area} variant="primary" size="md">{area}</Badge>
              ))}
            </div>
          )}
          {notifPrefs && (
            <div className="readar-notif-block">
              <h3 className="readar-notif-title">Email notifications</h3>
              <p className="readar-profile-muted" style={{ marginBottom: '1rem' }}>
                Sent to {user?.email ?? 'your account email'}.
              </p>
              {([
                {
                  key: 'notify_email_recommendations' as const,
                  label: 'New recommendations',
                  desc: 'Email me when fresh book recommendations are ready.',
                },
                {
                  key: 'notify_email_learning_tips' as const,
                  label: 'Learning tips',
                  desc: 'Tips from the book you’re reading, tied to your current bottleneck.',
                },
                {
                  key: 'notify_email_product' as const,
                  label: 'Product updates',
                  desc: 'Occasional news about new Readar features.',
                },
              ]).map((row) => (
                <label key={row.key} className="readar-notif-row">
                  <div className="readar-notif-text">
                    <span className="readar-notif-label">{row.label}</span>
                    <span className="readar-notif-desc">{row.desc}</span>
                  </div>
                  <input
                    type="checkbox"
                    className="readar-notif-toggle"
                    checked={notifPrefs[row.key]}
                    disabled={savingNotifKey === row.key}
                    onChange={() => toggleNotif(row.key)}
                  />
                </label>
              ))}
            </div>
          )}

          <div className="readar-account-foot readar-account-actions">
            {user?.subscription_status === 'free' && (
              <Button variant="secondary" size="sm" onClick={() => navigate('/upgrade')} delayMs={0}>
                <Zap size={16} strokeWidth={2} style={{ marginRight: '0.35rem', verticalAlign: 'text-bottom' }} />
                Upgrade to Premium
              </Button>
            )}
            <button className="readar-link-button" onClick={() => navigate('/onboarding')}>
              Re-run full onboarding
            </button>
            <button className="readar-link-button readar-link-button--danger" onClick={handleLogout}>
              <LogOut size={15} strokeWidth={2} style={{ marginRight: '0.3rem', verticalAlign: 'text-bottom' }} />
              Log out
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
}
