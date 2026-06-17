/**
 * Flat, geometric brand illustrations (no gradients, brand palette via CSS vars).
 * Silhouette-first and semantically simple — per the visual-language report
 * (Gumroad/Canva/Formfrom: illustrations explain, they don't perform).
 */

interface ArtProps {
  size?: number;
  className?: string;
}

/** Radar scope with no blips — "scanning, nothing found yet." */
export function RadarScopeArt({ size = 132, className }: ArtProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 132 132" className={className} role="img" aria-label="Radar scope">
      <circle cx="66" cy="66" r="60" fill="var(--rd-surface)" stroke="var(--rd-border-strong)" strokeWidth="2" />
      <circle cx="66" cy="66" r="42" fill="none" stroke="var(--rd-border)" strokeWidth="2" />
      <circle cx="66" cy="66" r="22" fill="none" stroke="var(--rd-border)" strokeWidth="2" />
      {/* crosshair */}
      <line x1="66" y1="8" x2="66" y2="124" stroke="var(--rd-border)" strokeWidth="1.5" />
      <line x1="8" y1="66" x2="124" y2="66" stroke="var(--rd-border)" strokeWidth="1.5" />
      {/* sweep wedge */}
      <path d="M66 66 L66 8 A60 60 0 0 1 117 95 Z" fill="var(--rd-accent-soft)" />
      <line x1="66" y1="66" x2="117" y2="95" stroke="var(--rd-accent)" strokeWidth="2.5" strokeLinecap="round" />
      {/* center */}
      <circle cx="66" cy="66" r="4" fill="var(--rd-accent)" />
    </svg>
  );
}

/** A near-empty shelf with one lone book — for empty shelves. */
export function EmptyShelfArt({ size = 132, className }: ArtProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 132 132" className={className} role="img" aria-label="Empty shelf">
      {/* shelf */}
      <rect x="18" y="92" width="96" height="6" rx="2" fill="var(--rd-border-strong)" />
      {/* a couple of book outlines (empty slots) */}
      <rect x="30" y="58" width="14" height="34" rx="2" fill="none" stroke="var(--rd-border-strong)" strokeWidth="2" strokeDasharray="4 4" />
      <rect x="48" y="58" width="14" height="34" rx="2" fill="none" stroke="var(--rd-border-strong)" strokeWidth="2" strokeDasharray="4 4" />
      {/* one real book (accent) */}
      <rect x="70" y="46" width="18" height="46" rx="2" fill="var(--rd-accent-soft)" stroke="var(--rd-accent)" strokeWidth="2" />
      <line x1="74" y1="54" x2="84" y2="54" stroke="var(--rd-accent)" strokeWidth="2" strokeLinecap="round" />
      <rect x="92" y="58" width="14" height="34" rx="2" fill="none" stroke="var(--rd-border-strong)" strokeWidth="2" strokeDasharray="4 4" />
    </svg>
  );
}

/** An open book with a signal mark — for "no recommendations / picks" states. */
export function BookSignalArt({ size = 132, className }: ArtProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 132 132" className={className} role="img" aria-label="Book with signal">
      {/* open book */}
      <path d="M66 40 C54 32 36 32 24 38 L24 96 C36 90 54 90 66 98 Z" fill="var(--rd-surface)" stroke="var(--rd-border-strong)" strokeWidth="2" />
      <path d="M66 40 C78 32 96 32 108 38 L108 96 C96 90 78 90 66 98 Z" fill="var(--rd-surface)" stroke="var(--rd-border-strong)" strokeWidth="2" />
      <line x1="66" y1="40" x2="66" y2="98" stroke="var(--rd-border)" strokeWidth="2" />
      {/* signal arcs */}
      <path d="M88 30 A14 14 0 0 1 100 44" fill="none" stroke="var(--rd-accent)" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M84 22 A24 24 0 0 1 106 48" fill="none" stroke="var(--rd-accent)" strokeWidth="2.5" strokeLinecap="round" opacity="0.6" />
      <circle cx="84" cy="48" r="3.5" fill="var(--rd-accent)" />
    </svg>
  );
}
