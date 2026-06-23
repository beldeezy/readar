import { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import readarLogo from '../assets/readar-logo.png';
import './store.css';

const DISCLOSURE = 'As an Amazon Associate, Readar earns from qualifying purchases.';

/** Shared chrome for the temporary prop store (self-contained — no app nav/login). */
export default function StoreLayout({ children }: { children: ReactNode }) {
  return (
    <div className="store-root">
      <header className="store-header">
        <div className="store-container store-header-inner">
          <Link to="/store" className="store-brand">
            <img src={readarLogo} alt="Readar" />
            <span className="store-brand-name">readar</span>
          </Link>
          <span className="store-brand-tag">Reads for builders</span>
        </div>
      </header>

      {children}

      <footer className="store-footer">
        <div className="store-container">
          <div className="store-footer-links">
            <Link to="/store">Store</Link>
            <Link to="/about">About</Link>
            <Link to="/privacy">Privacy</Link>
          </div>
          <p>{DISCLOSURE}</p>
          <p>© {new Date().getFullYear()} Readar. Prices and availability are set on Amazon and may change.</p>
        </div>
      </footer>
    </div>
  );
}

export { DISCLOSURE };
