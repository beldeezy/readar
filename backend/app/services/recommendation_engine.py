from typing import List, Tuple, Set, Optional, Dict, Any, TypedDict
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import ProgrammingError, OperationalError
import logging
from collections import Counter, defaultdict
from urllib.parse import quote_plus
from dataclasses import dataclass
from app.utils.timing import now_ms, log_elapsed
from app.core.config import settings
from app.models import (
    User,
    OnboardingProfile,
    Book,
    UserBookInteraction,
    UserBookStatus,
    ReadingHistoryEntry,
    BookDifficulty,
    UserBookStatusModel,
)
from app.schemas.recommendation import RecommendationItem

logger = logging.getLogger(__name__)


# Insight type definition (internal, not persisted)
class Insight(TypedDict):
    """Internal insight representation with key, weight, and reason."""
    key: str  # e.g. "business_stage:pre-revenue"
    weight: float  # e.g. 1.2
    reason: str  # Human-readable explanation


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

    for book in books:
        # Build purchase URL (generic recs don't have onboarding, so why_this_book can be None)
        purchase_url = _build_purchase_url(book)
        
        # Build why_signals (generic recs don't have onboarding, so signals will be limited)
        why_signals = _build_why_signals(None, book)
        
        # Build why_this_book for generic recs (no onboarding, so use empty factors)
        why_this_book_text = build_why_this_book_v2(None, book, None, None)
        
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


def _get_book_insight_tags(book: Book) -> Set[str]:
    """
    Extract insight-comparable tags from a book.
    
    Returns a set of insight keys that can be matched against user insights.
    Format: "prefix:value" (e.g., "business_stage:pre-revenue", "focus_area:marketing")
    """
    insight_tags: Set[str] = set()
    
    # business_stage_tags → "business_stage:*"
    if book.business_stage_tags:
        for tag in book.business_stage_tags:
            if tag:
                normalized = _normalize_tag_value(tag)
                insight_tags.add(f"business_stage:{normalized}")
    
    # functional_tags → "focus_area:*"
    if book.functional_tags:
        for tag in book.functional_tags:
            if tag:
                normalized = _normalize_tag_value(tag)
                insight_tags.add(f"focus_area:{normalized}")
    
    # theme_tags → "bottleneck:*"
    if book.theme_tags:
        for tag in book.theme_tags:
            if tag:
                normalized = _normalize_tag_value(tag)
                insight_tags.add(f"bottleneck:{normalized}")
    
    return insight_tags


def _normalize_tag_value(value: str) -> str:
    """Normalize tag value: lowercase, spaces → hyphens."""
    if not value:
        return ""
    return value.lower().strip().replace(" ", "-").replace("_", "-")


def _get_dominant_insight(matched_insights: List[Insight]) -> Optional[str]:
    """
    Determine the dominant insight for a book based on matched insights.
    
    Returns the key of the highest-weight matched insight, or None if no insights.
    """
    if not matched_insights:
        return None
    
    # Sort by weight descending and return the key of the highest-weight insight
    sorted_insights = sorted(matched_insights, key=lambda x: x["weight"], reverse=True)
    return sorted_insights[0]["key"]


def _apply_diversity_penalty(
    scored_items: List[Tuple[UUID, float]],
    book_dominant_insights: Dict[UUID, Optional[str]],
) -> Tuple[List[Tuple[UUID, float]], Dict[UUID, Dict[str, Any]]]:
    """
    Apply diversity penalty to discourage over-representation of the same dominant insight.
    
    Algorithm:
    - Sort books by score (descending)
    - Iterate in order, maintaining seen_insight_counts
    - For each book, if dominant_insight has been seen before, apply penalty:
      score -= 0.15 * seen_insight_counts[dominant_insight]
    - First occurrence is untouched
    - Never reduce score below zero
    
    Returns:
    - Re-ranked scored_items with diversity penalties applied
    - Debug info dict mapping book_id to diversity info
    """
    # Sort by score descending
    sorted_items = sorted(scored_items, key=lambda x: x[1], reverse=True)
    
    seen_insight_counts: Dict[str, int] = {}
    diversity_info: Dict[UUID, Dict[str, Any]] = {}
    re_ranked_items: List[Tuple[UUID, float]] = []
    
    for book_id, score in sorted_items:
        dominant_insight = book_dominant_insights.get(book_id)
        
        diversity_penalty = 0.0
        diversity_rank_index = None
        
        if dominant_insight is None:
            # No penalty for books without dominant insight
            diversity_rank_index = None
        else:
            # Check if we've seen this insight before
            count = seen_insight_counts.get(dominant_insight, 0)
            
            if count >= 1:
                # Apply penalty: 0.15 * count
                diversity_penalty = 0.15 * count
                diversity_rank_index = count  # 0 = first, 1 = second, 2 = third, etc.
            else:
                # First occurrence - no penalty
                diversity_rank_index = 0
            
            # Increment counter for next time
            seen_insight_counts[dominant_insight] = count + 1
        
        # Apply penalty (never go below zero)
        adjusted_score = max(0.0, score - diversity_penalty)
        re_ranked_items.append((book_id, adjusted_score))
        
        # Store debug info
        if dominant_insight is not None:
            diversity_info[book_id] = {
                "dominant_insight": dominant_insight,
                "diversity_penalty_applied": round(diversity_penalty, 2),
                "diversity_rank_index": diversity_rank_index,
            }
        else:
            diversity_info[book_id] = {
                "dominant_insight": None,
                "diversity_penalty_applied": 0.0,
                "diversity_rank_index": None,
            }
    
    return re_ranked_items, diversity_info


def _build_user_insights(onboarding: Optional[OnboardingProfile]) -> List[Insight]:
    """
    Convert onboarding profile into a list of weighted insights.
    
    Rules:
    - business_stage → weight 1.2, key: "business_stage:{value}"
    - business_model → weight 1.0, key: "business_model:{normalized_value}"
    - areas_of_business (array) → each weight 0.8, key: "focus_area:{value}"
    - biggest_challenge → weight 1.1, key: "bottleneck:{normalized_value}"
    
    Returns empty list if onboarding is None or all fields are empty.
    This function must NEVER throw.
    """
    insights: List[Insight] = []
    
    try:
        if not onboarding:
            return insights
        
        # business_stage → weight 1.2
        if onboarding.business_stage:
            stage_value = (
                onboarding.business_stage.value 
                if hasattr(onboarding.business_stage, 'value') 
                else str(onboarding.business_stage)
            )
            if stage_value:
                normalized = _normalize_tag_value(stage_value)
                insights.append({
                    "key": f"business_stage:{normalized}",
                    "weight": 1.2,
                    "reason": f"at the {stage_value.replace('-', ' ').title()} stage"
                })
        
        # business_model → weight 1.0
        if onboarding.business_model:
            normalized = _normalize_tag_value(onboarding.business_model)
            if normalized:
                insights.append({
                    "key": f"business_model:{normalized}",
                    "weight": 1.0,
                    "reason": f"building a {onboarding.business_model} business"
                })
        
        # areas_of_business (array) → each weight 0.8
        if onboarding.areas_of_business:
            for area in onboarding.areas_of_business:
                if area:
                    normalized = _normalize_tag_value(area)
                    if normalized:
                        insights.append({
                            "key": f"focus_area:{normalized}",
                            "weight": 0.8,
                            "reason": f"focused on {area.replace('_', ' ').title()}"
                        })
        
        # biggest_challenge → weight 1.1
        if onboarding.biggest_challenge:
            normalized = _normalize_tag_value(onboarding.biggest_challenge)
            if normalized:
                insights.append({
                    "key": f"bottleneck:{normalized}",
                    "weight": 1.1,
                    "reason": f"facing {onboarding.biggest_challenge}"
                })
    
    except Exception as e:
        # This function must NEVER throw - log and return empty list
        logger.warning(f"Error building user insights: {e}", exc_info=True)
        return []
    
    return insights


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
    matched_insights: Optional[List[Insight]] = None
) -> str:
    """
    Build a single compelling paragraph explaining why a book is recommended.
    
    Uses Hook → Bridge → Action structure:
    - Hook: user bottleneck (from user profile + score factors or matched insights)
    - Bridge: book promise + optional framework (from book.promise and book.core_frameworks)
    - Action: one concrete outcome (from book.outcomes)
    
    If matched_insights are provided, uses top 2-3 insights by weight to generate explanation.
    Falls back to factor-based copy when insight fields are missing.
    Outputs one paragraph (2-4 sentences max).
    No generic CTA.
    """
    parts: List[str] = []
    
    # Check if book has insight fields
    has_promise = book.promise and book.promise.strip()
    has_frameworks = book.core_frameworks and isinstance(book.core_frameworks, list) and len(book.core_frameworks) > 0
    has_outcomes = book.outcomes and isinstance(book.outcomes, list) and len(book.outcomes) > 0
    has_insights = has_promise or has_frameworks or has_outcomes
    
    if not user_profile:
        # Fallback for users without onboarding
        if has_promise:
            return book.promise.strip()
        return "This is a solid foundational pick to build clarity and execution momentum."
    
    # If we have matched insights, use them to build the explanation
    if matched_insights:
        # Sort by weight (descending) and take top 2-3
        sorted_insights = sorted(matched_insights, key=lambda x: x["weight"], reverse=True)[:3]
        
        if sorted_insights:
            # Build hook from top insights (top 2-3 by weight)
            hook_parts = []
            for insight in sorted_insights[:2]:  # Use top 2 for hook
                reason = insight["reason"]
                # Clean up reason text - remove "You're" prefix if present
                if reason.startswith("You're "):
                    reason = reason[7:]  # Remove "You're "
                elif reason.startswith("you're "):
                    reason = reason[7:]  # Remove "you're "
                
                hook_parts.append(reason)
            
            if hook_parts:
                # Combine hook parts naturally
                if len(hook_parts) == 1:
                    parts.append(f"You're {hook_parts[0]}, making this especially relevant right now.")
                else:
                    # Join with "and" for multiple insights
                    combined = " and ".join(hook_parts)
                    parts.append(f"You're {combined}, making this especially relevant right now.")
            
            # BRIDGE: Book promise + optional framework
            if has_promise:
                promise_text = book.promise.strip()
                if has_frameworks:
                    framework = book.core_frameworks[0]
                    parts.append(f"{promise_text}, introducing the {framework} framework.")
                else:
                    parts.append(promise_text + ".")
            elif has_frameworks:
                framework = book.core_frameworks[0]
                parts.append(f"This book introduces the {framework} framework.")
            
            # ACTION: One concrete outcome
            if has_outcomes:
                outcome = book.outcomes[0]
                parts.append(f"You'll walk away with {outcome.lower()}.")
            
            # Final formatting: one paragraph (2-4 sentences)
            result = " ".join(parts).strip()
            if result:
                return result
    
    # Fallback to original logic if no matched insights or if matched insights didn't produce good output
    # Format business stage for display
    business_stage = None
    if user_profile.business_stage:
        business_stage = (
            user_profile.business_stage.value 
            if hasattr(user_profile.business_stage, 'value') 
            else str(user_profile.business_stage)
        )
        business_stage = humanize(business_stage).replace("-", " ").title()
    
    # HOOK: User bottleneck (from user profile + score factors)
    hook_parts = []
    
    if factors.challenge_fit > 0 and user_profile.biggest_challenge:
        challenge_text = humanize(user_profile.biggest_challenge)
        hook_parts.append(f"You're facing {challenge_text}")
    
    if factors.stage_fit > 0 and business_stage:
        if hook_parts:
            hook_parts.append(f"at the {business_stage} stage")
        else:
            hook_parts.append(f"You're at the {business_stage} stage")
    
    if hook_parts:
        hook = " ".join(hook_parts) + "."
        parts.append(hook)
    elif factors.areas_fit > 0 and user_profile.areas_of_business:
        areas = [humanize(a) for a in (user_profile.areas_of_business[:1] or [])]
        if areas:
            parts.append(f"You're focused on {areas[0]}.")
    
    # BRIDGE: Book promise + optional framework
    if has_promise:
        # Use promise as the bridge
        promise_text = book.promise.strip()
        if has_frameworks:
            # Mention one framework by name (max 1 per description)
            framework = book.core_frameworks[0]
            # Combine promise and framework naturally
            parts.append(f"{promise_text}, introducing the {framework} framework.")
        else:
            parts.append(promise_text + ".")
    elif has_frameworks:
        # If no promise, use framework as the bridge
        framework = book.core_frameworks[0]
        parts.append(f"This book introduces the {framework} framework.")
    else:
        # Fallback: factor-based bridge
        if factors.business_model_fit > 0 and user_profile.business_model:
            model_text = humanize(user_profile.business_model)
            parts.append(f"It's especially relevant if you're building a {model_text}.")
        elif factors.areas_fit > 0 and user_profile.areas_of_business:
            areas = [humanize(a) for a in (user_profile.areas_of_business[:2] or [])]
            if areas:
                parts.append(f"It will sharpen your thinking in {', '.join(areas)}—the areas most likely to unlock momentum next.")
    
    # ACTION: One concrete outcome
    if has_outcomes:
        outcome = book.outcomes[0]  # Use one concrete outcome
        parts.append(f"You'll walk away with {outcome.lower()}.")
    elif not has_insights:
        # Fallback: generic action only if no insights at all
        if factors.stage_fit > 0 or factors.challenge_fit > 0:
            parts.append("This should help you prioritize the right moves.")
    
    # Final formatting: one paragraph (2-4 sentences)
    result = " ".join(parts).strip()
    
    # If none of the factors hit (rare), provide a neutral reason
    if not result:
        if has_promise:
            return book.promise.strip()
        return "This is a solid foundational pick to build clarity and execution momentum."
    
    return result


def build_why_this_book_v2(
    user_ctx: Optional[Dict[str, Any]],
    book: Book,
    matched_insights: Optional[List[Insight]] = None,
    dominant_insight: Optional[str] = None,
) -> str:
    """
    Build a concise, personal "Why this book?" explanation.
    
    Requirements:
    - Limit to 1-2 sentences
    - Explicitly reference: the user's stated challenge OR business stage OR what the book helps them stop doing
    - Remove generic phrases and tag lists
    - Keep all logic deterministic. No new data sources.
    
    Priority order:
    1. If matched_insights exist: use top insight + book promise (personalized to user challenge/stage)
    2. Else if user_ctx has biggest_challenge: reference challenge + book promise
    3. Else if user_ctx has business_stage: reference stage + book promise
    4. Else: simple fallback with book promise
    
    Returns 1-2 sentences, max 240 chars. Never shows raw tags.
    
    Args:
        user_ctx: User context dict (from _build_user_context) or None
        book: Book model instance
        matched_insights: List of matched insights (from scoring)
        dominant_insight: Dominant insight key (from _get_dominant_insight) or None
    """
    parts: List[str] = []
    
    # Helper: Normalize stage display
    def normalize_stage(stage_value: str) -> str:
        """Convert stage value to display format."""
        stage_map = {
            "idea": "Idea",
            "pre-revenue": "Pre-revenue",
            "pre_revenue": "Pre-revenue",
            "early-revenue": "Early revenue",
            "early_revenue": "Early revenue",
            "scaling": "Scaling",
        }
        normalized = stage_value.lower().replace("_", "-")
        return stage_map.get(normalized, stage_value.replace("-", " ").title())
    
    # Helper: Extract value from insight key
    def extract_insight_value(insight_key: str) -> str:
        """Extract the value part from an insight key like 'business_stage:pre-revenue'."""
        if ":" in insight_key:
            return insight_key.split(":", 1)[1]
        return insight_key
    
    # Helper: Convert insight to plain English phrase
    def insight_to_phrase(insight: Insight) -> str:
        """Convert an insight to a human-readable phrase."""
        key = insight["key"]
        reason = insight.get("reason", "")
        
        # If reason exists, convert it to the right format based on insight type
        if reason:
            if key.startswith("business_stage:"):
                # Reason is like "at the Pre Revenue stage" -> "You're in the Pre-revenue stage"
                if reason.startswith("at the "):
                    stage_part = reason[7:]  # "Pre Revenue stage"
                    # Normalize the stage part
                    stage_value = extract_insight_value(key)
                    stage_display = normalize_stage(stage_value)
                    return f"You're in the {stage_display} stage"
                return f"You're in the {reason}."
            elif key.startswith("business_model:"):
                # Reason is like "building a saas business" -> "This fits a SaaS-style business"
                if reason.startswith("building a "):
                    model_part = reason[10:]  # "saas business"
                    model_display = model_part.replace(" business", "").title()
                    return f"This fits a {model_display}-style business"
                return f"This fits a {reason}."
            elif key.startswith("focus_area:"):
                # Reason is like "focused on Marketing" -> "It strengthens your Marketing"
                if reason.startswith("focused on "):
                    area_part = reason[11:]  # "Marketing"
                    return f"It strengthens your {area_part}"
                return f"It strengthens your {reason}."
            elif key.startswith("bottleneck:"):
                # Reason is like "facing pricing challenges" -> "It helps with Pricing Challenges"
                if reason.startswith("facing "):
                    bottleneck_part = reason[7:]  # "pricing challenges"
                    # Clean up: title case, trim to ~6 words
                    words = bottleneck_part.split()[:6]
                    bottleneck_display = " ".join(words).title()
                    return f"It helps with {bottleneck_display}"
                return f"It helps with {reason}."
            # If reason doesn't match expected patterns, use it as-is
            return reason
        
        # Fallback: parse from key if no reason
        if key.startswith("business_stage:"):
            value = extract_insight_value(key)
            stage_display = normalize_stage(value)
            return f"You're in the {stage_display} stage"
        elif key.startswith("business_model:"):
            value = extract_insight_value(key)
            model_display = value.replace("-", " ").replace("_", " ").title()
            return f"This fits a {model_display}-style business"
        elif key.startswith("focus_area:"):
            value = extract_insight_value(key)
            area_display = value.replace("-", " ").replace("_", " ").title()
            return f"It strengthens your {area_display}"
        elif key.startswith("bottleneck:"):
            value = extract_insight_value(key)
            # Clean up bottleneck: remove punctuation, trim to ~6 words
            words = value.replace("-", " ").replace("_", " ").split()[:6]
            bottleneck_display = " ".join(words).title()
            return f"It helps with {bottleneck_display}"
        return ""
    
    # Helper: Get book promise clause
    def get_book_promise() -> Optional[str]:
        """Get a single book promise clause if available."""
        if book.promise and book.promise.strip():
            promise = book.promise.strip()
            # Remove trailing period if present, we'll add it later
            if promise.endswith("."):
                promise = promise[:-1]
            return promise
        return None
    
    # Helper: Get book category/functional tag for fallback
    def get_book_category_fallback() -> Optional[str]:
        """Get a single category or functional tag for fallback."""
        if book.categories and len(book.categories) > 0:
            return book.categories[0]
        if book.functional_tags and len(book.functional_tags) > 0:
            return book.functional_tags[0]
        return None
    
    # PRIORITY A: If matched_insights exist
    if matched_insights and len(matched_insights) > 0:
        # Sort by weight (descending) and take top 1
        sorted_insights = sorted(matched_insights, key=lambda x: x.get("weight", 0.0), reverse=True)
        top_insight = sorted_insights[0]
        
        # Get user context for personalization
        biggest_challenge = user_ctx.get("biggest_challenge") if user_ctx else None
        business_stage = user_ctx.get("business_stage") if user_ctx else None
        
        # Build personalized opening based on insight type
        insight_key = top_insight.get("key", "")
        if insight_key.startswith("bottleneck:") and biggest_challenge:
            # Reference the user's stated challenge directly
            challenge_text = biggest_challenge.strip()
            # Capitalize first letter
            if challenge_text:
                challenge_text = challenge_text[0].upper() + challenge_text[1:] if len(challenge_text) > 1 else challenge_text.upper()
            parts.append(f"Since you're facing {challenge_text.lower()}, this book")
        elif insight_key.startswith("business_stage:") and business_stage:
            # Reference the user's business stage
            stage_display = normalize_stage(business_stage)
            parts.append(f"As you're in the {stage_display} stage, this book")
        else:
            # Use insight phrase as opening
            phrase = insight_to_phrase(top_insight)
            if phrase:
                # Make it more personal - convert "You're" to "Since you're" or similar
                if phrase.startswith("You're "):
                    phrase = "Since " + phrase.lower()
                elif phrase.startswith("This "):
                    phrase = "This book " + phrase[5:].lower()
                parts.append(phrase)
        
        # Add book promise - make it actionable
        promise = get_book_promise()
        if promise:
            # Ensure promise references what it helps them stop doing or achieve
            promise_lower = promise.lower()
            if "help" not in promise_lower and "stop" not in promise_lower and "avoid" not in promise_lower:
                # Add a connector if promise doesn't already have action words
                if parts:
                    parts[-1] = parts[-1].rstrip(".") + " helps you " + promise.lower()
                else:
                    parts.append(f"This book helps you {promise.lower()}")
            else:
                if parts:
                    parts[-1] = parts[-1].rstrip(".") + ", " + promise.lower()
                else:
                    parts.append(promise)
        else:
            # Fallback if no promise
            if not parts:
                parts.append("This book directly addresses your current needs.")
        
        # Build result - limit to 1-2 sentences
        result = " ".join(parts).strip()
        if result:
            # Enforce length limit (1-2 sentences, ~240 chars max)
            if len(result) > 240:
                # Truncate at last sentence boundary before 240 chars
                sentences = result.split(". ")
                if len(sentences) > 1:
                    # Take first sentence if it's reasonable length
                    first_sentence = sentences[0] + "."
                    if len(first_sentence) <= 240:
                        result = first_sentence
                    else:
                        # Truncate first sentence
                        truncated = first_sentence[:237]
                        last_space = truncated.rfind(" ")
                        if last_space > 180:
                            result = truncated[:last_space] + "..."
                        else:
                            result = truncated + "..."
                else:
                    # Single sentence - truncate at word boundary
                    truncated = result[:237]
                    last_space = truncated.rfind(" ")
                    if last_space > 180:
                        result = truncated[:last_space] + "..."
                    else:
                        result = truncated + "..."
            # Clean up: remove double spaces, ensure ends with period
            result = " ".join(result.split())
            if not result.endswith("."):
                result += "."
            return result
    
    # PRIORITY B: Reference user's biggest challenge directly
    if user_ctx:
        biggest_challenge = user_ctx.get("biggest_challenge")
        if biggest_challenge:
            challenge_text = biggest_challenge.strip()
            # Capitalize first letter
            if challenge_text:
                challenge_text = challenge_text[0].upper() + challenge_text[1:] if len(challenge_text) > 1 else challenge_text.upper()
            parts.append(f"Since you're facing {challenge_text.lower()}, this book")
            
            # Add book promise
            promise = get_book_promise()
            if promise:
                promise_lower = promise.lower()
                if "help" not in promise_lower and "stop" not in promise_lower:
                    parts[-1] = parts[-1].rstrip(".") + " helps you " + promise.lower()
                else:
                    parts[-1] = parts[-1].rstrip(".") + ", " + promise.lower()
            else:
                parts[-1] = parts[-1] + " directly addresses this challenge."
            
            result = " ".join(parts).strip()
            if result and len(result) <= 240:
                if not result.endswith("."):
                    result += "."
                return result
    
    # PRIORITY C: Reference business stage
    if user_ctx:
        business_stage = user_ctx.get("business_stage")
        if business_stage:
            stage_display = normalize_stage(business_stage)
            parts.append(f"As you're in the {stage_display} stage, this book")
            
            # Add book promise
            promise = get_book_promise()
            if promise:
                promise_lower = promise.lower()
                if "help" not in promise_lower and "stop" not in promise_lower:
                    parts[-1] = parts[-1].rstrip(".") + " helps you " + promise.lower()
                else:
                    parts[-1] = parts[-1].rstrip(".") + ", " + promise.lower()
            else:
                parts[-1] = parts[-1] + " is tailored to your current needs."
            
            result = " ".join(parts).strip()
            if result:
                if len(result) > 240:
                    truncated = result[:237]
                    last_space = truncated.rfind(" ")
                    if last_space > 180:
                        result = truncated[:last_space] + "..."
                    else:
                        result = truncated + "..."
                result = " ".join(result.split())
                if not result.endswith("."):
                    result += "."
                return result
    
    # Ultimate fallback
    promise = get_book_promise()
    if promise:
        result = promise + "."
        if len(result) > 240:
            truncated = result[:237]
            last_space = truncated.rfind(" ")
            if last_space > 180:
                result = truncated[:last_space] + "..."
            else:
                result = truncated + "..."
        return result
    
    return "This is a solid foundational pick to build clarity and execution momentum."


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
    # Timing: start of function
    t0 = now_ms() if settings.DEBUG else None
    
    # A) Load user + onboarding profile
    if settings.DEBUG:
        t1 = log_elapsed(t0, f"user={user_id} phase=load_user_profile", logger.debug)
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
    
    if settings.DEBUG:
        t2 = log_elapsed(t1, f"user={user_id} phase=load_onboarding", logger.debug)

    # B) Fetch user book status once per request
    # Defensive: handle missing table gracefully (schema drift protection)
    if settings.DEBUG:
        t_status_start = now_ms()
    try:
        user_book_statuses = (
            db.query(UserBookStatusModel)
            .filter(UserBookStatusModel.user_id == user_id)
            .all()
        )
    except (ProgrammingError, OperationalError) as e:
        # Table doesn't exist yet - treat as empty status map
        # This allows onboarding/recommendations to work even if migrations haven't run
        error_msg = str(e).lower()
        if "does not exist" in error_msg or "relation" in error_msg and "does not exist" in error_msg:
            # CRITICAL: Rollback the aborted transaction before continuing
            # Without this, subsequent queries will fail with InFailedSqlTransaction
            db.rollback()
            logger.warning(
                "user_book_status table not found for user %s. "
                "Treating as empty status map. Run migrations: alembic upgrade head",
                user_id
            )
            user_book_statuses = []
        else:
            # Re-raise if it's a different database error
            raise
    
    if settings.DEBUG:
        status_count = len(user_book_statuses)
        t_status_elapsed = now_ms() - t_status_start
        logger.debug(f"user={user_id} phase=user_book_status query={t_status_elapsed:.2f}ms count={status_count}")
        t3 = now_ms()
    
    # Build dict mapping book_id (as string) to status
    # Note: UserBookStatusModel.book_id is String, Book.id is UUID
    book_status_map: Dict[str, str] = {
        status_obj.book_id: status_obj.status
        for status_obj in user_book_statuses
    }

    # C) Load candidate books – for now, all books.
    if settings.DEBUG:
        t_books_start = now_ms()
    books: List[Book] = db.query(Book).all()
    if settings.DEBUG:
        books_count = len(books)
        t_books_elapsed = now_ms() - t_books_start
        logger.debug(f"user={user_id} phase=fetch_books query={t_books_elapsed:.2f}ms count={books_count}")
        t4 = now_ms()
    
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
    
    # Build user insights from onboarding profile
    user_insights = _build_user_insights(onboarding)

    total_scores: Dict[UUID, float] = defaultdict(float)
    book_reasons: Dict[UUID, List[str]] = defaultdict(list)
    book_score_factors: Dict[UUID, ScoreFactors] = {}
    # Track original scores and adjustments for debug
    original_scores: Dict[UUID, float] = {}
    status_adjustments: Dict[UUID, Dict[str, Any]] = {}
    # Track matched insights for each book (for debug and "why this book")
    book_matched_insights: Dict[UUID, List[Insight]] = defaultdict(list)
    # Track base scores before insight adjustments (for debug)
    base_scores: Dict[UUID, float] = {}

    # D) Scoring loop
    # NOTE: User feedback is collected in v1 but not applied to recommendation scoring yet.
    # Feedback is stored in user_book_feedback table for future use.
    if settings.DEBUG:
        t_scoring_start = now_ms()
    scored_count = 0
    for book in books:
        if book.id in blocked_book_ids:
            continue

        # Skip books the user already read (optional – adjust if you want to show re-reads)
        # Check if book is in liked/disliked interactions (already read)
        if book.id in {i.book_id for i in interactions if i.status in {UserBookStatus.READ_LIKED, UserBookStatus.READ_DISLIKED}}:
            continue

        # Check user_book_status for exclusion rules
        book_id_str = str(book.id)
        status = book_status_map.get(book_id_str)
        
        # Hard exclusion rules: skip books with "not_for_me" or "read_disliked"
        if status in ("not_for_me", "read_disliked"):
            continue

        # Start with interaction + history scores
        total_scores[book.id] += interaction_scores.get(book.id, 0.0)
        total_scores[book.id] += history_scores.get(book.id, 0.0)

        # Stage / model / challenge fit
        stage_fit_score, score_factors = _score_from_stage_fit(user_ctx, book, onboarding)
        total_scores[book.id] += stage_fit_score
        book_score_factors[book.id] = score_factors
        
        # Store base score before insight and status adjustments
        base_scores[book.id] = total_scores[book.id]
        
        # Store original score BEFORE status adjustments (for debug tracking)
        # This must happen before status adjustments so we can reference it safely
        original_scores[book.id] = total_scores[book.id]
        
        # Apply score adjustments based on user_book_status
        if status == "interested":
            # Store score before adjustment
            score_before_adjustment = total_scores[book.id]
            total_scores[book.id] += 0.3
            # Safe access: original_score should already be set above, but use .get() as fallback
            original_score = original_scores.get(book.id)
            if original_score is None:
                # Fallback: use the score we just stored before adjustment
                original_score = score_before_adjustment
                logger.warning("original_scores missing key for book_id=%s user_id=%s, using score_before_adjustment as fallback", book.id, user_id)
            status_adjustments[book.id] = {
                "status": status,
                "adjustment": 0.3,
                "original_score": original_score,
                "adjusted_score": total_scores[book.id],
            }
        elif status == "read_liked":
            # Store score before adjustment
            score_before_adjustment = total_scores[book.id]
            total_scores[book.id] += 0.5
            # Safe access: original_score should already be set above, but use .get() as fallback
            original_score = original_scores.get(book.id)
            if original_score is None:
                # Fallback: use the score we just stored before adjustment
                original_score = score_before_adjustment
                logger.warning("original_scores missing key for book_id=%s user_id=%s, using score_before_adjustment as fallback", book.id, user_id)
            status_adjustments[book.id] = {
                "status": status,
                "adjustment": 0.5,
                "original_score": original_score,
                "adjusted_score": total_scores[book.id],
            }
        
        # Apply insight-weighted scoring
        # Match user insights against book insight tags
        book_insight_tags = _get_book_insight_tags(book)
        insight_score_total = 0.0
        
        for insight in user_insights:
            if insight["key"] in book_insight_tags:
                # Exact prefix match found
                insight_score_total += insight["weight"]
                book_matched_insights[book.id].append(insight)
        
        # Add insight score to total
        total_scores[book.id] += insight_score_total

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
        
        scored_count += 1

    if settings.DEBUG:
        t_scoring_elapsed = now_ms() - t_scoring_start
        logger.debug(f"user={user_id} phase=scoring_loop elapsed={t_scoring_elapsed:.2f}ms scored={scored_count}")
        t5 = now_ms()

    # Remove books with zero score if we have at least some positive scores
    # but keep a fallback so we don't end up empty.
    scored_items = [
        (book_id, score)
        for book_id, score in total_scores.items()
    ]

    # If everything is zero/negative, we still return top N; router can decide to fall back if needed.
    if not scored_items:
        raise NotEnoughSignalError("No scored items for this user.")

    # Determine dominant insight for each book
    book_dominant_insights: Dict[UUID, Optional[str]] = {}
    for book_id in total_scores.keys():
        matched_insights = book_matched_insights.get(book_id, [])
        book_dominant_insights[book_id] = _get_dominant_insight(matched_insights)

    # Apply diversity penalty before sorting/limiting
    scored_items, diversity_info = _apply_diversity_penalty(
        scored_items, book_dominant_insights
    )
    
    # Update total_scores with diversity-adjusted scores for final ranking
    for book_id, adjusted_score in scored_items:
        total_scores[book_id] = adjusted_score

    # Check if user has a service-like or SaaS-like business model
    is_service_like = False
    is_saas_like = False
    if onboarding:
        business_model = (onboarding.business_model or "").strip().lower()
        is_service_like = business_model in SERVICE_LIKE_BUSINESS_MODELS
        is_saas_like = business_model in SAAS_LIKE_BUSINESS_MODELS

    # Build mapping for quick lookup
    books_by_id = {b.id: b for b in books}

    # E) Sorting/limiting (now using diversity-adjusted scores)
    if settings.DEBUG:
        t_sorting_start = now_ms()
    
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
    
    if settings.DEBUG:
        t_sorting_elapsed = now_ms() - t_sorting_start
        logger.debug(f"user={user_id} phase=sorting_limiting elapsed={t_sorting_elapsed:.2f}ms")
        t6 = now_ms()

    recommendations: List[RecommendationItem] = []
    for book_id in top_ids:
        book = books_by_id.get(book_id)
        if not book:
            continue
        
        # Defensive check: ensure book has expected attributes
        if not hasattr(book, "id"):
            logger.error("Expected book object with .id attribute, got: %r (type: %s)", book, type(book))
            continue

        # Build why_this_book paragraph from score factors and matched insights
        score_factors = book_score_factors.get(book_id, ScoreFactors())
        matched_insights = book_matched_insights.get(book_id, [])
        dominant_insight = book_dominant_insights.get(book_id)
        why_this_book_text = build_why_this_book_v2(user_ctx, book, matched_insights, dominant_insight)
        
        # Build why_signals (reason chips)
        why_signals = _build_why_signals(onboarding, book)
        
        # Build purchase URL
        purchase_url = _build_purchase_url(book)

        relevancy_score = round(total_scores[book_id], 2)
        
        # Calculate insight score total for debug
        insight_score_total = sum(insight["weight"] for insight in matched_insights)
        base_score = base_scores.get(book_id, original_scores.get(book_id, 0.0))
        
        # Get diversity info for this book
        book_diversity_info = diversity_info.get(book_id, {})
        
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
                "matched_insights": [
                    {
                        "key": insight["key"],
                        "weight": insight["weight"],
                        "reason": insight["reason"]
                    }
                    for insight in matched_insights
                ],
                "insight_score_total": round(insight_score_total, 2),
                "base_score": round(base_score, 2),
                "final_score": relevancy_score,
                "dominant_insight": book_diversity_info.get("dominant_insight"),
                "diversity_penalty_applied": book_diversity_info.get("diversity_penalty_applied", 0.0),
                "diversity_rank_index": book_diversity_info.get("diversity_rank_index"),
            }
            
            # Add user_book_status debug trace if available
            book_id_str = str(book_id)
            status = book_status_map.get(book_id_str)
            if status:
                adjustment_info = status_adjustments.get(book_id)
                if adjustment_info:
                    debug_fields["user_book_status"] = {
                        "book_id": book_id_str,
                        "original_score": adjustment_info["original_score"],
                        "adjusted_score": adjustment_info["adjusted_score"],
                        "applied_status": adjustment_info["status"],
                        "adjustment": adjustment_info["adjustment"],
                    }
                else:
                    # Status exists but no adjustment (e.g., excluded books won't reach here)
                    debug_fields["user_book_status"] = {
                        "book_id": book_id_str,
                        "applied_status": status,
                        "note": "Status present but no score adjustment applied",
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
    
    # Final timing summary
    if settings.DEBUG and t0 is not None:
        total_elapsed = now_ms() - t0
        logger.debug(
            f"user={user_id} phase=total elapsed={total_elapsed:.2f}ms "
            f"limit={limit} debug={debug} returned={len(recommendations)}"
        )

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
    
    # Build user insights from onboarding profile
    user_insights = _build_user_insights(onboarding)
    
    total_scores: Dict[UUID, float] = defaultdict(float)
    book_reasons: Dict[UUID, List[str]] = defaultdict(list)
    book_score_factors: Dict[UUID, ScoreFactors] = {}
    # Track matched insights for each book (for debug and "why this book")
    book_matched_insights: Dict[UUID, List[Insight]] = defaultdict(list)
    # Track base scores before insight adjustments (for debug)
    base_scores: Dict[UUID, float] = {}
    
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
        
        # Store base score before insight adjustments
        base_scores[book.id] = total_scores[book.id]
        
        # Apply insight-weighted scoring
        book_insight_tags = _get_book_insight_tags(book)
        insight_score_total = 0.0
        
        for insight in user_insights:
            if insight["key"] in book_insight_tags:
                # Exact prefix match found
                insight_score_total += insight["weight"]
                book_matched_insights[book.id].append(insight)
        
        # Add insight score to total
        total_scores[book.id] += insight_score_total
        
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
    
    # Determine dominant insight for each book
    book_dominant_insights: Dict[UUID, Optional[str]] = {}
    for book_id in total_scores.keys():
        matched_insights = book_matched_insights.get(book_id, [])
        book_dominant_insights[book_id] = _get_dominant_insight(matched_insights)

    # Apply diversity penalty before sorting/limiting
    scored_items, diversity_info = _apply_diversity_penalty(
        scored_items, book_dominant_insights
    )
    
    # Update total_scores with diversity-adjusted scores for final ranking
    for book_id, adjusted_score in scored_items:
        total_scores[book_id] = adjusted_score
    
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
    for book_id in top_ids:
        book = books_by_id.get(book_id)
        if not book:
            continue
        
        # Build why_this_book paragraph from score factors and matched insights
        score_factors = book_score_factors.get(book_id, ScoreFactors())
        matched_insights = book_matched_insights.get(book_id, [])
        dominant_insight = book_dominant_insights.get(book_id)
        why_this_book_text = build_why_this_book_v2(user_ctx, book, matched_insights, dominant_insight)
        
        # Build why_signals (reason chips)
        why_signals = _build_why_signals(onboarding, book)
        
        # Build purchase URL
        purchase_url = _build_purchase_url(book)
        
        relevancy_score = round(total_scores[book_id], 2)
        
        # Calculate insight score total for debug
        insight_score_total = sum(insight["weight"] for insight in matched_insights)
        base_score = base_scores.get(book_id, relevancy_score - insight_score_total)
        
        # Get diversity info for this book
        book_diversity_info = diversity_info.get(book_id, {})
        
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
                "matched_insights": [
                    {
                        "key": insight["key"],
                        "weight": insight["weight"],
                        "reason": insight["reason"]
                    }
                    for insight in matched_insights
                ],
                "insight_score_total": round(insight_score_total, 2),
                "base_score": round(base_score, 2),
                "final_score": relevancy_score,
                "dominant_insight": book_diversity_info.get("dominant_insight"),
                "diversity_penalty_applied": book_diversity_info.get("diversity_penalty_applied", 0.0),
                "diversity_rank_index": book_diversity_info.get("diversity_rank_index"),
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
    def compute_total_score(book: Book) -> Tuple[float, str, bool, ScoreFactors]:
        """
        Compute total score for a book.
        
        Returns: (total_score, why_recommended, should_filter_out, score_factors)
        """
        # FILTERING: Check for hard filters first
        # 1. NOT_INTERESTED - hard filter
        if book.id in not_interested_book_ids:
            return 0.0, "You marked this as not interested.", True, ScoreFactors()
        
        # 2. Already read (unless we want to allow re-reads)
        is_already_read = (
            book.id in liked_book_ids
            or book.id in disliked_book_ids
            or book.title.lower().strip() in history_titles
        )
        if is_already_read:
            # Filter out already-read books (can be changed to allow re-reads)
            return 0.0, "You've already read this book.", True, ScoreFactors()
        
        # 3. READ_DISLIKED with high similarity to other disliked books
        if book.id in disliked_book_ids:
            # Check similarity to other disliked books
            other_disliked = [b for b in books if b.id in disliked_book_ids and b.id != book.id]
            similar_count = sum(1 for db in other_disliked if _books_share_tags(book, db))
            if similar_count >= 2:  # Very similar to multiple disliked books
                return 0.0, "Very similar to books you disliked.", True, ScoreFactors()
        
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
        
        return total_score, why, False, score_factors
    
    # Score all books
    candidates: List[Tuple[Book, float, str, ScoreFactors]] = []
    for book in books:
        score, why, should_filter, factors = compute_total_score(book)
        if should_filter or score <= -5.0:  # Filter out negative scores below threshold
            continue
        candidates.append((book, score, why, factors))
    
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
        services_candidates: List[Tuple[Book, float, str, ScoreFactors]] = []
        saas_candidates: List[Tuple[Book, float, str, ScoreFactors]] = []
        general_candidates: List[Tuple[Book, float, str, ScoreFactors]] = []
        
        for book, score, why, factors in candidates:
            if is_services_canon(book):
                services_candidates.append((book, score, why, factors))
            elif is_saas_canon(book):
                saas_candidates.append((book, score, why, factors))
            else:
                general_candidates.append((book, score, why, factors))
        
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
    # Build user_ctx for v2 function
    user_ctx = _build_user_context(onboarding)
    for book, score, why, factors in top:
        # Build why_this_book paragraph from score factors
        why_this_book_text = build_why_this_book_v2(user_ctx, book, None, None)
        
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
