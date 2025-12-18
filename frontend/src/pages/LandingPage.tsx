import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import Button from '../components/Button';
import RadarIcon from '../components/RadarIcon';
import Footer from '../components/Footer';
import './LandingPage.css';

export default function LandingPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const handleFindNextBook = async () => {
    if (user) {
      // If user is logged in, go to onboarding (which will redirect to recommendations if already complete)
      navigate('/onboarding');
    } else {
      // If not logged in, go to login
      navigate('/login');
    }
  };

  return (
    <div className="readar-landing">
      <div className="readar-hero">
        <div className="readar-hero-content">
          <h1 className="readar-hero-title">Know what to read next.</h1>
          <p className="readar-hero-subtitle">
            Built for entrepreneurs. Find the right book to eliminate blind spots and move your business forward.
          </p>
          <p className="readar-hero-microcopy">
            No noise — just the next book you actually need.
          </p>
          <Button variant="primary" size="lg" onClick={handleFindNextBook} delayMs={140} className="readar-hero-cta">
            Find my next book
          </Button>
          <div className="readar-hero-radar">
            <RadarIcon size={160} opacity={0.7} animationDuration={10} />
          </div>
        </div>
      </div>
      {/* 
        NOTE: Feature cards section intentionally removed for now.
        The three feature cards (Personalized Recommendations, Curated Catalog, 
        Track Your Reading) have been removed to simplify the landing page.
      */}
      <Footer />
    </div>
  );
}

