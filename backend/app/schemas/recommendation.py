from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.schemas.book import BookResponse


class RecommendationItem(BaseModel):
    book_id: str
    title: str
    subtitle: Optional[str] = None
    author_name: Optional[str] = None
    score: float
    relevancy_score: float  # Same as score, for clarity and explicit sorting
    thumbnail_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    page_count: Optional[int] = None
    published_year: Optional[int] = None
    categories: Optional[List[str]] = None
    language: Optional[str] = None
    isbn_10: Optional[str] = None
    isbn_13: Optional[str] = None
    average_rating: Optional[float] = None
    ratings_count: Optional[int] = None
    theme_tags: Optional[List[str]] = None
    functional_tags: Optional[List[str]] = None
    business_stage_tags: Optional[List[str]] = None
    purchase_url: Optional[str] = None
    why_this_book: str  # Always present, single compelling paragraph explaining why recommended
    why_recommended: Optional[List[str]] = None  # Deprecated: use why_this_book instead
    why_signals: Optional[List[Dict[str, str]]] = None
    # Debug fields (only included when debug=true)
    promise_match: Optional[float] = None
    framework_match: Optional[float] = None
    outcome_match: Optional[float] = None
    score_factors: Optional[Dict[str, float]] = None  # Full score factors breakdown
    matched_insights: Optional[List[Dict[str, Any]]] = None  # Matched insights with key, weight, reason
    insight_score_total: Optional[float] = None  # Total score contribution from insights
    base_score: Optional[float] = None  # Score before insight and status adjustments
    final_score: Optional[float] = None  # Final score after all adjustments
    dominant_insight: Optional[str] = None  # Dominant insight key (highest-weight matched insight)
    diversity_penalty_applied: Optional[float] = None  # Diversity penalty applied to discourage over-representation
    diversity_rank_index: Optional[int] = None  # Rank index for this dominant insight (0 = first, 1 = second, etc.)


class RecommendationRequest(BaseModel):
    max_results: Optional[int] = 10


class RecommendationsResponse(BaseModel):
    """Response wrapper for recommendations that includes request_id for event tracking."""
    request_id: str
    items: List[RecommendationItem]
    debug: Optional[Dict[str, Any]] = None  # Only included when DEBUG=true

