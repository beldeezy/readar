// Temporary "prop store" data layer (throwaway — removed once Amazon PA API is granted).
//
// Affiliate tag comes from VITE_AMAZON_ASSOC_TAG (set in Vercel once the new
// Associates account is live). Until then a placeholder is used; unknown tags are
// simply ignored by Amazon, so preview links are harmless.
//
// NOTE: pre-PA-API we may NOT use Amazon's product images. Covers here come from
// Open Library (by ISBN) and degrade to a clean text card if missing.

export interface StoreProduct {
  id: string;
  title: string;
  author: string;
  /** Exact product (preferred). When absent we fall back to a tagged search link. */
  asin?: string;
  /** ISBN-13 used only to fetch an Open Library cover (never an Amazon image). */
  isbn?: string;
  blurb: string;
  category?: string;
}

const ASSOC_TAG = import.meta.env.VITE_AMAZON_ASSOC_TAG || 'readarstore-20';

/** Build a tagged Amazon link: a direct product link when we have an ASIN, else search. */
export function amazonLink(p: StoreProduct): string {
  if (p.asin) {
    return `https://www.amazon.com/dp/${p.asin}/?tag=${ASSOC_TAG}`;
  }
  const q = encodeURIComponent(`${p.title} ${p.author}`);
  return `https://www.amazon.com/s?k=${q}&tag=${ASSOC_TAG}`;
}

/** Open Library cover by ISBN (default=false => 404 when absent, so onError can fall back). */
export function coverUrl(p: StoreProduct): string | null {
  return p.isbn ? `https://covers.openlibrary.org/b/isbn/${p.isbn}-L.jpg?default=false` : null;
}

// Draft "general top picks" — placeholder copy for review. The founder's
// hand-selected, higher-intent titles (with exact ASINs) get added here later.
export const PRODUCTS: StoreProduct[] = [
  {
    id: 'lean-startup',
    title: 'The Lean Startup',
    author: 'Eric Ries',
    isbn: '9780307887894',
    category: 'Build',
    blurb:
      'The playbook for building a company through fast, cheap experiments instead of guesswork — how to find what customers actually want before you run out of runway.',
  },
  {
    id: 'zero-to-one',
    title: 'Zero to One',
    author: 'Peter Thiel',
    isbn: '9780804139298',
    category: 'Strategy',
    blurb:
      "Thiel's case for building something genuinely new instead of copying what already works — mental models for founders chasing a real edge, not a me-too product.",
  },
  {
    id: 'emyth-revisited',
    title: 'The E-Myth Revisited',
    author: 'Michael E. Gerber',
    isbn: '9780887307287',
    category: 'Systems',
    blurb:
      'Why most small businesses stall: the owner is trapped doing the work instead of building the system. A blueprint for working on your business, not just in it.',
  },
  {
    id: 'atomic-habits',
    title: 'Atomic Habits',
    author: 'James Clear',
    isbn: '9780735211292',
    category: 'Discipline',
    blurb:
      'The operating system for founder discipline — small, compounding routines that quietly determine whether your big goals actually happen.',
  },
  {
    id: '100m-offers',
    title: '$100M Offers',
    author: 'Alex Hormozi',
    category: 'Sales',
    blurb:
      'A direct, tactical guide to building an offer so good people feel stupid saying no — pricing, value-stacking, and positioning for early-stage revenue.',
  },
  {
    id: 'mom-test',
    title: 'The Mom Test',
    author: 'Rob Fitzpatrick',
    isbn: '9781492180746',
    category: 'Customers',
    blurb:
      'How to talk to customers so they tell you the truth, not what you want to hear — the cheapest way to avoid building something nobody buys.',
  },
];
