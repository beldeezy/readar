import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import Button from '../components/Button';
import Card from '../components/Card';
import Badge from '../components/Badge';
import './UpgradePage.css';

const STRIPE_PRICE_ID = import.meta.env.VITE_STRIPE_PRICE_ID || 'price_1234567890';

export default function UpgradePage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleUpgrade = async () => {
    if (!STRIPE_PRICE_ID || STRIPE_PRICE_ID === 'price_1234567890') {
      setError('Stripe price ID not configured. Please set VITE_STRIPE_PRICE_ID in your environment.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const successUrl = `${window.location.origin}/upgrade/success`;
      const cancelUrl = `${window.location.origin}/upgrade`;

      const response = await apiClient.createCheckoutSession(
        STRIPE_PRICE_ID,
        successUrl,
        cancelUrl
      );

      // Redirect to Stripe Checkout
      window.location.href = response.checkout_url;
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create checkout session');
      setLoading(false);
    }
  };

  if (user?.subscription_status === 'active') {
    return (
      <div className="readar-upgrade-page">
        <div className="container">
          <Card variant="elevated" className="readar-premium-card">
            <Badge variant="warm" size="md" className="readar-premium-badge">Premium</Badge>
            <h1 className="readar-premium-title">You're Premium!</h1>
            <p className="readar-premium-text">Thank you for your subscription. You have access to all premium features.</p>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="readar-upgrade-page">
      <div className="container">
        <h1 className="readar-upgrade-title">Upgrade to Premium</h1>
        <Card variant="elevated" className="readar-pricing-card">
          <h2 className="readar-pricing-title">Premium Features</h2>
          <ul className="readar-features-list">
            <li>✓ Unlimited book recommendations</li>
            <li>✓ Advanced filtering and search</li>
            <li>✓ Priority support</li>
            <li>✓ Early access to new features</li>
          </ul>
          <div className="readar-price">
            <span className="readar-price-amount">$9.99</span>
            <span className="readar-price-period">/month</span>
          </div>
          {error && (
            <Card variant="flat" className="readar-upgrade-error">
              {error}
            </Card>
          )}
          <Button
            variant="primary"
            size="lg"
            onClick={handleUpgrade}
            disabled={loading}
            className="readar-upgrade-button"
          >
            {loading ? 'Processing...' : 'Upgrade to Premium'}
          </Button>
        </Card>
      </div>
    </div>
  );
}

