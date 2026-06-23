import { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { logEvent } from '../api/client';
import { PRODUCTS, amazonLink, coverUrl, productsByCategory, type StoreProduct } from './products';
import StoreLayout, { DISCLOSURE } from './StoreLayout';
import './store.css';

function ProductCard({ p }: { p: StoreProduct }) {
  const [imgOk, setImgOk] = useState(true);
  const src = coverUrl(p);

  const onBuy = () => {
    // Best-effort outbound tracking (anonymous) so we can see which titles convert.
    logEvent('affiliate_click', { product_id: p.id, title: p.title, asin: p.asin ?? null });
  };

  return (
    <div className="store-card">
      {src && imgOk ? (
        <img
          className="store-cover"
          src={src}
          alt={`${p.title} cover`}
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setImgOk(false)}
        />
      ) : (
        <div className="store-cover-fallback">{p.title}</div>
      )}

      <div className="store-card-body">
        <div className="store-card-cat">{p.category}</div>
        <h3 className="store-card-title">{p.title}</h3>
        <div className="store-card-author">by {p.author}</div>
        <p className="store-card-blurb">{p.blurb}</p>
        <a
          className="store-buy"
          href={amazonLink(p)}
          target="_blank"
          rel="nofollow noopener noreferrer sponsored"
          onClick={onBuy}
        >
          View on Amazon →
        </a>
      </div>
    </div>
  );
}

export default function StorePage() {
  const [query, setQuery] = useState('');
  const q = query.trim().toLowerCase();

  const matches = useMemo(() => {
    if (!q) return PRODUCTS;
    return PRODUCTS.filter((p) =>
      `${p.title} ${p.author} ${p.category} ${p.blurb}`.toLowerCase().includes(q),
    );
  }, [q]);

  const groups = useMemo(() => productsByCategory(matches), [matches]);

  return (
    <StoreLayout>
      <section className="store-hero">
        <div className="store-container">
          <h1>Books that move builders forward</h1>
          <p>
            Hand-picked reads for entrepreneurs, grouped by where you are — from finding the
            idea to scaling the team. Tap through to grab any of them on Amazon.
          </p>
          <p className="store-disclosure">{DISCLOSURE}</p>

          <div className="store-search">
            <Search size={18} className="store-search-icon" aria-hidden />
            <input
              className="store-search-input"
              type="search"
              placeholder="Search by title, author, or topic…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search books"
            />
          </div>
        </div>
      </section>

      <main className="store-container">
        {groups.length === 0 ? (
          <p className="store-empty">No books match “{query}”. Try a different search.</p>
        ) : (
          groups.map((group) => (
            <section key={group.category} className="store-section">
              <h2 className="store-section-title">{group.category}</h2>
              <div className="store-grid">
                {group.items.map((p) => (
                  <ProductCard key={p.id} p={p} />
                ))}
              </div>
            </section>
          ))
        )}
      </main>
    </StoreLayout>
  );
}
