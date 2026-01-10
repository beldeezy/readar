"""
Service for logging recommendation events.

Tracks user interactions with recommendations for analytics and feedback loops.
"""
from uuid import UUID
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models import RecommendationEvent
import logging

logger = logging.getLogger(__name__)


def log_recommendation_event(
    db: Session,
    user_id: UUID,
    book_id: UUID,
    event_type: str,
    recommendation_session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log a recommendation event to the database.

    Args:
        db: Database session
        user_id: User UUID
        book_id: Book UUID
        event_type: Event type (recommendation_shown, save_interested, mark_read_liked, mark_read_disliked, not_for_me)
        recommendation_session_id: Optional session/request ID linking to the recommendation response
        metadata: Optional metadata dict (rank, score, dominant_insight, etc.)

    Returns:
        None (logs errors but doesn't raise exceptions to avoid breaking the main flow)
    """
    try:
        event = RecommendationEvent(
            user_id=user_id,
            book_id=book_id,
            event_type=event_type,
            recommendation_session_id=recommendation_session_id,
            metadata=metadata,
        )
        db.add(event)
        db.commit()
    except Exception as e:
        # Log error but don't raise to avoid breaking the main flow
        logger.warning(
            f"Failed to log recommendation event: user_id={user_id}, book_id={book_id}, "
            f"event_type={event_type}, error={str(e)}"
        )
        db.rollback()
