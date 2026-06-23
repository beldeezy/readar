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
  /** Stage category — drives the on-site grouping. Must be one of CATEGORIES. */
  category: Category;
}

// Stage-based categories, in display order.
export const CATEGORIES = [
  'Idea & Validation',
  'Getting to Revenue',
  'Growth & Marketing',
  'Scaling & Leadership',
  'Mindset & Discipline',
] as const;
export type Category = (typeof CATEGORIES)[number];

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

/** Group products by category in CATEGORIES order (skips empty categories). */
export function productsByCategory(items: StoreProduct[]): { category: Category; items: StoreProduct[] }[] {
  return CATEGORIES.map((category) => ({
    category,
    items: items.filter((p) => p.category === category),
  })).filter((g) => g.items.length > 0);
}

// Draft picks across stages — placeholder copy for review. The founder's
// hand-selected, higher-intent titles (with exact ASINs) get added/edited here.
export const PRODUCTS: StoreProduct[] = [
  // ── Idea & Validation ──────────────────────────────────────────────
  {
    id: 'lean-startup', title: 'The Lean Startup', author: 'Eric Ries', isbn: '9780307887894',
    category: 'Idea & Validation',
    blurb: 'Build through fast, cheap experiments instead of guesswork — find what customers want before you run out of runway.',
  },
  {
    id: 'mom-test', title: 'The Mom Test', author: 'Rob Fitzpatrick', isbn: '9781492180746',
    category: 'Idea & Validation',
    blurb: 'How to talk to customers so they tell you the truth — the cheapest way to avoid building something nobody buys.',
  },
  {
    id: 'running-lean', title: 'Running Lean', author: 'Ash Maurya', isbn: '9781449305178',
    category: 'Idea & Validation',
    blurb: 'A step-by-step system for stress-testing your idea and finding a business model that actually works.',
  },
  {
    id: 'zero-to-one', title: 'Zero to One', author: 'Peter Thiel', isbn: '9780804139298',
    category: 'Idea & Validation',
    blurb: "Thiel's case for building something genuinely new instead of copying what already works.",
  },

  // ── Getting to Revenue ─────────────────────────────────────────────
  {
    id: '100m-offers', title: '$100M Offers', author: 'Alex Hormozi',
    category: 'Getting to Revenue',
    blurb: 'Build an offer so good people feel stupid saying no — pricing, value-stacking, and positioning for first revenue.',
  },
  {
    id: 'predictable-revenue', title: 'Predictable Revenue', author: 'Aaron Ross & Marylou Tyler', isbn: '9780984380244',
    category: 'Getting to Revenue',
    blurb: 'The outbound playbook behind a repeatable sales pipeline — how to stop relying on referrals and luck.',
  },
  {
    id: 'spin-selling', title: 'SPIN Selling', author: 'Neil Rackham', isbn: '9780070511132',
    category: 'Getting to Revenue',
    blurb: 'The research-backed questioning method for closing larger, more complex sales without being pushy.',
  },
  {
    id: '1page-marketing', title: 'The 1-Page Marketing Plan', author: 'Allan Dib',
    category: 'Getting to Revenue',
    blurb: 'A no-nonsense marketing framework you can fit on a single page and actually execute as a small team.',
  },

  // ── Growth & Marketing ─────────────────────────────────────────────
  {
    id: 'traction', title: 'Traction', author: 'Gabriel Weinberg & Justin Mares', isbn: '9781591848363',
    category: 'Growth & Marketing',
    blurb: 'A systematic way to find the few marketing channels that will actually move your growth needle.',
  },
  {
    id: 'storybrand', title: 'Building a StoryBrand', author: 'Donald Miller', isbn: '9780718033323',
    category: 'Growth & Marketing',
    blurb: 'Clarify your message so customers instantly get why you matter — make them the hero, not your product.',
  },
  {
    id: 'hooked', title: 'Hooked', author: 'Nir Eyal', isbn: '9781591847786',
    category: 'Growth & Marketing',
    blurb: 'The psychology of habit-forming products — how to design something people come back to on their own.',
  },
  {
    id: 'influence', title: 'Influence', author: 'Robert B. Cialdini', isbn: '9780061241895',
    category: 'Growth & Marketing',
    blurb: 'The six principles of persuasion every founder should understand for marketing, sales, and hiring.',
  },

  // ── Scaling & Leadership ───────────────────────────────────────────
  {
    id: 'emyth-revisited', title: 'The E-Myth Revisited', author: 'Michael E. Gerber', isbn: '9780887307287',
    category: 'Scaling & Leadership',
    blurb: 'Stop being trapped doing the work — a blueprint for building systems so the business runs without you.',
  },
  {
    id: 'scaling-up', title: 'Scaling Up', author: 'Verne Harnish', isbn: '9780986019524',
    category: 'Scaling & Leadership',
    blurb: 'A practical operating system (people, strategy, execution, cash) for growing past the founder bottleneck.',
  },
  {
    id: 'hard-thing', title: 'The Hard Thing About Hard Things', author: 'Ben Horowitz', isbn: '9780062273208',
    category: 'Scaling & Leadership',
    blurb: 'Brutally honest lessons on the decisions no one prepares you for once you have a team and customers.',
  },
  {
    id: 'high-output', title: 'High Output Management', author: 'Andrew S. Grove', isbn: '9780679762881',
    category: 'Scaling & Leadership',
    blurb: "Intel legend Andy Grove's enduring manual for running teams that consistently ship results.",
  },

  // ── Mindset & Discipline ───────────────────────────────────────────
  {
    id: 'atomic-habits', title: 'Atomic Habits', author: 'James Clear', isbn: '9780735211292',
    category: 'Mindset & Discipline',
    blurb: 'The operating system for founder discipline — small, compounding routines that determine whether goals happen.',
  },
  {
    id: 'deep-work', title: 'Deep Work', author: 'Cal Newport', isbn: '9781455586691',
    category: 'Mindset & Discipline',
    blurb: 'How to do the focused, high-value work that actually moves a business in a world built to distract you.',
  },
  {
    id: 'obstacle-is-the-way', title: 'The Obstacle Is the Way', author: 'Ryan Holiday', isbn: '9781591846352',
    category: 'Mindset & Discipline',
    blurb: 'A stoic playbook for turning setbacks into fuel — essential mental armor for the founder rollercoaster.',
  },
];
