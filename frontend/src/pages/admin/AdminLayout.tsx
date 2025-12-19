import { Link, Outlet, useLocation } from 'react-router-dom';
import './AdminLayout.css';

export default function AdminLayout() {
  const { pathname } = useLocation();

  const nav = [
    { name: 'Books', path: '/admin/books' },
    { name: 'Users', path: '/admin/users' },
    { name: 'Engine Debug', path: '/admin/engine' },
    { name: 'Recs Debug', path: '/admin/recommendations-debug' },
  ];

  return (
    <div className="readar-admin-layout">
      <aside className="readar-admin-sidebar">
        <h2 className="readar-admin-sidebar-title">Admin</h2>
        <nav className="readar-admin-nav">
          {nav.map(({ name, path }) => (
            <Link
              key={name}
              to={path}
              className={`readar-admin-nav-link ${
                pathname === path || pathname.startsWith(path + '/')
                  ? 'readar-admin-nav-link--active'
                  : ''
              }`}
            >
              {name}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="readar-admin-main">
        <Outlet />
      </main>
    </div>
  );
}

