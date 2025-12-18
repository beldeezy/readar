from typing import List, Tuple, Set, Optional, Dict
from uuid import UUID
from sqlalchemy.orm import Session
import logging
from collections import Counter, defaultdict
from urllib.parse import quote_plus
from dataclasses import dataclass
from app.models import (
    User,
    OnboardingProfile,
    Book,
    UserBookInteraction,
    UserBookStatus,
    ReadingHistoryEntry,
    BookDifficulty,
)
from app.schemas.recommendation import RecommendationItem

logger = logging.getLogger(__name__)


@dataclass
class ScoreFactors:
    """Tracks contributing factors for a book recommendation score."""
    challenge_fit: float = 0.0
    stage_fit: float = 0.0
    business_model_fit: float = 0.0
    areas_fit: float = 0.0
    promise_match: float = 0.0
    framework_match: float = 0.0
    outcome_match: float = 0.0

# Business models that should prioritize services canon books
SERVICE_LIKE_BUSINESS_MODELS = {
    "service",
    "services",
    "agency",
    "direct/high-ticket",
    "direct / high-ticket",
    "high-ticket",
    "direct",
    "direct_high_ticket",  # Also handle snake_case variant
}

# Business models that should prioritize SaaS canon books
SAAS_LIKE_BUSINESS_MODELS = {
    "saas",
    "software",
    "software-as-a-service",
    "subscription_saas",
    "b2b saas",
    "b2b_saas",
}

# Revenue range to stage mapping for scoring
REVENUE_STAGE = {
    "pre_revenue": "early",
    "lt_100k": "early",
    "100k_300k": "early",
    "300k_500k": "early_mid",
    "500k_1m": "early_mid",
    "1m_3m": "mid",
    "3m_5m": "mid",
    "5m_10m": "scale",
    "10m_30m": "scale",
    "30m_100m": "enterprise",
    "100m_plus": "enterprise",
}


def is_services_canon(book: Book) -> bool:
    """
    Return True if this book is considered part of the 'services canon'.
    We treat any book that has 'services_canon' in theme_tags or functional_tags as part of it.
    """
    tags = (book.theme_tags or []) + (book.functional_tags or [])
    return "services_canon" in tags


def is_saas_canon(book: Book) -> bool:
    """
    Return True if this book is considered part of the 'saas canon'.
    We treat any book that has 'saas_canon' in theme_tags or functional_tags as part of it.
    """
    tags = (book.theme_tags or []) + (book.functional_tags or [])
    return "saas_canon" in tags


def score_promise_match(book: Book, profile: OnboardingProfile) -> float:
    """Score match between book promise and user's biggest challenge."""
    if not book.promise or not profile.biggest_challenge:
        return 0.0
    if profile.biggest_challenge.lower() in book.promise.lower():
        return 1.0
    return 0.0


def score_framework_match(book: Book, profile: OnboardingProfile) -> float:
    """Score match between book frameworks and user's business model."""
    if not book.core_frameworks or not profile.business_model:
        return 0.0
    if not isinstance(book.core_frameworks, list):
        return 0.0
    return 1.0 if any(profile.business_model.lower() in str(fw).lower() for fw in book.core_frameworks) else 0.0


def score_outcome_match(book: Book, profile: OnboardingProfile) -> float:
    """Score match between book outcomes and user's vision."""
    if not book.outcomes or not profile.vision_6_12_months:
        return 0.0
    if not isinstance(book.outcomes, list):
        return 0.0
    return 1.0 if any(str(goal).lower() in profile.vision_6_12_months.lower() for goal in book.outcomes) else 0.0


class NotEnoughSignalError(Exception):
    """Raised when we don't have enough user signal to compute personalized recommendations."""
    pass

# Interaction weights for direct book interactions
INTERACTION_WEIGHTS = {
    UserBookStatus.READ_LIKED: 5.0,
    UserBookStatus.INTERESTED: 3.0,
    UserBookStatus.READ_DISLIKED: -4.0,
    UserBookStatus.NOT_INTERESTED: -6.0,
}

# Scoring weights as per spec (for other scoring components)
WEIGHTS = {
    "READ_LIKED": 5.0,
    "INTERESTED": 3.0,
    "NOT_INTERESTED": -6.0,  # Hard filter
    "READ_DISLIKED": -4.0,
    "SIMILAR_TO_LIKED": 2.0,  # Average of 1.5-3.0 range
    "SIMILAR_TO_DISLIKED": -2.0,
    "HISTORY_RATING_4_PLUS": 4.0,
    "HISTORY_RATING_3": 2.0,
    "HISTORY_RATING_2_OR_LESS": -3.0,
    "HISTORY_TO_READ": 2.0,
    "STAGE_FIT_STRONG": 3.0,
    "STAGE_FIT_MEDIUM": 1.5,
    "STAGE_FIT_WEAK": 0.0,
    "CATEGORY_BOOST": 0.75,  # Average of 0.5-1.0 range
}

# Weight constants for insight-based scoring factors
W_STAGE = 1.2
W_CHALLENGE = 1.4
W_AREAS = 1.0
W_MODEL = 0.8
W_PROMISE = 1.2
W_FRAMEWORK = 0.6
W_OUTCOME = 0.6

# Signal threshold for determining if user has enough data
SIGNAL_THRESHOLD = 10


def get_generic_recommendations(
    db: Session,
    limit: int = 10,
    business_stage: Optional[str] = None,
    business_model: Optional[str] = None,
) -> List[RecommendationItem]:
    """
    Generic, non-personalized recommendations for cold-start users.
    
    For now, just return a curated or stable set (e.g. newest or hand-tagged).
    If business_stage or business_model are provided, uses curated filtering.
    Otherwise, returns books ordered by created_at (newest first).
    
    For service-like business models, prioritizes services canon books.
    For SaaS-like business models, prioritizes SaaS canon books.
    """
    q = db.query(Book)
    
    # Check if business model is service-like or SaaS-like
    is_service_like = False
    is_saas_like = False
    if business_model:
        model_lower = business_model.lower()
        is_service_like = model_lower in SERVICE_LIKE_BUSINESS_MODELS
        is_saas_like = model_lower in SAAS_LIKE_BUSINESS_MODELS

    # If stage/model provided, use curated filtering (backward compatibility)
    if business_stage or business_model:
        all_books = q.all()
        if not all_books:
            return []
        
        curated_books = []
        
        # Stage-based curation
        if business_stage:
            stage_str = (
                business_stage.value if hasattr(business_stage, 'value') else str(business_stage)
            )
            
            if stage_str in ["idea", "pre-revenue"]:
                curated_books = [
                    b for b in all_books
                    if b.business_stage_tags and (
                        "idea" in b.business_stage_tags or "pre-revenue" in b.business_stage_tags
                    )
                ]
            elif stage_str in ["early-revenue", "scaling"]:
                curated_books = [
                    b for b in all_books
                    if b.business_stage_tags and (
                        "early-revenue" in b.business_stage_tags or "scaling" in b.business_stage_tags
                    )
                ]
        
        # Model-based curation
        if business_model and curated_books:
            model_lower = business_model.lower()
            model_tag_mapping = {
                "subscription_saas": ["saas", "product", "recurring", "subscription"],
                "service": ["service", "agency", "freelancing", "client"],
                "product": ["product", "manufacturing", "physical"],
                "marketplace_platform": ["marketplace", "platform", "network"],
            }
            relevant_tags = model_tag_mapping.get(model_lower, [])
            if relevant_tags:
                filtered_books = [
                    b for b in curated_books
                    if any(any(rt in tag.lower() for tag in (b.functional_tags or [])) for rt in relevant_tags)
                ]
                if filtered_books:
                    curated_books = filtered_books
        
        if not curated_books:
            curated_books = all_books
        
        # For service-like or SaaS-like users, apply 70/30 split
        if is_service_like or is_saas_like:
            if is_service_like:
                niche_books = [b for b in curated_books if is_services_canon(b)]
            else:  # is_saas_like
                niche_books = [b for b in curated_books if is_saas_canon(b)]
            
            general_books = [b for b in curated_books if b not in niche_books]
            
            target_niche = int(limit * 0.7)
            primary = niche_books[:target_niche]
            remaining_slots = limit - len(primary)
            secondary = general_books[:max(0, remaining_slots)]
            
            books = primary + secondary
            
            # Fill remaining slots if needed
            if len(books) < limit:
                remaining = [b for b in curated_books if b not in books]
                books.extend(remaining[:limit - len(books)])
        else:
            books = curated_books[:limit]
    else:
        # Simple generic: prefer books with business_stage_tags / theme_tags populated
        # Order by created_at descending (newest first)
        q = q.order_by(Book.created_at.desc())
        books = q.limit(limit).all()

    recommendations: List[RecommendationItem] = []

    for idx, book in enumerate(books):
        # Build purchase URL (generic recs don't have onboarding, so why_this_book can be None)
        purchase_url = _build_purchase_url(book)
        
        # Build why_signals (generic recs don't have onboarding, so signals will be limited)
        why_signals = _build_why_signals(None, book)
        
        # Build why_this_book for generic recs (no onboarding, so use empty factors)
        empty_factors = ScoreFactors()
        is_top = (idx == 0)
        why_this_book_text = build_why_this_book(empty_factors, None, book, is_top=is_top)
        
        relevancy_score = 0.0  # generic recs, no personalized score
        recommendations.append(
            RecommendationItem(
                book_id=str(book.id),
                title=book.title,
                subtitle=getattr(book, "subtitle", None),
                author_name=getattr(book, "author_name", None),
                score=relevancy_score,
                relevancy_score=relevancy_score,
                thumbnail_url=getattr(book, "thumbnail_url", None),
                cover_image_url=getattr(book, "cover_image_url", None),
                page_count=getattr(book, "page_count", None),
                published_year=getattr(book, "published_year", None),
                categories=book.categories,
                language=getattr(book, "language", None),
                isbn_10=getattr(book, "isbn_10", None),
                isbn_13=getattr(book, "isbn_13", None),
                average_rating=getattr(book, "average_rating", None),
                ratings_count=getattr(book, "ratings_count", None),
                theme_tags=book.theme_tags,
                functional_tags=book.functional_tags,
                business_stage_tags=book.business_stage_tags,
                purchase_url=purchase_url,
                why_this_book=why_this_book_text,
                why_recommended=None,  # Deprecated
                why_signals=why_signals if why_signals else None,
            )
        )

    # Ensure recommendations are sorted by relevancy_score descending
    recommendations.sort(key=lambda x: x.relevancy_score, reverse=True)

    return recommendations


def _get_book_tags(book: Book) -> Tuple[Set[str], Set[str], Set[str]]:
    """Extract all tags from a book for similarity matching."""
    categories = set(book.categories or [])
    functional_tags = set(book.functional_tags or [])
    theme_tags = set(book.theme_tags or [])
    return categories, functional_tags, theme_tags


def _books_share_tags(book1: Book, book2: Book) -> bool:
    """Check if two books share any tags."""
    cats1, func1, theme1 = _get_book_tags(book1)
    cats2, func2, theme2 = _get_book_tags(book2)
    
    return bool(
        (cats1 & cats2) or
        (func1 & func2) or
        (theme1 & theme2)
    )


def _get_user(db: Session, user_id: UUID) -> Optional[User]:
    """Load user by ID."""
    return db.query(User).filter(User.id == user_id).first()


def _get_user_interactions(db: Session, user_id: UUID) -> List[UserBookInteraction]:
    """Load all book interactions for a user."""
    return (
        db.query(UserBookInteraction)
        .filter(UserBookInteraction.user_id == user_id)
        .all()
    )


def _get_user_reading_history(db: Session, user_id: UUID) -> List[ReadingHistoryEntry]:
    """Load all reading history entries for a user."""
    return (
        db.query(ReadingHistoryEntry)
        .filter(ReadingHistoryEntry.user_id == user_id)
        .all()
    )


def _score_from_interactions(
    interactions: List[UserBookInteraction],
) -> Tuple[Dict[UUID, float], Set[UUID]]:
    """
    Compute direct interaction scores and a set of blocked book_ids.
    
    Returns: (scores dict mapping book_id to score, blocked set of book_ids)
    """
    scores: Dict[UUID, float] = defaultdict(float)
    blocked: Set[UUID] = set()

    for inter in interactions:
        weight = INTERACTION_WEIGHTS.get(inter.status)
        if weight is None:
            continue

        book_id = inter.book_id

        # Hard-block NOT_INTERESTED
        if inter.status == UserBookStatus.NOT_INTERESTED:
            blocked.add(book_id)
            continue

        # We still might want to allow READ_DISLIKED to participate as negative signal
        scores[book_id] += weight

    return scores, blocked


def _score_from_history(
    history_entries: List[ReadingHistoryEntry],
    book_id_by_title_author: Dict[Tuple[str, str], UUID],
) -> Dict[UUID, float]:
    """
    Score books based on reading history entries.
    
    Args:
        history_entries: List of reading history entries from Goodreads
        book_id_by_title_author: Dict mapping (title_lower, author_lower) to book_id
    
    Returns:
        Dict mapping book_id to score
    """
    scores: Dict[UUID, float] = defaultdict(float)

    for entry in history_entries:
        key = (entry.title.strip().lower(), (entry.author or "").strip().lower())
        book_id = book_id_by_title_author.get(key)
        if not book_id:
            continue

        shelf = (entry.shelf or "").lower()
        rating = entry.my_rating or 0.0

        if shelf == "read":
            if rating >= 4.0:
                scores[book_id] += 4.0
            elif rating >= 3.0:
                scores[book_id] += 2.0
            elif rating > 0:
                scores[book_id] -= 3.0
        elif shelf in {"to-read", "want-to-read"}:
            scores[book_id] += 2.0

    return scores


def _build_purchase_url(book: Book) -> str:
    """
    Build a purchase URL for a book.
    
    Uses purchase_url if present, otherwise falls back to Amazon search URL.
    """
    if book.purchase_url:
        return book.purchase_url
    
    # Build Amazon search URL from title and author
    title = book.title or ""
    author = book.author_name or ""
    search_query = f"{title} {author}".strip()
    search_query_encoded = quote_plus(search_query)
    return f"https://www.amazon.com/s?k={search_query_encoded}"


def humanize(value: str) -> str:
    """Replace underscores with spaces and clean up the string."""
    return value.replace("_", " ").strip()


def build_why_this_book(
    factors: ScoreFactors, 
    user_profile: Optional[OnboardingProfile], 
    book: Book,
    is_top: bool = False,
    reasons: Optional[List[str]] = None
) -> str:
    """
    Returns user-facing explanation copy.
    
    - Top book: 1 lead sentence + bullets + action line (decision memo format)
    - Others: short 1-2 lines
    
    Args:
        factors: Score factors for the book
        user_profile: User's onboarding profile (optional)
        book: The book being recommended
        is_top: Whether this is the top recommendation (index 0)
        reasons: List of reason strings explaining why this book matches (optional)
    """
    if not user_profile:
        # Fallback for users without onboarding
        has_promise = book.promise and book.promise.strip()
        if has_promise:
            if is_top:
                return f"This is your next read because it attacks the bottleneck you're facing right now.\n\n• {book.promise.strip()}\n\nStart by skimming the table of contents, then read the chapter that maps to your bottleneck first."
            return book.promise.strip()
        if is_top:
            return "This is your next read because it attacks the bottleneck you're facing right now.\n\n• A strong fit for where you are right now.\n\nStart by skimming the table of contents, then read the chapter that maps to your bottleneck first."
        return "This is a solid foundational pick to build clarity and execution momentum."
    
    # Extract profile fields
    stage = None
    if user_profile.business_stage:
        stage = (
            user_profile.business_stage.value 
            if hasattr(user_profile.business_stage, 'value') 
            else str(user_profile.business_stage)
        )
        stage = humanize(stage).replace("-", " ").title()
    
    model = (user_profile.business_model or "").strip()
    challenge = (user_profile.biggest_challenge or "").strip()
    
    # Normalize reasons (keep it small + readable)
    clean_reasons: List[str] = []
    if reasons:
        clean_reasons = [r.strip() for r in reasons if isinstance(r, str) and r.strip()]
        clean_reasons = clean_reasons[:3]
    
    # If no reasons provided, generate some from factors
    if not clean_reasons:
        if factors.challenge_fit > 0 and challenge:
            challenge_text = humanize(challenge)
            clean_reasons.append(f"Directly addresses your {challenge_text} challenge")
        if factors.stage_fit > 0 and stage:
            clean_reasons.append(f"Strong fit for your {stage} stage")
        if factors.business_model_fit > 0 and model:
            model_text = humanize(model)
            clean_reasons.append(f"Matches your {model_text} business model")
        if factors.areas_fit > 0 and user_profile.areas_of_business:
            areas = [humanize(a) for a in (user_profile.areas_of_business[:1] or [])]
            if areas:
                clean_reasons.append(f"Focuses on {areas[0]}")
    
    # Limit to 3 reasons
    clean_reasons = clean_reasons[:3]
    
    if is_top:
        # Decision memo format for top recommendation
        lead = "This is your next read because it attacks the bottleneck you're facing right now."
        
        context_bits = []
        if stage:
            context_bits.append(f"Stage: {stage}")
        if model:
            context_bits.append(f"Model: {model}")
        if challenge:
            context_bits.append(f"Bottleneck: {challenge}")
        
        bullets = []
        for r in clean_reasons:
            # Ensure reason starts with capital and ends appropriately
            reason_text = r.strip()
            if not reason_text[0].isupper():
                reason_text = reason_text[0].upper() + reason_text[1:]
            bullets.append(f"• {reason_text}")
        
        # Action line
        action = "Start by skimming the table of contents, then read the chapter that maps to your bottleneck first."
        
        parts = [lead]
        if context_bits:
            parts.append(" / ".join(context_bits))
        if bullets:
            parts.append("\n".join(bullets))
        parts.append(action)
        
        return "\n".join(parts)
    
    # Non-top: short and clean (1-2 lines)
    short = []
    if clean_reasons:
        short.append(clean_reasons[0])
    elif challenge:
        challenge_text = humanize(challenge)
        short.append(f"Useful if you're stuck on: {challenge_text}")
    else:
        short.append("A strong fit for where you are right now.")
    
    return " ".join(short)


def _build_why_signals(
    onboarding: Optional[OnboardingProfile],
    book: Book,
) -> List[Dict[str, str]]:
    """
    Build structured why_signals (reason chips) for a book recommendation.
    
    Returns up to 3 signals:
    - canon: "SaaS Canon" / "Services Canon" etc.
    - stage_match: "Scaling stage fit" (or whatever the user's stage is)
    - function_overlap: e.g., "Marketing + Product", "Operations + Systems"
    - (optional) challenge_match: "Directly addresses your biggest blocker"
    """
    signals: List[Dict[str, str]] = []
    
    # Extract book metadata
    book_theme_tags = [t.lower() for t in (book.theme_tags or [])]
    book_functional_tags = [t.lower() for t in (book.functional_tags or [])]
    book_stage_tags = [t.lower() for t in (book.business_stage_tags or [])]
    
    # Signal 1: Canon
    if "services_canon" in (book_theme_tags + book_functional_tags):
        signals.append({"type": "canon", "label": "Services Canon"})
    elif "saas_canon" in (book_theme_tags + book_functional_tags):
        signals.append({"type": "canon", "label": "SaaS Canon"})
    
    # Signal 2: Stage match
    if onboarding and onboarding.business_stage:
        business_stage = (
            onboarding.business_stage.value 
            if hasattr(onboarding.business_stage, 'value') 
            else str(onboarding.business_stage)
        )
        if business_stage.lower() in book_stage_tags:
            stage_display = business_stage.replace("-", " ").title()
            signals.append({"type": "stage_match", "label": f"{stage_display} stage fit"})
    
    # Signal 3: Function overlap
    if onboarding and onboarding.areas_of_business:
        areas_lower = [a.lower() if isinstance(a, str) else str(a).lower() for a in onboarding.areas_of_business]
        matching_areas = []
        for area in areas_lower:
            # Check if area matches any functional tag
            for ft in book_functional_tags:
                if area in ft or ft in area:
                    # Format the area nicely
                    area_display = area.replace("_", " ").title()
                    if area_display not in matching_areas:
                        matching_areas.append(area_display)
        
        if matching_areas:
            # Join up to 2 matching areas
            label = " + ".join(matching_areas[:2])
            signals.append({"type": "function_overlap", "label": label})
    
    # Signal 4 (optional): Challenge match
    if onboarding and onboarding.biggest_challenge and len(signals) < 3:
        challenge_lower = onboarding.biggest_challenge.lower()
        challenge_mapping = {
            "focus": ["systems", "strategy", "operations", "productivity"],
            "prioritization": ["systems", "strategy", "operations", "productivity"],
            "sales": ["sales", "marketing", "positioning", "client_acquisition"],
            "leads": ["sales", "marketing", "positioning", "client_acquisition"],
            "retention": ["customer_success", "onboarding", "retention"],
            "churn": ["customer_success", "onboarding", "retention"],
            "hiring": ["leadership", "management", "team", "hiring"],
            "team": ["leadership", "management", "team", "hiring"],
        }
        
        matched_themes = []
        for keyword, themes in challenge_mapping.items():
            if keyword in challenge_lower:
                matched_themes.extend(themes)
        
        if matched_themes:
            book_tags_all = book_theme_tags + book_functional_tags
            if any(theme in book_tags_all for theme in matched_themes):
                signals.append({"type": "challenge_match", "label": "Directly addresses your biggest blocker"})
    
    # Return up to 3 signals
    return signals[:3]


def _build_why_this_book(
    onboarding: Optional[OnboardingProfile],
    book: Book,
    score_context: Optional[Dict] = None,
) -> str:
    """
    Build a personalized "Why this book" explanation using:
    - User onboarding (business_model, business_stage, areas_of_business, biggest_challenge, vision/blockers)
    - Book metadata (categories, functional_tags, theme_tags, difficulty, page_count)
    
    Returns 2-4 sentences that sound like an advisor, not a bot.
    """
    sentences = []
    
    # Extract user context
    business_model = None
    business_stage = None
    areas_of_business = []
    biggest_challenge = None
    vision = None
    blockers = None
    
    if onboarding:
        business_model = onboarding.business_model
        if onboarding.business_stage:
            business_stage = (
                onboarding.business_stage.value 
                if hasattr(onboarding.business_stage, 'value') 
                else str(onboarding.business_stage)
            )
        areas_of_business = onboarding.areas_of_business or []
        biggest_challenge = onboarding.biggest_challenge
        vision = onboarding.vision_6_12_months
        blockers = onboarding.blockers
    
    # Extract book metadata
    book_theme_tags = [t.lower() for t in (book.theme_tags or [])]
    book_functional_tags = [t.lower() for t in (book.functional_tags or [])]
    book_stage_tags = [t.lower() for t in (book.business_stage_tags or [])]
    book_categories = book.categories or []
    book_difficulty = book.difficulty
    book_page_count = book.page_count
    
    # Sentence 1: Reflect user context
    context_parts = []
    
    # Business model match
    if business_model:
        model_lower = business_model.lower()
        is_service_like = model_lower in SERVICE_LIKE_BUSINESS_MODELS
        is_saas_like = model_lower in SAAS_LIKE_BUSINESS_MODELS
        
        if is_service_like and "services_canon" in (book_theme_tags + book_functional_tags):
            context_parts.append(f"your {business_model} business")
        elif is_saas_like and "saas_canon" in (book_theme_tags + book_functional_tags):
            context_parts.append(f"your {business_model} business")
        elif business_model:
            context_parts.append(f"your {business_model} business")
    
    # Stage match
    if business_stage and business_stage.lower() in book_stage_tags:
        stage_display = business_stage.replace("-", " ").title()
        context_parts.append(f"your current stage ({stage_display})")
    
    # Functional overlap
    if areas_of_business:
        areas_lower = [a.lower() if isinstance(a, str) else str(a).lower() for a in areas_of_business]
        matching_areas = [a for a in areas_lower if any(a in ft for ft in book_functional_tags)]
        if matching_areas:
            area_display = matching_areas[0].replace("_", " ").title()
            context_parts.append(f"your focus on {area_display}")
    
    # Build sentence 1
    if context_parts:
        context_str = " and ".join(context_parts[:2])  # Max 2 context parts
        sentences.append(f"Based on {context_str}, {book.title} is a strong match.")
    elif business_model:
        sentences.append(f"Based on your {business_model} business, {book.title} is a strong match.")
    else:
        sentences.append(f"{book.title} is a strong match for your situation.")
    
    # Sentence 2: Connect to book strength
    book_strengths = []
    
    # Canon books
    if "services_canon" in (book_theme_tags + book_functional_tags):
        book_strengths.append("part of the essential services canon")
    elif "saas_canon" in (book_theme_tags + book_functional_tags):
        book_strengths.append("part of the essential SaaS canon")
    
    # Challenge alignment
    if biggest_challenge:
        challenge_lower = biggest_challenge.lower()
        challenge_mapping = {
            "focus": ["systems", "strategy", "operations", "productivity"],
            "prioritization": ["systems", "strategy", "operations", "productivity"],
            "sales": ["sales", "marketing", "positioning", "client_acquisition"],
            "leads": ["sales", "marketing", "positioning", "client_acquisition"],
            "retention": ["customer_success", "onboarding", "retention"],
            "churn": ["customer_success", "onboarding", "retention"],
            "hiring": ["leadership", "management", "team", "hiring"],
            "team": ["leadership", "management", "team", "hiring"],
        }
        
        matched_themes = []
        for keyword, themes in challenge_mapping.items():
            if keyword in challenge_lower:
                matched_themes.extend(themes)
        
        if matched_themes:
            book_tags_all = book_theme_tags + book_functional_tags
            if any(theme in book_tags_all for theme in matched_themes):
                book_strengths.append("addresses your biggest challenge")
    
    # Functional tag highlights
    if book_functional_tags:
        notable_tags = []
        if "marketing" in book_functional_tags:
            notable_tags.append("marketing")
        if "sales" in book_functional_tags:
            notable_tags.append("sales")
        if "operations" in book_functional_tags:
            notable_tags.append("operations")
        if "product" in book_functional_tags:
            notable_tags.append("product")
        if "leadership" in book_functional_tags:
            notable_tags.append("leadership")
        
        if notable_tags and not book_strengths:
            tag_display = notable_tags[0].replace("_", " ").title()
            book_strengths.append(f"a practical framework for {tag_display}")
    
    # Build sentence 2
    if book_strengths:
        strength = book_strengths[0]
        sentences.append(f"This book is {strength}.")
    else:
        # Generic strength based on tags
        if book_functional_tags:
            primary_tag = book_functional_tags[0].replace("_", " ").title()
            sentences.append(f"This book provides practical frameworks for {primary_tag}.")
        else:
            sentences.append("This book provides practical, actionable insights.")
    
    # Sentence 3 (optional): Reading intensity hint
    if book_page_count is not None or book_difficulty is not None:
        intensity_parts = []
        
        if book_page_count is not None:
            if book_page_count < 250 and book_difficulty == BookDifficulty.LIGHT:
                intensity_parts.append("quick, practical read")
            elif book_page_count > 350 or book_difficulty == BookDifficulty.DEEP:
                intensity_parts.append("deeper playbook and reference")
            elif book_difficulty == BookDifficulty.LIGHT:
                intensity_parts.append("accessible and practical")
        
        if intensity_parts:
            sentences.append(f"It's a {intensity_parts[0]}.")
    
    # Sentence 4 (optional): Next step hint based on vision/blockers
    if vision or blockers:
        next_step_parts = []
        
        if blockers:
            blockers_lower = blockers.lower()
            if "time" in blockers_lower or "busy" in blockers_lower:
                next_step_parts.append("apply one framework this week")
            elif "focus" in blockers_lower or "prioritization" in blockers_lower:
                next_step_parts.append("start with the prioritization chapter")
            elif "team" in blockers_lower or "hiring" in blockers_lower:
                next_step_parts.append("use it to refine your hiring process")
        
        if vision:
            vision_lower = vision.lower()
            if "growth" in vision_lower or "scale" in vision_lower:
                next_step_parts.append("apply it to your growth plan")
            elif "product" in vision_lower:
                next_step_parts.append("use it to improve your product strategy")
        
        if next_step_parts:
            sentences.append(f"Start here: {next_step_parts[0]}.")
    
    # Join sentences (2-4 sentences)
    return " ".join(sentences[:4])


def _build_user_context(onboarding: Optional[OnboardingProfile]) -> Dict[str, Optional[str]]:
    """
    Extract relevant onboarding fields from the OnboardingProfile model.
    
    Returns a dict with business_stage, business_model, biggest_challenge, areas_of_business, revenue_stage.
    """
    if not onboarding:
        return {}

    # Handle business_stage enum
    business_stage = None
    if onboarding.business_stage:
        business_stage = (
            onboarding.business_stage.value 
            if hasattr(onboarding.business_stage, 'value') 
            else str(onboarding.business_stage)
        )

    # Map revenue range to stage
    revenue_stage = None
    if getattr(onboarding, "current_gross_revenue", None):
        revenue_stage = REVENUE_STAGE.get(onboarding.current_gross_revenue)

    return {
        "business_stage": business_stage,
        "business_model": onboarding.business_model,
        "biggest_challenge": onboarding.biggest_challenge,
        "areas_of_business": onboarding.areas_of_business,
        "revenue_stage": revenue_stage,
    }


def _score_from_stage_fit(
    user_ctx: Dict[str, Optional[str]],
    book: Book,
    onboarding: Optional[OnboardingProfile] = None,
) -> Tuple[float, ScoreFactors]:
    """
    Simple rule-based fit:
    - boost books whose tags match the user's business_stage, business_model, or areas_of_business.
    - prioritize services canon books for service-like business models.
    - incorporate insight-based matches (promise, frameworks, outcomes).
    
    Returns: (score contribution from stage/model/challenge fit, score factors)
    """
    score = 0.0
    factors = ScoreFactors()

    business_stage = (user_ctx.get("business_stage") or "").lower()
    business_model = (user_ctx.get("business_model") or "").lower()
    biggest_challenge = (user_ctx.get("biggest_challenge") or "").lower()
    areas_of_business = user_ctx.get("areas_of_business") or []
    revenue_stage = user_ctx.get("revenue_stage")

    # Normalize to lower-case
    book_stage_tags = [t.lower() for t in (book.business_stage_tags or [])]
    functional_tags = [t.lower() for t in (book.functional_tags or [])]
    theme_tags = [t.lower() for t in (book.theme_tags or [])]

    # Check if user has a service-like or SaaS-like business model
    is_service_like = business_model in SERVICE_LIKE_BUSINESS_MODELS
    is_saas_like = business_model in SAAS_LIKE_BUSINESS_MODELS

    if business_stage and business_stage in book_stage_tags:
        stage_score = 3.0
        score += stage_score
        factors.stage_fit = stage_score

    # Revenue stage matching: boost if book's stage_tags match user's revenue stage
    if revenue_stage and book.business_stage_tags:
        # Map revenue stage to book stage tags
        revenue_to_book_stages = {
            "early": ["idea", "pre-revenue"],
            "early_mid": ["pre-revenue", "early-revenue"],
            "mid": ["early-revenue", "scaling"],
            "scale": ["scaling"],
            "enterprise": ["scaling"],
        }
        matching_stages = revenue_to_book_stages.get(revenue_stage, [])
        if any(stage in book.business_stage_tags for stage in matching_stages):
            revenue_score = 0.35
            score += revenue_score
            factors.stage_fit += revenue_score

    if business_model and business_model in theme_tags:
        model_score = 2.0
        score += model_score
        factors.business_model_fit = model_score

    # If areas_of_business is an array, not string
    if isinstance(areas_of_business, (list, tuple)):
        for area in areas_of_business:
            a = str(area).lower()
            if a in functional_tags:
                area_score = 1.5
                score += area_score
                factors.areas_fit += area_score

    # Very simple challenge-based boost
    if biggest_challenge:
        for tag in theme_tags:
            if biggest_challenge in tag:
                challenge_score = 1.5
                score += challenge_score
                factors.challenge_fit = challenge_score
                break

    all_tags = theme_tags + functional_tags

    # Service bias: prioritize services canon books for service-like business models
    if is_service_like:
        if "services_canon" in all_tags:
            # Big boost so services canon dominates
            canon_score = 6.0
            score += canon_score
            factors.business_model_fit += canon_score
        if "sales" in all_tags or "client_acquisition" in all_tags:
            score += 1.5
        if "service_delivery" in all_tags or "operations" in all_tags:
            score += 1.0

    # SaaS bias: prioritize SaaS canon books for SaaS/software founders
    if is_saas_like:
        if "saas_canon" in all_tags:
            # Big boost so SaaS canon dominates
            canon_score = 6.0
            score += canon_score
            factors.business_model_fit += canon_score
        # PLG/growth emphasis
        if "plg" in all_tags or "growth" in all_tags or "client_acquisition" in all_tags:
            score += 1.5
        # Product + metrics emphasis
        if "product" in all_tags or "metrics" in all_tags or "analytics" in all_tags:
            score += 1.0

    # Insight-based matching
    if onboarding:
        promise_match = score_promise_match(book, onboarding)
        framework_match = score_framework_match(book, onboarding)
        outcome_match = score_outcome_match(book, onboarding)
        
        factors.promise_match = promise_match
        factors.framework_match = framework_match
        factors.outcome_match = outcome_match
        
        # Apply weighted insight matches to score
        score += W_PROMISE * promise_match
        score += W_FRAMEWORK * framework_match
        score += W_OUTCOME * outcome_match

    return score, factors


def _calculate_preference_score(
    book: Book,
    interactions: List[UserBookInteraction],
    all_books: List[Book],
    liked_book_ids: Set[UUID],
    disliked_book_ids: Set[UUID],
) -> Tuple[float, List[str]]:
    """
    Calculate preference_score from 4-state interactions.
    
    Returns: (score, reasons)
    """
    score = 0.0
    reasons: List[str] = []
    
    # Direct interactions with this book
    for interaction in interactions:
        if interaction.book_id == book.id:
            if interaction.status == UserBookStatus.READ_LIKED:
                score += WEIGHTS["READ_LIKED"]
                reasons.append("You marked this as read and liked.")
            elif interaction.status == UserBookStatus.INTERESTED:
                score += WEIGHTS["INTERESTED"]
                reasons.append("You expressed interest in this book.")
            elif interaction.status == UserBookStatus.NOT_INTERESTED:
                score += WEIGHTS["NOT_INTERESTED"]
                reasons.append("You marked this as not interested.")
                return score, reasons  # Hard filter - return immediately
            elif interaction.status == UserBookStatus.READ_DISLIKED:
                score += WEIGHTS["READ_DISLIKED"]
                reasons.append("You marked this as read and disliked.")
    
    # Similarity propagation: similar to liked books
    if liked_book_ids:
        liked_books = [b for b in all_books if b.id in liked_book_ids]
        for liked_book in liked_books:
            if _books_share_tags(book, liked_book):
                score += WEIGHTS["SIMILAR_TO_LIKED"]
                reasons.append("Similar to books you liked.")
                break  # Only count once per similarity match
    
    # Similarity propagation: similar to disliked books
    if disliked_book_ids:
        disliked_books = [b for b in all_books if b.id in disliked_book_ids]
        for disliked_book in disliked_books:
            if _books_share_tags(book, disliked_book):
                score += WEIGHTS["SIMILAR_TO_DISLIKED"]
                reasons.append("Similar to books you disliked.")
                break  # Only count once per similarity match
    
    return score, reasons


def _calculate_history_score(
    book: Book,
    history_entries: List[ReadingHistoryEntry],
    all_books: List[Book],
) -> Tuple[float, List[str]]:
    """
    Calculate history_score from Goodreads import.
    
    Returns: (score, reasons)
    """
    score = 0.0
    reasons: List[str] = []
    
    # Check if this exact book is in history
    book_title_lower = book.title.lower().strip()
    for entry in history_entries:
        entry_title_lower = entry.title.lower().strip()
        
        # Exact match (same book)
        if entry_title_lower == book_title_lower:
            if entry.shelf == "read":
                if entry.my_rating is not None:
                    if entry.my_rating >= 4:
                        score += WEIGHTS["HISTORY_RATING_4_PLUS"]
                        reasons.append("You rated this highly in your reading history.")
                    elif entry.my_rating == 3:
                        score += WEIGHTS["HISTORY_RATING_3"]
                        reasons.append("You rated this book in your reading history.")
                    elif entry.my_rating <= 2:
                        score += WEIGHTS["HISTORY_RATING_2_OR_LESS"]
                        reasons.append("You rated this low in your reading history.")
                else:
                    # Read but no rating - treat as neutral/positive
                    score += 1.0
                    reasons.append("You've read this book before.")
            elif entry.shelf == "to-read":
                score += WEIGHTS["HISTORY_TO_READ"]
                reasons.append("This is in your to-read list.")
    
    return score, reasons


def _calculate_category_boost(
    book: Book,
    history_entries: List[ReadingHistoryEntry],
    all_books: List[Book],
) -> Tuple[float, List[str]]:
    """
    Calculate boost based on category frequency in reading history.
    
    Returns: (score, reasons)
    """
    score = 0.0
    reasons: List[str] = []
    
    if not history_entries:
        return score, reasons
    
    # Build category frequency from history
    # We need to match history entries to books to get their categories
    history_titles = {h.title.lower().strip() for h in history_entries}
    category_counter = Counter()
    
    for book_candidate in all_books:
        if book_candidate.title.lower().strip() in history_titles:
            if book_candidate.categories:
                category_counter.update(book_candidate.categories)
    
    if not category_counter:
        return score, reasons
    
    # Get top N categories (top 5)
    top_categories = {cat for cat, _ in category_counter.most_common(5)}
    
    # Check if this book's categories match
    book_categories = set(book.categories or [])
    if book_categories & top_categories:
        score += WEIGHTS["CATEGORY_BOOST"]
        matching_cats = book_categories & top_categories
        reasons.append(f"Matches your reading interests in {', '.join(list(matching_cats)[:2])}.")
    
    return score, reasons


def _calculate_stage_fit_score(
    book: Book,
    onboarding: Optional[OnboardingProfile],
) -> Tuple[float, List[str], ScoreFactors]:
    """
    Calculate stage_fit_score from onboarding data.
    
    Returns: (score, reasons, score_factors)
    """
    score = 0.0
    reasons: List[str] = []
    factors = ScoreFactors()
    
    if not onboarding:
        return score, reasons, factors
    
    # Business stage match
    if onboarding.business_stage:
        business_stage_str = (
            onboarding.business_stage.value 
            if hasattr(onboarding.business_stage, 'value') 
            else str(onboarding.business_stage)
        )
        
        if book.business_stage_tags:
            if business_stage_str in book.business_stage_tags:
                stage_score = WEIGHTS["STAGE_FIT_STRONG"]
                score += stage_score
                factors.stage_fit = stage_score
                reasons.append("Strong match for your business stage.")
            else:
                # Check for related stages (e.g., idea/pre-revenue are similar)
                related_stages = {
                    "idea": ["pre-revenue"],
                    "pre-revenue": ["idea"],
                    "early-revenue": ["scaling"],
                    "scaling": ["early-revenue"],
                }
                related = related_stages.get(business_stage_str, [])
                if any(rel in book.business_stage_tags for rel in related):
                    stage_score = WEIGHTS["STAGE_FIT_MEDIUM"]
                    score += stage_score
                    factors.stage_fit = stage_score
                    reasons.append("Good match for your business stage.")
    
    # Revenue stage matching: boost if book's stage_tags match user's revenue stage
    if getattr(onboarding, "current_gross_revenue", None):
        user_revenue_stage = REVENUE_STAGE.get(onboarding.current_gross_revenue)
        if user_revenue_stage and book.business_stage_tags:
            # Map revenue stage to book stage tags
            revenue_to_book_stages = {
                "early": ["idea", "pre-revenue"],
                "early_mid": ["pre-revenue", "early-revenue"],
                "mid": ["early-revenue", "scaling"],
                "scale": ["scaling"],
                "enterprise": ["scaling"],
            }
            matching_stages = revenue_to_book_stages.get(user_revenue_stage, [])
            if any(stage in book.business_stage_tags for stage in matching_stages):
                revenue_score = 0.35
                score += revenue_score
                factors.stage_fit += revenue_score
                # Optionally add a reason if we want to surface this
                # reasons.append("Matches your revenue stage.")
    
    # Business model match (simple keyword matching in functional_tags)
    is_service_like = False
    is_saas_like = False
    if onboarding.business_model:
        business_model_lower = onboarding.business_model.lower()
        is_service_like = business_model_lower in SERVICE_LIKE_BUSINESS_MODELS
        is_saas_like = business_model_lower in SAAS_LIKE_BUSINESS_MODELS
        book_functional_tags = set(book.functional_tags or [])
        
        # Map business models to relevant tags
        model_tag_mapping = {
            "subscription_saas": ["saas", "product", "recurring", "subscription"],
            "service": ["service", "agency", "freelancing", "client"],
            "product": ["product", "manufacturing", "physical"],
            "marketplace_platform": ["marketplace", "platform", "network"],
            "licensing_ip": ["licensing", "ip", "intellectual property"],
            "advertising_supported": ["advertising", "media", "content"],
            "affiliate_commission": ["affiliate", "commission", "referral"],
            "direct_high_ticket": ["sales", "high-ticket", "enterprise"],
            "franchise": ["franchise", "expansion"],
            "hybrid": [],  # Too broad, no specific tags
        }
        
        relevant_tags = model_tag_mapping.get(business_model_lower, [])
        if relevant_tags:
            matches = [tag for tag in relevant_tags if any(tag in ft.lower() for ft in book_functional_tags)]
            if matches:
                model_score = WEIGHTS["STAGE_FIT_STRONG"]
                score += model_score
                factors.business_model_fit = model_score
                reasons.append("Matches your business model.")
    
    all_tags = set((book.theme_tags or []) + (book.functional_tags or []))
    all_tags_lower = {tag.lower() for tag in all_tags}
    
    # Service bias: prioritize services canon books for service-like business models
    if is_service_like:
        if "services_canon" in all_tags_lower:
            # Big boost so services canon dominates
            canon_score = 6.0
            score += canon_score
            factors.business_model_fit += canon_score
            reasons.append("Part of the services canon - essential reading for service businesses.")
        if "sales" in all_tags_lower or "client_acquisition" in all_tags_lower:
            score += 1.5
        if "service_delivery" in all_tags_lower or "operations" in all_tags_lower:
            score += 1.0
    
    # SaaS bias: prioritize SaaS canon books for SaaS/software founders
    if is_saas_like:
        if "saas_canon" in all_tags_lower:
            # Big boost so SaaS canon dominates
            canon_score = 6.0
            score += canon_score
            factors.business_model_fit += canon_score
            reasons.append("Part of the SaaS canon - essential reading for SaaS founders.")
        # PLG/growth emphasis
        if "plg" in all_tags_lower or "growth" in all_tags_lower or "client_acquisition" in all_tags_lower:
            score += 1.5
        # Product + metrics emphasis
        if "product" in all_tags_lower or "metrics" in all_tags_lower or "analytics" in all_tags_lower:
            score += 1.0
    
    # Biggest challenge match (keyword matching in theme_tags)
    if onboarding.biggest_challenge:
        challenge_lower = onboarding.biggest_challenge.lower()
        book_theme_tags = set(book.theme_tags or [])
        
        # Map common challenges to themes
        challenge_theme_mapping = {
            "focus": ["productivity", "focus", "prioritization", "strategy"],
            "prioritization": ["productivity", "focus", "prioritization", "strategy"],
            "customer": ["marketing", "sales", "customer", "acquisition"],
            "marketing": ["marketing", "sales", "customer", "acquisition"],
            "sales": ["marketing", "sales", "customer", "acquisition"],
            "hiring": ["management", "leadership", "hiring", "team"],
            "delegation": ["management", "leadership", "hiring", "team"],
            "team": ["management", "leadership", "hiring", "team"],
            "growth": ["growth", "scaling", "expansion"],
            "scaling": ["growth", "scaling", "expansion"],
        }
        
        # Check for keyword matches
        matched_themes = []
        for keyword, themes in challenge_theme_mapping.items():
            if keyword in challenge_lower:
                matched_themes.extend(themes)
        
        if matched_themes:
            theme_matches = [theme for theme in matched_themes if any(theme in tt.lower() for tt in book_theme_tags)]
            if theme_matches:
                challenge_score = WEIGHTS["STAGE_FIT_STRONG"]
                score += challenge_score
                factors.challenge_fit = challenge_score
                reasons.append("Addresses your biggest challenge.")
    
    # Areas of business match
    if onboarding.areas_of_business:
        areas_lower = [a.lower() if isinstance(a, str) else str(a).lower() for a in onboarding.areas_of_business]
        book_functional_tags_lower = [ft.lower() for ft in (book.functional_tags or [])]
        for area in areas_lower:
            if any(area in ft or ft in area for ft in book_functional_tags_lower):
                area_score = 1.5
                score += area_score
                factors.areas_fit += area_score
                break  # Only count once
    
    # Insight-based matching
    promise_match = score_promise_match(book, onboarding)
    framework_match = score_framework_match(book, onboarding)
    outcome_match = score_outcome_match(book, onboarding)
    
    factors.promise_match = promise_match
    factors.framework_match = framework_match
    factors.outcome_match = outcome_match
    
    # Apply weighted insight matches to score
    score += W_PROMISE * promise_match
    score += W_FRAMEWORK * framework_match
    score += W_OUTCOME * outcome_match
    
    return score, reasons, factors


def get_personalized_recommendations(
    db: Session,
    user_id: UUID,
    limit: int = 10,
    debug: bool = False,
) -> List[RecommendationItem]:
    """
    Generate personalized recommendations using the new scoring helpers.
    
    Uses:
    - Direct book interactions (4-state)
    - Reading history (Goodreads)
    - Onboarding profile (stage, model, challenge)
    """
    user = _get_user(db, user_id)
    interactions = _get_user_interactions(db, user_id)
    history_entries = _get_user_reading_history(db, user_id)

    if not interactions and not history_entries:
        # No direct interactions or reading history yet – cold-start user.
        # We still proceed and let onboarding/profile-based scoring drive recommendations.
        logger.info(
            "Cold-start user %s: no interactions or reading history; "
            "falling back to onboarding/stage-based scoring only.",
            user_id,
        )

    # Load onboarding profile
    onboarding = (
        db.query(OnboardingProfile)
        .filter(OnboardingProfile.user_id == user_id)
        .one_or_none()
    )

    # Load candidate books – for now, all books.
    books: List[Book] = db.query(Book).all()
    if not books:
        raise NotEnoughSignalError("No books in catalog.")

    # Build lookup to map titles/authors from history to Book IDs
    title_author_to_id: Dict[Tuple[str, str], UUID] = {}
    for b in books:
        key = (b.title.strip().lower(), (b.author_name or "").strip().lower())
        title_author_to_id[key] = b.id

    # Direct interaction scores + blocked books
    interaction_scores, blocked_book_ids = _score_from_interactions(interactions)
    history_scores = _score_from_history(history_entries, title_author_to_id)
    user_ctx = _build_user_context(onboarding)

    total_scores: Dict[UUID, float] = defaultdict(float)
    book_reasons: Dict[UUID, List[str]] = defaultdict(list)
    book_score_factors: Dict[UUID, ScoreFactors] = {}

    for book in books:
        if book.id in blocked_book_ids:
            continue

        # Skip books the user already read (optional – adjust if you want to show re-reads)
        # Check if book is in liked/disliked interactions (already read)
        if book.id in {i.book_id for i in interactions if i.status in {UserBookStatus.READ_LIKED, UserBookStatus.READ_DISLIKED}}:
            continue

        # Start with interaction + history scores
        total_scores[book.id] += interaction_scores.get(book.id, 0.0)
        total_scores[book.id] += history_scores.get(book.id, 0.0)

        # Stage / model / challenge fit
        stage_fit_score, score_factors = _score_from_stage_fit(user_ctx, book, onboarding)
        total_scores[book.id] += stage_fit_score
        book_score_factors[book.id] = score_factors

        # Collect reasons for why_this_book explanation
        reasons: List[str] = []
        
        # Stage fit
        if stage_fit_score >= 3.0:
            business_stage = user_ctx.get("business_stage")
            if business_stage:
                reasons.append(f"is a strong fit for your current stage ({business_stage})")
        
        # Business model canon
        theme_tags = book.theme_tags or []
        functional_tags = book.functional_tags or []
        all_tags = theme_tags + functional_tags
        
        if "services_canon" in all_tags:
            reasons.append("was written specifically for service-based businesses")
        if "saas_canon" in all_tags:
            reasons.append("is tailored for SaaS and software founders")
        
        # Areas of business / challenge alignment
        challenge = (user_ctx.get("biggest_challenge") or "").lower()
        areas = [a.lower() for a in (user_ctx.get("areas_of_business") or [])]
        
        if "pricing" in functional_tags and ("price" in challenge or "pricing" in challenge):
            reasons.append("directly addresses your pricing and profitability challenges")
        if "marketing" in functional_tags and ("marketing" in areas or "leads" in challenge or "customer" in challenge):
            reasons.append("focuses on practical marketing and lead generation for your situation")
        if "operations" in functional_tags and ("operations" in areas or "systems" in challenge):
            reasons.append("helps you build systems and operations so the business can run without you")
        if "sales" in functional_tags and ("sales" in challenge or "client" in challenge):
            reasons.append("provides proven strategies for client acquisition and sales")
        
        if reasons:
            book_reasons[book.id] = reasons

    # Remove books with zero score if we have at least some positive scores
    # but keep a fallback so we don't end up empty.
    scored_items = [
        (book_id, score)
        for book_id, score in total_scores.items()
    ]

    # If everything is zero/negative, we still return top N; router can decide to fall back if needed.
    if not scored_items:
        raise NotEnoughSignalError("No scored items for this user.")

    # Check if user has a service-like or SaaS-like business model
    is_service_like = False
    is_saas_like = False
    if onboarding:
        business_model = (onboarding.business_model or "").strip().lower()
        is_service_like = business_model in SERVICE_LIKE_BUSINESS_MODELS
        is_saas_like = business_model in SAAS_LIKE_BUSINESS_MODELS

    # Build mapping for quick lookup
    books_by_id = {b.id: b for b in books}

    if not is_service_like and not is_saas_like:
        # Non-service, non-SaaS behavior: sort by score only
        scored_items.sort(key=lambda x: x[1], reverse=True)
        top_ids = [book_id for (book_id, _) in scored_items[:limit]]
    else:
        # We are either service-like OR SaaS-like; split into niche vs general pools
        services_pool: List[Tuple[UUID, float]] = []
        saas_pool: List[Tuple[UUID, float]] = []
        general_pool: List[Tuple[UUID, float]] = []
        
        for book_id, score in scored_items:
            book = books_by_id.get(book_id)
            if not book:
                continue
            if is_services_canon(book):
                services_pool.append((book_id, score))
            elif is_saas_canon(book):
                saas_pool.append((book_id, score))
            else:
                general_pool.append((book_id, score))
        
        services_pool.sort(key=lambda pair: pair[1], reverse=True)
        saas_pool.sort(key=lambda pair: pair[1], reverse=True)
        general_pool.sort(key=lambda pair: pair[1], reverse=True)
        
        target_niche = int(limit * 0.7)
        
        if is_service_like:
            niche_pool = services_pool
        else:  # is_saas_like
            niche_pool = saas_pool
        
        primary = niche_pool[:target_niche]
        remaining_slots = limit - len(primary)
        secondary = general_pool[:max(0, remaining_slots)]
        
        top_ids = [book_id for (book_id, _) in primary + secondary]
        
        # If catalog is small, fill any remaining slots with leftover books
        if len(top_ids) < limit:
            remaining = [
                pair
                for pair in (services_pool + saas_pool + general_pool)
                if pair[0] not in top_ids
            ]
            remaining.sort(key=lambda pair: pair[1], reverse=True)
            top_ids.extend([book_id for (book_id, _) in remaining[:limit - len(top_ids)]])

    recommendations: List[RecommendationItem] = []
    for idx, book_id in enumerate(top_ids):
        book = books_by_id.get(book_id)
        if not book:
            continue

        # Build why_this_book paragraph from score factors
        score_factors = book_score_factors.get(book_id, ScoreFactors())
        reasons = book_reasons.get(book_id, [])
        is_top = (idx == 0)
        why_this_book_text = build_why_this_book(score_factors, onboarding, book, is_top=is_top, reasons=reasons)
        
        # Build why_signals (reason chips)
        why_signals = _build_why_signals(onboarding, book)
        
        # Build purchase URL
        purchase_url = _build_purchase_url(book)

        relevancy_score = round(total_scores[book_id], 2)
        
        # Include debug fields if debug mode is enabled
        debug_fields = {}
        if debug:
            debug_fields = {
                "promise_match": score_factors.promise_match,
                "framework_match": score_factors.framework_match,
                "outcome_match": score_factors.outcome_match,
                "score_factors": {
                    "challenge_fit": score_factors.challenge_fit,
                    "stage_fit": score_factors.stage_fit,
                    "business_model_fit": score_factors.business_model_fit,
                    "areas_fit": score_factors.areas_fit,
                    "promise_match": score_factors.promise_match,
                    "framework_match": score_factors.framework_match,
                    "outcome_match": score_factors.outcome_match,
                    "total": relevancy_score,
                },
            }
        
        recommendations.append(
            RecommendationItem(
                book_id=str(book.id),
                title=book.title,
                subtitle=getattr(book, "subtitle", None),
                author_name=getattr(book, "author_name", None),
                score=relevancy_score,
                relevancy_score=relevancy_score,
                thumbnail_url=getattr(book, "thumbnail_url", None),
                cover_image_url=getattr(book, "cover_image_url", None),
                page_count=getattr(book, "page_count", None),
                published_year=getattr(book, "published_year", None),
                categories=book.categories,
                language=getattr(book, "language", None),
                isbn_10=getattr(book, "isbn_10", None),
                isbn_13=getattr(book, "isbn_13", None),
                average_rating=getattr(book, "average_rating", None),
                ratings_count=getattr(book, "ratings_count", None),
                theme_tags=book.theme_tags,
                functional_tags=book.functional_tags,
                business_stage_tags=book.business_stage_tags,
                purchase_url=purchase_url,
                why_this_book=why_this_book_text,
                why_recommended=None,  # Deprecated
                why_signals=why_signals if why_signals else None,
                **debug_fields,
            )
        )

    if not recommendations:
        raise NotEnoughSignalError("No recommendations after scoring/filtering.")

    # Ensure recommendations are sorted by relevancy_score descending
    recommendations.sort(key=lambda x: x.relevancy_score, reverse=True)

    return recommendations


def get_recommendations_from_payload(
    db: Session,
    payload: "OnboardingPayload",
    limit: int = 10,
    debug: bool = False,
) -> List[RecommendationItem]:
    """
    Generate recommendations from onboarding payload without requiring a user_id.
    This is used for preview recommendations before the user logs in.
    
    Uses only onboarding/profile-based scoring (no user interactions or reading history).
    """
    from app.schemas.onboarding import OnboardingPayload
    
    # Create a simple namespace object that mimics OnboardingProfile
    # This allows us to reuse the existing scoring logic
    class MockOnboardingProfile:
        def __init__(self, payload: OnboardingPayload):
            self.business_stage = payload.business_stage
            self.business_model = payload.business_model
            self.biggest_challenge = payload.biggest_challenge
            self.areas_of_business = payload.areas_of_business
            self.current_gross_revenue = payload.current_gross_revenue
            self.vision_6_12_months = payload.vision_6_12_months
            self.blockers = payload.blockers
    
    # Create mock onboarding profile from payload
    onboarding = MockOnboardingProfile(payload)
    
    # Load candidate books
    books: List[Book] = db.query(Book).all()
    if not books:
        raise NotEnoughSignalError("No books in catalog.")
    
    # Build user context from onboarding
    user_ctx = _build_user_context(onboarding)
    
    total_scores: Dict[UUID, float] = defaultdict(float)
    book_reasons: Dict[UUID, List[str]] = defaultdict(list)
    book_score_factors: Dict[UUID, ScoreFactors] = {}
    
    # Extract book preferences to block books user marked as not_interested
    blocked_book_ids: Set[UUID] = set()
    if payload.book_preferences:
        for pref in payload.book_preferences:
            if pref.status == "not_interested":
                # Try to find book by ID
                try:
                    from uuid import UUID as UUIDType
                    book_id = UUIDType(pref.book_id)
                    blocked_book_ids.add(book_id)
                except (ValueError, TypeError):
                    # If not a UUID, try to find by external_id
                    book = db.query(Book).filter(Book.external_id == pref.book_id).first()
                    if book:
                        blocked_book_ids.add(book.id)
    
    for book in books:
        if book.id in blocked_book_ids:
            continue
        
        # Only use stage/model/challenge fit (no interactions or history)
        stage_fit_score, score_factors = _score_from_stage_fit(user_ctx, book, onboarding)
        total_scores[book.id] += stage_fit_score
        book_score_factors[book.id] = score_factors
        
        # Collect reasons
        reasons: List[str] = []
        if stage_fit_score >= 3.0:
            business_stage = user_ctx.get("business_stage")
            if business_stage:
                reasons.append(f"is a strong fit for your current stage ({business_stage})")
        
        theme_tags = book.theme_tags or []
        functional_tags = book.functional_tags or []
        all_tags = theme_tags + functional_tags
        
        if "services_canon" in all_tags:
            reasons.append("was written specifically for service-based businesses")
        if "saas_canon" in all_tags:
            reasons.append("is tailored for SaaS and software founders")
        
        challenge = (user_ctx.get("biggest_challenge") or "").lower()
        areas = [a.lower() for a in (user_ctx.get("areas_of_business") or [])]
        
        if "pricing" in functional_tags and ("price" in challenge or "pricing" in challenge):
            reasons.append("directly addresses your pricing and profitability challenges")
        if "marketing" in functional_tags and ("marketing" in areas or "leads" in challenge or "customer" in challenge):
            reasons.append("focuses on practical marketing and lead generation for your situation")
        if "operations" in functional_tags and ("operations" in areas or "systems" in challenge):
            reasons.append("helps you build systems and operations so the business can run without you")
        if "sales" in functional_tags and ("sales" in challenge or "client" in challenge):
            reasons.append("provides proven strategies for client acquisition and sales")
        
        if reasons:
            book_reasons[book.id] = reasons
    
    # Remove books with zero score if we have at least some positive scores
    scored_items = [
        (book_id, score)
        for book_id, score in total_scores.items()
    ]
    
    if not scored_items:
        raise NotEnoughSignalError("No scored items for this payload.")
    
    # Check if business model is service-like or SaaS-like
    is_service_like = False
    is_saas_like = False
    if onboarding.business_model:
        business_model = onboarding.business_model.strip().lower()
        is_service_like = business_model in SERVICE_LIKE_BUSINESS_MODELS
        is_saas_like = business_model in SAAS_LIKE_BUSINESS_MODELS
    
    # Build mapping for quick lookup
    books_by_id = {b.id: b for b in books}
    
    if not is_service_like and not is_saas_like:
        # Non-service, non-SaaS behavior: sort by score only
        scored_items.sort(key=lambda x: x[1], reverse=True)
        top_ids = [book_id for (book_id, _) in scored_items[:limit]]
    else:
        # We are either service-like OR SaaS-like; split into niche vs general pools
        services_pool: List[Tuple[UUID, float]] = []
        saas_pool: List[Tuple[UUID, float]] = []
        general_pool: List[Tuple[UUID, float]] = []
        
        for book_id, score in scored_items:
            book = books_by_id.get(book_id)
            if not book:
                continue
            if is_services_canon(book):
                services_pool.append((book_id, score))
            elif is_saas_canon(book):
                saas_pool.append((book_id, score))
            else:
                general_pool.append((book_id, score))
        
        services_pool.sort(key=lambda pair: pair[1], reverse=True)
        saas_pool.sort(key=lambda pair: pair[1], reverse=True)
        general_pool.sort(key=lambda pair: pair[1], reverse=True)
        
        target_niche = int(limit * 0.7)
        
        if is_service_like:
            niche_pool = services_pool
        else:  # is_saas_like
            niche_pool = saas_pool
        
        primary = niche_pool[:target_niche]
        remaining_slots = limit - len(primary)
        secondary = general_pool[:max(0, remaining_slots)]
        
        top_ids = [book_id for (book_id, _) in primary + secondary]
        
        # If catalog is small, fill any remaining slots with leftover books
        if len(top_ids) < limit:
            remaining = [
                pair
                for pair in (services_pool + saas_pool + general_pool)
                if pair[0] not in top_ids
            ]
            remaining.sort(key=lambda pair: pair[1], reverse=True)
            top_ids.extend([book_id for (book_id, _) in remaining[:limit - len(top_ids)]])
    
    recommendations: List[RecommendationItem] = []
    for idx, book_id in enumerate(top_ids):
        book = books_by_id.get(book_id)
        if not book:
            continue
        
        # Build why_this_book paragraph from score factors
        score_factors = book_score_factors.get(book_id, ScoreFactors())
        reasons = book_reasons.get(book_id, [])
        is_top = (idx == 0)
        why_this_book_text = build_why_this_book(score_factors, onboarding, book, is_top=is_top, reasons=reasons)
        
        # Build why_signals (reason chips)
        why_signals = _build_why_signals(onboarding, book)
        
        # Build purchase URL
        purchase_url = _build_purchase_url(book)
        
        relevancy_score = round(total_scores[book_id], 2)
        
        # Include debug fields if debug mode is enabled
        debug_fields = {}
        if debug:
            debug_fields = {
                "promise_match": score_factors.promise_match,
                "framework_match": score_factors.framework_match,
                "outcome_match": score_factors.outcome_match,
                "score_factors": {
                    "challenge_fit": score_factors.challenge_fit,
                    "stage_fit": score_factors.stage_fit,
                    "business_model_fit": score_factors.business_model_fit,
                    "areas_fit": score_factors.areas_fit,
                    "promise_match": score_factors.promise_match,
                    "framework_match": score_factors.framework_match,
                    "outcome_match": score_factors.outcome_match,
                    "total": relevancy_score,
                },
            }
        
        recommendations.append(
            RecommendationItem(
                book_id=str(book.id),
                title=book.title,
                subtitle=getattr(book, "subtitle", None),
                author_name=getattr(book, "author_name", None),
                score=relevancy_score,
                relevancy_score=relevancy_score,
                thumbnail_url=getattr(book, "thumbnail_url", None),
                cover_image_url=getattr(book, "cover_image_url", None),
                page_count=getattr(book, "page_count", None),
                published_year=getattr(book, "published_year", None),
                categories=book.categories,
                language=getattr(book, "language", None),
                isbn_10=getattr(book, "isbn_10", None),
                isbn_13=getattr(book, "isbn_13", None),
                average_rating=getattr(book, "average_rating", None),
                ratings_count=getattr(book, "ratings_count", None),
                theme_tags=book.theme_tags,
                functional_tags=book.functional_tags,
                business_stage_tags=book.business_stage_tags,
                purchase_url=purchase_url,
                why_this_book=why_this_book_text,
                why_recommended=None,  # Deprecated
                why_signals=why_signals if why_signals else None,
                **debug_fields,
            )
        )
    
    if not recommendations:
        raise NotEnoughSignalError("No recommendations after scoring/filtering.")
    
    # Ensure recommendations are sorted by relevancy_score descending
    recommendations.sort(key=lambda x: x.relevancy_score, reverse=True)
    
    return recommendations


def get_recommendations_for_user(
    user_id: UUID,
    db: Session,
    limit: int = 10,
) -> List[RecommendationItem]:
    """
    Generate personalized book recommendations for a user using Rec Engine v1.5 scoring.
    
    Scoring structure:
    total_score = preference_score + history_score + stage_fit_score + category_boost
    
    Uses:
    - Onboarding profile (business_stage, business_model, biggest_challenge, areas_of_business)
    - Book interactions (4-state: READ_LIKED, READ_DISLIKED, INTERESTED, NOT_INTERESTED)
    - Reading history (Goodreads CSV: shelf, my_rating, date_read)
    
    Returns ranked list with explanations.
    """
    # Load user signals
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if not user:
        logger.warning("User %s not found in recommendation engine, falling back to generic recommendations", user_id)
        return get_generic_recommendations(db=db, limit=limit)
    
    onboarding = (
        db.query(OnboardingProfile)
        .filter(OnboardingProfile.user_id == user_id)
        .one_or_none()
    )
    
    # Load book interactions
    interactions = (
        db.query(UserBookInteraction)
        .filter(UserBookInteraction.user_id == user_id)
        .all()
    )
    
    liked_book_ids: Set[UUID] = {
        i.book_id for i in interactions if i.status == UserBookStatus.READ_LIKED
    }
    
    disliked_book_ids: Set[UUID] = {
        i.book_id for i in interactions if i.status == UserBookStatus.READ_DISLIKED
    }
    
    interested_book_ids: Set[UUID] = {
        i.book_id for i in interactions if i.status == UserBookStatus.INTERESTED
    }
    
    not_interested_book_ids: Set[UUID] = {
        i.book_id for i in interactions if i.status == UserBookStatus.NOT_INTERESTED
    }
    
    # Load reading history
    history_entries = (
        db.query(ReadingHistoryEntry)
        .filter(ReadingHistoryEntry.user_id == user_id)
        .all()
    )
    
    history_titles: Set[str] = {h.title.lower().strip() for h in history_entries}
    
    # Load all candidate books
    books = db.query(Book).all()
    
    if not books:
        return []
    
    # Compute score for each book
    def compute_total_score(book: Book) -> Tuple[float, str, bool, ScoreFactors, List[str]]:
        """
        Compute total score for a book.
        
        Returns: (total_score, why_recommended, should_filter_out, score_factors, reasons_list)
        """
        # FILTERING: Check for hard filters first
        # 1. NOT_INTERESTED - hard filter
        if book.id in not_interested_book_ids:
            return 0.0, "You marked this as not interested.", True, ScoreFactors(), []
        
        # 2. Already read (unless we want to allow re-reads)
        is_already_read = (
            book.id in liked_book_ids
            or book.id in disliked_book_ids
            or book.title.lower().strip() in history_titles
        )
        if is_already_read:
            # Filter out already-read books (can be changed to allow re-reads)
            return 0.0, "You've already read this book.", True, ScoreFactors(), []
        
        # 3. READ_DISLIKED with high similarity to other disliked books
        if book.id in disliked_book_ids:
            # Check similarity to other disliked books
            other_disliked = [b for b in books if b.id in disliked_book_ids and b.id != book.id]
            similar_count = sum(1 for db in other_disliked if _books_share_tags(book, db))
            if similar_count >= 2:  # Very similar to multiple disliked books
                return 0.0, "Very similar to books you disliked.", True, ScoreFactors(), []
        
        # SCORING: Calculate additive components
        preference_score, pref_reasons = _calculate_preference_score(
            book, interactions, books, liked_book_ids, disliked_book_ids
        )
        
        history_score, hist_reasons = _calculate_history_score(
            book, history_entries, books
        )
        
        stage_fit_score, stage_reasons, score_factors = _calculate_stage_fit_score(
            book, onboarding
        )
        
        category_boost, cat_reasons = _calculate_category_boost(
            book, history_entries, books
        )
        
        # Total score (additive)
        total_score = (
            preference_score
            + history_score
            + stage_fit_score
            + category_boost
        )
        
        # Combine reasons
        all_reasons = pref_reasons + hist_reasons + stage_reasons + cat_reasons
        if not all_reasons:
            all_reasons = ["Good fit based on your profile and reading history."]
        
        why = " ".join(all_reasons[:3])  # Limit to top 3 reasons
        
        return total_score, why, False, score_factors, all_reasons[:3]
    
    # Score all books
    candidates: List[Tuple[Book, float, str, ScoreFactors, List[str]]] = []
    for book in books:
        score, why, should_filter, factors, reasons = compute_total_score(book)
        if should_filter or score <= -5.0:  # Filter out negative scores below threshold
            continue
        candidates.append((book, score, why, factors, reasons))
    
    # Check if user has a service-like or SaaS-like business model
    is_service_like = False
    is_saas_like = False
    if onboarding:
        business_model = (onboarding.business_model or "").strip().lower()
        is_service_like = business_model in SERVICE_LIKE_BUSINESS_MODELS
        is_saas_like = business_model in SAAS_LIKE_BUSINESS_MODELS
    
    # Sort by score descending
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    # For service-like or SaaS-like users, apply 70/30 split (niche canon / general)
    if (is_service_like or is_saas_like) and candidates:
        services_candidates: List[Tuple[Book, float, str, ScoreFactors, List[str]]] = []
        saas_candidates: List[Tuple[Book, float, str, ScoreFactors, List[str]]] = []
        general_candidates: List[Tuple[Book, float, str, ScoreFactors, List[str]]] = []
        
        for book, score, why, factors, reasons in candidates:
            if is_services_canon(book):
                services_candidates.append((book, score, why, factors, reasons))
            elif is_saas_canon(book):
                saas_candidates.append((book, score, why, factors, reasons))
            else:
                general_candidates.append((book, score, why, factors, reasons))
        
        target_niche = int(limit * 0.7)
        
        if is_service_like:
            niche_candidates = services_candidates
        else:  # is_saas_like
            niche_candidates = saas_candidates
        
        primary = niche_candidates[:target_niche]
        remaining_slots = limit - len(primary)
        secondary = general_candidates[:max(0, remaining_slots)]
        
        candidates = primary + secondary
        
        # If catalog is small, fill any remaining slots with leftover books
        if len(candidates) < limit:
            remaining = [
                item
                for item in (services_candidates + saas_candidates + general_candidates)
                if item not in candidates
            ]
            remaining.sort(key=lambda x: x[1], reverse=True)
            candidates.extend(remaining[:limit - len(candidates)])
    
    # Calculate total signal count
    total_signal = len(interactions) + len(history_entries)
    
    # Handle "not enough signal" vs "logic bug" cases
    if not candidates:
        if total_signal >= SIGNAL_THRESHOLD:
            # User has enough signal but no results - this is a logic bug
            logger.warning(
                "User %s has %d signals (>= %d threshold) but no recommendations. "
                "This may indicate a logic bug in filtering/scoring.",
                user_id, total_signal, SIGNAL_THRESHOLD
            )
            return []  # Return empty - this is a bug case
        elif total_signal == 0 and not onboarding:
            # Truly zero signal: no interactions, no history, no onboarding
            raise NotEnoughSignalError(
                f"User {user_id} has no interactions, reading history, or onboarding data."
            )
        else:
            # User is very new / imported nothing - use curated fallback
            business_stage = onboarding.business_stage if onboarding else None
            business_model = onboarding.business_model if onboarding else None
            
            logger.info(
                "User %s has only %d signals (< %d threshold). "
                "Falling back to curated recommendations for stage=%s, model=%s",
                user_id, total_signal, SIGNAL_THRESHOLD, business_stage, business_model
            )
            
            return get_generic_recommendations(
                db=db,
                limit=limit,
                business_stage=business_stage,
                business_model=business_model,
            )
    
    # Take top N
    top = candidates[:limit]
    
    # Build RecommendationItem objects
    items: List[RecommendationItem] = []
    for idx, (book, score, why, factors, reasons) in enumerate(top):
        # Build why_this_book paragraph from score factors
        is_top = (idx == 0)
        why_this_book_text = build_why_this_book(factors, onboarding, book, is_top=is_top, reasons=reasons)
        
        # Build why_signals (reason chips)
        why_signals = _build_why_signals(onboarding, book)
        
        # Build purchase URL
        purchase_url = _build_purchase_url(book)
        
        relevancy_score = round(score, 2)
        items.append(
            RecommendationItem(
                book_id=str(book.id),
                title=book.title,
                subtitle=book.subtitle,
                author_name=book.author_name,
                score=relevancy_score,
                relevancy_score=relevancy_score,
                thumbnail_url=book.thumbnail_url,
                cover_image_url=book.cover_image_url,
                page_count=book.page_count,
                published_year=book.published_year,
                categories=book.categories,
                language=getattr(book, "language", None),
                isbn_10=getattr(book, "isbn_10", None),
                isbn_13=getattr(book, "isbn_13", None),
                average_rating=getattr(book, "average_rating", None),
                ratings_count=getattr(book, "ratings_count", None),
                theme_tags=book.theme_tags,
                functional_tags=book.functional_tags,
                business_stage_tags=book.business_stage_tags,
                purchase_url=purchase_url,
                why_this_book=why_this_book_text,
                why_recommended=None,  # Deprecated
                why_signals=why_signals if why_signals else None,
            )
        )
    
    # Ensure items are sorted by relevancy_score descending
    items.sort(key=lambda x: x.relevancy_score, reverse=True)
    
    return items
