import { Link, Outlet, useLocation } from 'react-router-dom';
import './Engine.css';

export default function Engine() {
  const { pathname } = useLocation();

  const engineNav = [
    { name: 'Insight Review', path: '/admin/engine/insight-review' },
  ];

  // If we're on a sub-route, show the sub-navigation and outlet
  if (pathname !== '/admin/engine') {
    return (
      <div className="readar-engine-page">
        <div className="readar-engine-nav">
          {engineNav.map(({ name, path }) => (
            <Link
              key={name}
              to={path}
              className={`readar-engine-nav-link ${
                pathname === path ? 'readar-engine-nav-link--active' : ''
              }`}
            >
              {name}
            </Link>
          ))}
        </div>
        <div className="readar-engine-content">
          <Outlet />
        </div>
      </div>
    );
  }

  // Default view when on /admin/engine
  return (
    <div>
      <h1 className="readar-admin-page-title">🧠 Engine Debug Tools</h1>
      <p className="readar-admin-page-subtitle">Engine debug tools coming soon...</p>
      <div className="readar-engine-quick-links">
        <h2>Quick Links</h2>
        <ul>
          {engineNav.map(({ name, path }) => (
            <li key={name}>
              <Link to={path}>{name}</Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

