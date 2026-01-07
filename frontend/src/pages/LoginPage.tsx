import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { supabase } from '../auth/supabaseClient';
import PrimaryButton from '../components/PrimaryButton';
import Card from '../components/Card';
import './AuthPage.css';

export default function LoginPage() {
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [searchParams] = useSearchParams();

  const handleGoogleSignIn = async () => {
    setError('');
    setLoading(true);

    try {
      const origin = window.location.origin;
      const next = searchParams.get('next') || '/onboarding';
      const callbackUrl = `${origin}/auth/callback?next=${encodeURIComponent(next)}`;

      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: callbackUrl,
        },
      });

      if (error) {
        setError(error.message);
        setLoading(false);
      }
      // Don't set loading false on success - page will redirect to Google
    } catch (err: any) {
      setError(err.message || 'An error occurred');
      setLoading(false);
    }
  };

  return (
    <div className="readar-auth-page">
      <Card variant="elevated" className="readar-auth-card">
        <h1 className="readar-auth-title">Sign in to Readar</h1>

        {error && (
          <div className="readar-auth-error" style={{ marginBottom: '1.5rem' }}>
            {error}
          </div>
        )}

        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          width: '100%',
        }}>
          <div style={{ maxWidth: '420px', width: '100%' }}>
            <PrimaryButton
              onClick={handleGoogleSignIn}
              isDisabled={loading}
              className="readar-auth-google-button"
              style={{
                width: '100%',
                backgroundColor: '#fff',
                color: '#000',
                border: '1px solid #ddd',
                padding: '0.75rem 1.5rem',
                fontSize: '1rem',
              }}
            >
              {loading ? 'Redirecting...' : '🔐 Continue with Google'}
            </PrimaryButton>
          </div>
        </div>
      </Card>
    </div>
  );
}
