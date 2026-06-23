import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import Badge from './Badge';
import Button from './Button';
import readarLogo from '../assets/readar-logo.png';
import './Header.css';

// Immersive full-screen flows that own the whole viewport — hide the marketing header.
// Store routes are self-contained (own chrome), so the app header is hidden there too.
const IMMERSIVE_PATHS = ['/onboarding', '/onboarding/import', '/recommendations/loading', '/store', '/about', '/privacy'];

const SHOW_PROP_STORE = import.meta.env.VITE_PROP_STORE === 'true';

export default function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  if (IMMERSIVE_PATHS.includes(location.pathname)) {
    return null;
  }
  // When the prop store owns the homepage, it brings its own chrome.
  if (SHOW_PROP_STORE && location.pathname === '/') {
    return null;
  }

  return (
    <header className="readar-header">
      <div className="readar-header-container container">
        <Link to="/" className="readar-logo-link">
          <img src={readarLogo} alt="Readar" className="readar-logo-icon" />
          <span className="readar-logo-text">readar</span>
        </Link>
        <nav className={`readar-nav${user ? ' readar-nav--authenticated' : ''}`}>
          {user ? (
            <>
              <Link to="/recommendations" className="readar-nav-link">Recommendations</Link>
              <Link to="/library" className="readar-nav-link">Library</Link>
              <Link to="/reading" className="readar-nav-link">Reading</Link>
              <Link to="/profile" className="readar-nav-link">Profile</Link>
              {user.subscription_status === 'free' && (
                <Link to="/upgrade" className="readar-nav-link readar-nav-link--cta">Upgrade</Link>
              )}
              {user.subscription_status === 'active' && (
                <Badge variant="warm">Premium</Badge>
              )}
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                Logout
              </Button>
            </>
          ) : (
            <>
              <Link to="/login" className="readar-nav-link">Log In</Link>
              <Link to="/onboarding">
                <Button variant="primary" size="sm">Get Started</Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}

