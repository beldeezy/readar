"""
Feedback service for handling user book feedback actions.

This service centralizes feedback logic with zero recommendation side-effects.
Feedback is collected in v1 but not applied to recommendation scoring yet.
"""
import logging
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import UserBookFeedback, FeedbackSentiment, FeedbackState

logger = logging.getLogger(__name__)


def submit_feedback(
    db: Session,
    user_id: UUID,
    book_id: UUID,
    action: str,
) -> bool:
    """
    Submit user feedback for a book.
    
    Maps actions deterministically:
    - save_interested → sentiment=positive, state=interested
    - read_liked → sentiment=positive, state=read_completed
    - read_disliked → sentiment=negative, state=read_completed
    - not_for_me → sentiment=negative, state=dismissed
    
    Args:
        db: Database session
        user_id: User UUID
        book_id: Book UUID
        action: One of: save_interested, read_liked, read_disliked, not_for_me
    
    Returns:
        True if feedback was persisted, False otherwise
    
    Rules:
        - Silently ignores duplicate feedback for the same (user_id, book_id, state)
        - Never throws an exception outward
        - No recommendation scoring logic here
    """
    # Map action to sentiment and state
    action_map = {
        "save_interested": (FeedbackSentiment.POSITIVE, FeedbackState.INTERESTED),
        "read_liked": (FeedbackSentiment.POSITIVE, FeedbackState.READ_COMPLETED),
        "read_disliked": (FeedbackSentiment.NEGATIVE, FeedbackState.READ_COMPLETED),
        "not_for_me": (FeedbackSentiment.NEGATIVE, FeedbackState.DISMISSED),
    }
    
    if action not in action_map:
        logger.warning(f"Unknown feedback action: {action}")
        return False
    
    sentiment, state = action_map[action]
    
    try:
        # Check if feedback already exists for this (user_id, book_id, state)
        existing = db.query(UserBookFeedback).filter(
            UserBookFeedback.user_id == user_id,
            UserBookFeedback.book_id == book_id,
            UserBookFeedback.state == state,
        ).first()
        
        if existing:
            # Silently ignore duplicate feedback
            logger.debug(f"Duplicate feedback ignored: user_id={user_id}, book_id={book_id}, state={state}")
            return True
        
        # Create new feedback record
        feedback = UserBookFeedback(
            user_id=user_id,
            book_id=book_id,
            sentiment=sentiment,
            state=state,
            source="recommendations_v1",
        )
        db.add(feedback)
        db.commit()
        logger.debug(f"Feedback persisted: user_id={user_id}, book_id={book_id}, action={action}")
        return True
        
    except IntegrityError as e:
        # Handle race condition where duplicate is inserted between check and insert
        db.rollback()
        logger.debug(f"Duplicate feedback (race condition): user_id={user_id}, book_id={book_id}, state={state}")
        return True
    except Exception as e:
        # Never throw exceptions outward - log and return False
        db.rollback()
        logger.warning(
            f"Failed to persist feedback: user_id={user_id}, book_id={book_id}, action={action}, error={e}",
            exc_info=True,
        )
        return False

