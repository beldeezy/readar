import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { supabase } from '../auth/supabaseClient';
import Input from '../components/Input';
import PrimaryButton from '../components/PrimaryButton';
import Card from '../components/Card';
import './AuthPage.css';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const handleGoogleSignIn = async () => {
    setError('');
    setLoading(true);

    try {
      const origin = window.location.origin;
      const next = searchParams.get('next') || '/recommendations';
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess(false);
    setLoading(true);

    try {
      const origin = window.location.origin;
      const next = searchParams.get('next') || '/recommendations';
      const callbackUrl = `${origin}/auth/callback?next=${encodeURIComponent(next)}`;

      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: callbackUrl,
        },
      });

      if (error) {
        setError(error.message);
      } else {
        setSuccess(true);
      }
    } catch (err: any) {
      setError(err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="readar-auth-page">
      <Card variant="elevated" className="readar-auth-card">
        <h1 className="readar-auth-title">Sign in to Readar</h1>
        {success ? (
          <div style={{ textAlign: 'center', padding: '2rem 0' }}>
            <p style={{ color: 'var(--rd-success, #10b981)', marginBottom: '1rem', fontSize: '1rem' }}>
              Check your email for the magic link
            </p>
            <p style={{ color: 'var(--rd-muted)', fontSize: '0.875rem', marginBottom: '2rem' }}>
              Click the link in the email to sign in. You can close this page.
            </p>
            <PrimaryButton onClick={() => setSuccess(false)}>
              Send another link
            </PrimaryButton>
          </div>
        ) : (
          <>
            {error && <div className="readar-auth-error">{error}</div>}

            {/* Google Sign In */}
            <PrimaryButton
              onClick={handleGoogleSignIn}
              isDisabled={loading}
              className="readar-auth-google-button"
              style={{
                marginBottom: '1.5rem',
                backgroundColor: '#fff',
                color: '#000',
                border: '1px solid #ddd',
              }}
            >
              {loading ? 'Redirecting...' : '🔐 Continue with Google'}
            </PrimaryButton>

            {/* Divider */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              margin: '1.5rem 0',
              color: 'var(--rd-muted)',
              fontSize: '0.875rem',
            }}>
              <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--rd-border)' }} />
              <span>or</span>
              <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--rd-border)' }} />
            </div>

            {/* Email Magic Link Form */}
            <form onSubmit={handleSubmit} className="readar-auth-form">
              <Input
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
              <PrimaryButton type="submit" isDisabled={loading} className="readar-auth-submit">
                {loading ? 'Sending...' : 'Send magic link'}
              </PrimaryButton>
            </form>
          </>
        )}
      </Card>
    </div>
  );
}





