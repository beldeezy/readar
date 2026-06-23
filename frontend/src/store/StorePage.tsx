import { useState } from 'react';
import { logEvent } from '../api/client';
import { PRODUCTS, amazonLink, coverUrl, type StoreProduct } from './products';
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
        {p.category && <div className="store-card-cat">{p.category}</div>}
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
  return (
    <StoreLayout>
      <section className="store-hero">
        <div className="store-container">
          <h1>Books that move builders forward</h1>
          <p>
            A short, hand-picked shelf for entrepreneurs — the reads we'd start with for
            building, selling, and scaling. Tap through to grab any of them on Amazon.
          </p>
          <p className="store-disclosure">{DISCLOSURE}</p>
        </div>
      </section>

      <main className="store-container">
        <div className="store-grid">
          {PRODUCTS.map((p) => (
            <ProductCard key={p.id} p={p} />
          ))}
        </div>
      </main>
    </StoreLayout>
  );
}
