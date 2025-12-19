"""
Event logging endpoints for client-side events.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
import logging

from app.database import get_db
from app.core.auth import get_current_user
from app.models import User
from app.utils.instrumentation import log_event_best_effort

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["events"])


class RecommendationClickRequest(BaseModel):
    """Request body for recommendation click event."""
    book_id: str
    request_id: str
    position: int
    session_id: Optional[str] = None


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Optional user dependency - returns None if not authenticated."""
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


@router.post("/recommendation-click", status_code=status.HTTP_204_NO_CONTENT)
async def log_recommendation_click(
    payload: RecommendationClickRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Log a recommendation click event.
    
    This endpoint accepts click events from the frontend and logs them.
    It never throws errors for missing optional fields - validation is minimal.
    Authentication is optional - if user is authenticated, we log their user_id.
    Uses best-effort logging that never breaks the request path.
    """
    user = get_optional_user(request, db)
    user_id = user.id if user else None
    
    # Best-effort logging - never raises exceptions
    log_event_best_effort(
        event_name="recommendation_clicked",
        user_id=user_id,
        properties={
            "book_id": payload.book_id,
            "request_id": payload.request_id,
            "position": payload.position,
        },
        request_id=payload.request_id,
        session_id=payload.session_id,
    )
    
    return None


@router.get("/recent")
async def get_recent_events(
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Dev-only endpoint to view recent events (for debugging).
    """
    from app.models import EventLog
    
    events = db.query(EventLog).order_by(EventLog.created_at.desc()).limit(limit).all()
    
    return {
        "events": [
            {
                "id": str(event.id),
                "created_at": event.created_at.isoformat() if event.created_at else None,
                "user_id": str(event.user_id) if event.user_id else None,
                "event_name": event.event_name,
                "properties": event.properties,
                "request_id": event.request_id,
                "session_id": event.session_id,
            }
            for event in events
        ]
    }

