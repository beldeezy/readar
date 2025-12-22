"""
Feedback router for accepting user feedback on book recommendations.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from uuid import UUID
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.auth import get_current_user
from app.models import User
from app.services.feedback_service import submit_feedback
from app.utils.instrumentation import log_event_best_effort

router = APIRouter()


class FeedbackRequest(BaseModel):
    book_id: str
    action: str  # One of: save_interested, read_liked, read_disliked, not_for_me


class FeedbackResponse(BaseModel):
    success: bool


@router.post("/feedback", response_model=FeedbackResponse)
async def post_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accept feedback from the UI safely and non-fatally.
    
    Always returns { "success": true } even if persistence fails.
    """
    # Validate action
    valid_actions = {"save_interested", "read_liked", "read_disliked", "not_for_me"}
    if request.action not in valid_actions:
        # Still return success to avoid breaking UI
        return FeedbackResponse(success=True)
    
    # Validate book_id is a valid UUID
    try:
        book_id_uuid = UUID(request.book_id)
    except ValueError:
        # Invalid UUID format - return success anyway
        return FeedbackResponse(success=True)
    
    # Call feedback service
    try:
        submit_feedback(
            db=db,
            user_id=current_user.id,
            book_id=book_id_uuid,
            action=request.action,
        )
        
        # Log instrumentation events (best-effort, non-blocking)
        try:
            log_event_best_effort(
                event_name="feedback_submitted",
                user_id=current_user.id,
                properties={
                    "book_id": request.book_id,
                    "action": request.action,
                },
            )
            log_event_best_effort(
                event_name="feedback_action",
                user_id=current_user.id,
                properties={
                    "action": request.action,
                },
            )
        except Exception:
            # Silently ignore instrumentation failures
            pass
    except Exception as e:
        # Never throw exceptions - always return success
        pass
    
    # Always return success
    return FeedbackResponse(success=True)

