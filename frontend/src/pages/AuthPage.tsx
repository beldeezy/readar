import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { apiClient } from '../api/client';
import { AUTH_DISABLED } from '../config/auth';
import Input from '../components/Input';
import Button from '../components/Button';
import Card from '../components/Card';
import './AuthPage.css';

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, signup, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const checkOnboardingAndNavigate = useCallback(async () => {
    try {
      // Check if user has completed onboarding
      await apiClient.getOnboarding();
      // If we get here, onboarding exists, go to recommendations
      navigate('/recommendations');
    } catch (err: any) {
      // If 404, onboarding doesn't exist, go to onboarding
      if (err.response?.status === 404) {
        navigate('/onboarding');
      } else {
        // Other error, still try onboarding
        navigate('/onboarding');
      }
    }
  }, [navigate]);

  // TEMP: Auto-redirect when auth is disabled
  useEffect(() => {
    if (AUTH_DISABLED) {
      checkOnboardingAndNavigate();
      return;
    }

    // Redirect if already authenticated
    if (isAuthenticated) {
      checkOnboardingAndNavigate();
    }
  }, [isAuthenticated, checkOnboardingAndNavigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isLogin) {
        await login(email, password);
      } else {
        await signup(email, password);
      }
      // After successful auth, check if onboarding exists
      await checkOnboardingAndNavigate();
    } catch (err: any) {
      // Extract error message from API response
      const errorMessage = err.response?.data?.detail || err.message || 'An error occurred';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // TEMP: Show message when auth is disabled
  if (AUTH_DISABLED) {
    return (
      <div className="readar-auth-page">
        <Card variant="elevated" className="readar-auth-card">
          <h1 className="readar-auth-title">Authentication Temporarily Disabled</h1>
          <p style={{ 
            textAlign: 'center', 
            color: 'var(--rd-muted)', 
            marginBottom: '2rem',
            lineHeight: '1.6'
          }}>
            Authentication is currently disabled while we prepare our infrastructure. 
            Continuing as a demo user...
          </p>
          <div style={{ textAlign: 'center' }}>
            <Button 
              variant="primary" 
              size="lg" 
              onClick={() => checkOnboardingAndNavigate()}
            >
              Continue to App
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="readar-auth-page">
      <Card variant="elevated" className="readar-auth-card">
        <h1 className="readar-auth-title">{isLogin ? 'Log In' : 'Sign Up'}</h1>
        <div className="readar-auth-tabs">
          <button
            className={`readar-auth-tab ${isLogin ? 'readar-auth-tab--active' : ''}`}
            onClick={() => setIsLogin(true)}
            type="button"
          >
            Log In
          </button>
          <button
            className={`readar-auth-tab ${!isLogin ? 'readar-auth-tab--active' : ''}`}
            onClick={() => setIsLogin(false)}
            type="button"
          >
            Sign Up
          </button>
        </div>
        <form onSubmit={handleSubmit} className="readar-auth-form">
          {error && <div className="readar-auth-error">{error}</div>}
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
          />
          <Button type="submit" disabled={loading} variant="primary" size="lg" className="readar-auth-submit">
            {loading ? 'Loading...' : isLogin ? 'Log In' : 'Sign Up'}
          </Button>
        </form>
      </Card>
    </div>
  );
}

