import { useEffect, useState } from 'react';
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
  const navigate = useNavigate();

  useEffect(() => {
    loadProfile();
    loadBookStatuses();
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
            <p>No profile found. Please complete onboarding.</p>
            <Button variant="primary" onClick={handleReRunOnboarding} delayMs={140} className="readar-profile-action">
              Complete Onboarding
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

