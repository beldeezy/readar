"""
Founder Knowledge Map service.

Maps a user's *read* books onto six entrepreneurial knowledge domains, scores
each domain on a 1-3 scale, and computes a stage-aware "ideal founder" target
vector that bends to the user's business stage and biggest challenge.

The score is intentionally a *reading-diet / blind-spot* signal, not a claim of
competence: it reflects where a founder has invested their reading, surfacing
over- and under-developed areas relative to where they are in their journey.

No schema changes required — scores are derived from existing
``Book.functional_tags`` / ``Book.theme_tags`` arrays at read time.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import (
    Book,
    OnboardingProfile,
    ReadingHistoryEntry,
    UserBookInteraction,
)

# ── The six domains (display order = hexagon spoke order, starting at top) ────
DOMAINS: List[Tuple[str, str]] = [
    ("mindset", "Mindset & Self"),
    ("strategy", "Strategy & Vision"),
    ("sales", "Sales & Marketing"),
    ("operations", "Operations & Systems"),
    ("finance", "Finance & Capital"),
    ("leadership", "Leadership & People"),
]
DOMAIN_KEYS: List[str] = [k for k, _ in DOMAINS]
DOMAIN_LABELS: Dict[str, str] = dict(DOMAINS)

# ── Deterministic mapping: existing functional_tags vocabulary → domain ───────
FUNCTIONAL_TO_DOMAIN: Dict[str, str] = {
    # Mindset & Self
    "productivity": "mindset",
    # Strategy & Vision
    "strategy": "strategy",
    # Sales & Marketing
    "sales": "sales",
    "marketing": "sales",
    "client_acquisition": "sales",
    "growth": "sales",
    "plg": "sales",
    "negotiation": "sales",
    # Operations & Systems
    "operations": "operations",
    "service_delivery": "operations",
    "product": "operations",
    # Finance & Capital
    "finance": "finance",
    "fundraising": "finance",
    "pricing": "finance",
    "metrics": "finance",
    "analytics": "finance",
    # Leadership & People
    "leadership": "leadership",
    "hiring": "leadership",
    "culture": "leadership",
    "communication": "leadership",
}

# ── Free-form theme_tags → domain (substring match) ───────────────────────────
# Primarily fills the Mindset/Strategy axes that the functional vocabulary
# under-represents.
THEME_KEYWORD_TO_DOMAIN: Dict[str, str] = {
    "mindset": "mindset",
    "discipline": "mindset",
    "habit": "mindset",
    "self": "mindset",
    "psychology": "mindset",
    "emotional": "mindset",
    "confidence": "mindset",
    "resilience": "mindset",
    "focus": "mindset",
    "systems_thinking": "strategy",
    "decision_making": "strategy",
    "decision": "strategy",
    "vision": "strategy",
    "first_principles": "strategy",
    "mental_model": "strategy",
    "positioning": "strategy",
    "customer_discovery": "sales",
    "team_building": "leadership",
    "pricing_strategy": "finance",
}

# ── Stage-aware ideal target vectors (1-3 per domain) ─────────────────────────
STAGE_IDEAL: Dict[str, Dict[str, int]] = {
    "idea": {"mindset": 3, "strategy": 3, "sales": 3, "operations": 1, "finance": 1, "leadership": 1},
    "pre-revenue": {"mindset": 2, "strategy": 3, "sales": 3, "operations": 2, "finance": 1, "leadership": 1},
    "early-revenue": {"mindset": 2, "strategy": 2, "sales": 3, "operations": 3, "finance": 2, "leadership": 2},
    "scaling": {"mindset": 2, "strategy": 3, "sales": 2, "operations": 3, "finance": 3, "leadership": 3},
}
# Fallback when stage is unknown — a balanced mid-journey target.
DEFAULT_IDEAL: Dict[str, int] = STAGE_IDEAL["early-revenue"]

# ── biggest_challenge keyword → domain (for the +1 ideal nudge) ───────────────
CHALLENGE_KEYWORDS: Dict[str, List[str]] = {
    "mindset": ["focus", "burnout", "confidence", "procrastinat", "discipline",
                "motivat", "overwhelm", "mindset", "fear", "doubt", "imposter"],
    "strategy": ["strategy", "direction", "positioning", "vision", "decision",
                 "priorit", "clarity", "niche", "differentiat"],
    "sales": ["sales", "lead", "customer", "client", "marketing", "growth",
              "revenue", "acqui", "demand", "pipeline", "conversion", "audience"],
    "operations": ["operation", "system", "process", "deliver", "time", "scal",
                   "efficien", "workflow", "fulfil", "bottleneck"],
    "finance": ["cash", "runway", "financ", "pricing", "profit", "margin",
                "fund", "capital", "money", "invest", "unit econ"],
    "leadership": ["hire", "hiring", "team", "manage", "leadership", "culture",
                   "delegat", "people", "staff", "employee", "retention"],
}

# Per-book contribution: a focused (primary) domain hit counts fully; additional
# domains the book touches count at half. Disliked books count at half overall.
SECONDARY_WEIGHT = 0.5
DISLIKE_WEIGHT = 0.5


def _domains_for_book(book: Book) -> Dict[str, float]:
    """
    Return a per-domain weight contribution for a single book.

    Primary domain (the one its tags hit most) = 1.0; each additional domain
    touched = SECONDARY_WEIGHT.
    """
    hits: Dict[str, float] = {}

    for tag in (book.functional_tags or []):
        domain = FUNCTIONAL_TO_DOMAIN.get(str(tag).strip().lower())
        if domain:
            hits[domain] = hits.get(domain, 0.0) + 1.0

    for tag in (book.theme_tags or []):
        key = str(tag).strip().lower()
        for needle, domain in THEME_KEYWORD_TO_DOMAIN.items():
            if needle in key:
                hits[domain] = hits.get(domain, 0.0) + 0.5
                break

    if not hits:
        return {}

    primary = max(hits, key=hits.get)
    return {
        domain: (1.0 if domain == primary else SECONDARY_WEIGHT)
        for domain in hits
    }


def _collect_read_books(db: Session, user_id: UUID) -> Dict[UUID, Tuple[Book, float]]:
    """
    Gather the user's read books from both sources, keyed by catalog book id.

    Sources:
      - Goodreads ReadingHistoryEntry with shelf="read" and a matched catalog book
      - In-app UserBookInteraction with status read_liked / read_disliked

    Disliked books carry DISLIKE_WEIGHT. A book present in both sources is counted
    once (the stronger / liked signal wins).
    """
    collected: Dict[UUID, Tuple[Book, float]] = {}

    interactions = (
        db.query(UserBookInteraction)
        .filter(
            UserBookInteraction.user_id == user_id,
            UserBookInteraction.status.in_(["read_liked", "read_disliked"]),
        )
        .all()
    )
    for inter in interactions:
        if not inter.book_id:
            continue
        weight = DISLIKE_WEIGHT if inter.status == "read_disliked" else 1.0
        existing = collected.get(inter.book_id)
        if existing is None or weight > existing[1]:
            book = inter.book if getattr(inter, "book", None) else db.get(Book, inter.book_id)
            if book is not None:
                collected[inter.book_id] = (book, weight)

    goodreads = (
        db.query(ReadingHistoryEntry)
        .filter(
            ReadingHistoryEntry.user_id == user_id,
            ReadingHistoryEntry.shelf == "read",
            ReadingHistoryEntry.catalog_book_id.isnot(None),
        )
        .all()
    )
    for entry in goodreads:
        bid = entry.catalog_book_id
        if bid in collected:
            continue
        book = entry.catalog_book if getattr(entry, "catalog_book", None) else db.get(Book, bid)
        if book is not None:
            collected[bid] = (book, 1.0)

    return collected


def _bucket(raw: float) -> int:
    """Convert an accumulated raw domain weight into a 0-3 level."""
    if raw <= 0:
        return 0
    if raw < 3:
        return 1
    if raw < 6:
        return 2
    return 3


def _compute_ideal(profile: Optional[OnboardingProfile]) -> Dict[str, int]:
    """Stage-aware target vector, nudged +1 by the user's biggest challenge."""
    stage = None
    challenge = ""
    if profile is not None:
        stage = profile.business_stage.value if hasattr(profile.business_stage, "value") else profile.business_stage
        challenge = (profile.biggest_challenge or "").lower()

    ideal = dict(STAGE_IDEAL.get(stage, DEFAULT_IDEAL))

    if challenge:
        for domain, needles in CHALLENGE_KEYWORDS.items():
            if any(n in challenge for n in needles):
                ideal[domain] = min(3, ideal[domain] + 1)

    return ideal


def compute_knowledge_map(db: Session, user) -> dict:
    """
    Build the Founder Knowledge Map payload for a user.

    Returns a dict shaped for KnowledgeMapOut:
        {
          "domains": [{"key","label","score"}],   # user's reading shape
          "ideal":   [{"key","label","score"}],   # stage-aware target
          "total_books_scored": int,
          "stage": str | None,
        }
    """
    books = _collect_read_books(db, user.id)

    raw: Dict[str, float] = {k: 0.0 for k in DOMAIN_KEYS}
    # Depth = weighted average of knowledge_level (1-5) among the books that
    # contribute to each domain. Tracked as numerator/denominator so books
    # lacking a knowledge_level simply don't affect the average.
    depth_num: Dict[str, float] = {k: 0.0 for k in DOMAIN_KEYS}
    depth_den: Dict[str, float] = {k: 0.0 for k in DOMAIN_KEYS}

    for book, weight in books.values():
        contributions = _domains_for_book(book)
        level = getattr(book, "knowledge_level", None)
        for domain, contribution in contributions.items():
            raw[domain] += contribution * weight
            if isinstance(level, int) and 1 <= level <= 5:
                depth_num[domain] += level * contribution * weight
                depth_den[domain] += contribution * weight

    profile = (
        db.query(OnboardingProfile)
        .filter(OnboardingProfile.user_id == user.id)
        .first()
    )
    ideal = _compute_ideal(profile)
    stage = None
    if profile is not None:
        stage = profile.business_stage.value if hasattr(profile.business_stage, "value") else profile.business_stage

    def _depth(k: str) -> Optional[int]:
        if depth_den[k] <= 0:
            return None
        return int(round(depth_num[k] / depth_den[k]))

    domains = [
        {"key": k, "label": DOMAIN_LABELS[k], "score": _bucket(raw[k]), "depth": _depth(k)}
        for k in DOMAIN_KEYS
    ]
    ideal_out = [
        {"key": k, "label": DOMAIN_LABELS[k], "score": ideal[k]}
        for k in DOMAIN_KEYS
    ]

    return {
        "domains": domains,
        "ideal": ideal_out,
        "total_books_scored": len(books),
        "stage": stage,
    }
