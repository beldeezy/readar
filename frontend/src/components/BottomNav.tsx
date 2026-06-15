import { useState, useRef, useEffect } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { BookOpen, Library, BookMarked, User, MoreHorizontal, LogOut, Zap } from 'lucide-react';
import { useAuth } from '../auth/AuthProvider';
import './BottomNav.css';

// Routes where the bottom nav should NOT appear
const EXCLUDED_PATHS = ['/', '/login', '/auth/callback', '/onboarding', '/onboarding/import', '/recommendations/loading'];

export default function BottomNav() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  // Hide on excluded paths, admin routes, or when not authenticated
  const isExcluded =
    EXCLUDED_PATHS.includes(location.pathname) ||
    location.pathname.startsWith('/admin');

  if (!isAuthenticated || isExcluded) return null;

  const handleLogout = () => {
    setMoreOpen(false);
    logout();
    navigate('/');
  };

  const handleUpgrade = () => {
    setMoreOpen(false);
    navigate('/upgrade');
  };

  // Close "More" sheet when clicking outside
  const handleMoreToggle = () => setMoreOpen(prev => !prev);

  return (
    <>
      {/* Backdrop to close More sheet */}
      {moreOpen && (
        <div className="bottom-nav-backdrop" onClick={() => setMoreOpen(false)} />
      )}

      <nav className="bottom-nav" role="navigation" aria-label="Mobile navigation">
        <NavLink
          to="/recommendations"
          className={({ isActive }) =>
            `bottom-nav-tab${isActive ? ' bottom-nav-tab--active' : ''}`
          }
          aria-label="Recommendations"
        >
          <BookOpen size={22} strokeWidth={1.75} />
          <span>Recs</span>
        </NavLink>

        <NavLink
          to="/library"
          className={({ isActive }) =>
            `bottom-nav-tab${isActive ? ' bottom-nav-tab--active' : ''}`
          }
          aria-label="Library"
        >
          <Library size={22} strokeWidth={1.75} />
          <span>Library</span>
        </NavLink>

        <NavLink
          to="/shelves"
          className={({ isActive }) =>
            `bottom-nav-tab${isActive ? ' bottom-nav-tab--active' : ''}`
          }
          aria-label="Shelves"
        >
          <BookMarked size={22} strokeWidth={1.75} />
          <span>Shelves</span>
        </NavLink>

        <NavLink
          to="/profile"
          className={({ isActive }) =>
            `bottom-nav-tab${isActive ? ' bottom-nav-tab--active' : ''}`
          }
          aria-label="Profile"
        >
          <User size={22} strokeWidth={1.75} />
          <span>Profile</span>
        </NavLink>

        <div className="bottom-nav-tab bottom-nav-tab--more" ref={moreRef}>
          <button
            className={`bottom-nav-more-btn${moreOpen ? ' bottom-nav-more-btn--open' : ''}`}
            onClick={handleMoreToggle}
            aria-label="More options"
            aria-expanded={moreOpen}
          >
            <MoreHorizontal size={22} strokeWidth={1.75} />
            <span>More</span>
          </button>

          {moreOpen && (
            <div className="bottom-nav-more-sheet" role="menu">
              {user?.subscription_status === 'free' && (
                <button
                  className="bottom-nav-more-item bottom-nav-more-item--upgrade"
                  onClick={handleUpgrade}
                  role="menuitem"
                >
                  <Zap size={18} strokeWidth={1.75} />
                  <span>Upgrade to Premium</span>
                </button>
              )}
              <button
                className="bottom-nav-more-item bottom-nav-more-item--logout"
                onClick={handleLogout}
                role="menuitem"
              >
                <LogOut size={18} strokeWidth={1.75} />
                <span>Log out</span>
              </button>
            </div>
          )}
        </div>
      </nav>
    </>
  );
}
