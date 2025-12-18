import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import Badge from './Badge';
import Button from './Button';
import readarLogo from '../assets/readar-logo.png';
import './Header.css';

export default function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <header className="readar-header">
      <div className="readar-header-container container">
        <Link to="/" className="readar-logo-link">
          <img src={readarLogo} alt="Readar" className="readar-logo-icon" />
          <span className="readar-logo-text">readar</span>
        </Link>
        <nav className="readar-nav">
          {user ? (
            <>
              <Link to="/recommendations" className="readar-nav-link">Recommendations</Link>
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
            <Link to="/login">
              <Button variant="primary" size="sm">Get Started</Button>
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}

