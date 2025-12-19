"""
Book status endpoints for persisting user book status and powering Profile dashboard.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import logging

from app.database import get_db
from app.core.auth import get_current_user
from app.models import User, Book, UserBookStatusModel
from app.utils.instrumentation import log_event

logger = logging.getLogger(__name__)
router = APIRouter(tags=["book-status"])


class SetBookStatusRequest(BaseModel):
    """Request body for setting book status."""
    book_id: str
    status: str  # one of: interested | read_liked | read_disliked | not_for_me
    request_id: Optional[str] = None
    position: Optional[int] = None
    source: Optional[str] = "recommendations"


class BookStatusResponse(BaseModel):
    """Response for book status."""
    book_id: str
    status: str
    updated_at: str
    title: Optional[str] = None
    author_name: Optional[str] = None
    
    class Config:
        from_attributes = True


@router.post("/book-status", status_code=status.HTTP_200_OK)
async def set_book_status(
    payload: SetBookStatusRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Set or update the latest book status for the current user.
    
    This endpoint:
    1. Upserts into user_book_status (MUST succeed)
    2. Logs an event (best-effort, must never fail the request)
    """
    # Validate status
    valid_statuses = ["interested", "read_liked", "read_disliked", "not_for_me"]
    if payload.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
        )
    
    # Map frontend "not_interested" to backend "not_for_me" if needed
    # (This handles any legacy frontend calls)
    status_value = payload.status
    if status_value == "not_interested":
        status_value = "not_for_me"
    
    try:
        # Upsert into user_book_status
        existing = db.query(UserBookStatusModel).filter(
            and_(
                UserBookStatusModel.user_id == user.id,
                UserBookStatusModel.book_id == payload.book_id
            )
        ).first()
        
        if existing:
            # Update existing
            existing.status = status_value
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
        else:
            # Create new
            new_status = UserBookStatusModel(
                user_id=user.id,
                book_id=payload.book_id,
                status=status_value,
            )
            db.add(new_status)
            db.commit()
            db.refresh(new_status)
        
        # Log event (best-effort, must never fail the request)
        try:
            # Use a separate session for event logging to ensure it doesn't interfere
            # with the main transaction
            from app.database import SessionLocal
            event_db = SessionLocal()
            try:
                log_event(
                    db=event_db,
                    event_name="book_status_changed",
                    user_id=user.id,
                    properties={
                        "book_id": payload.book_id,
                        "status": status_value,
                        "request_id": payload.request_id,
                        "position": payload.position,
                        "source": payload.source or "recommendations",
                    },
                    request_id=payload.request_id,
                )
                event_db.commit()
            except Exception as e:
                # Swallow event logging errors - never break the request
                logger.warning(
                    "Failed to log book_status_changed event: book_id=%s, user_id=%s, error=%s",
                    payload.book_id,
                    user.id,
                    str(e),
                    exc_info=True,
                )
                event_db.rollback()
            finally:
                event_db.close()
        except Exception as e:
            # Extra safety net - log and continue
            logger.warning(
                "Event logging setup failed: %s",
                str(e),
                exc_info=True,
            )
        
        return {"ok": True}
        
    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to set book status: book_id=%s, user_id=%s, error=%s",
            payload.book_id,
            user.id,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set book status",
        )


@router.get("/profile/book-status", response_model=List[BookStatusResponse])
async def get_book_status_list(
    status_filter: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get list of books with their statuses for the Profile dashboard.
    
    Query params:
    - status: optional filter (interested|read_liked|read_disliked|not_for_me)
    
    Returns array of book statuses, optionally joined with book titles/authors if available.
    """
    query = db.query(UserBookStatusModel).filter(
        UserBookStatusModel.user_id == user.id
    )
    
    # Apply status filter if provided
    if status_filter:
        # Map "not_for_me" to handle both frontend and backend naming
        if status_filter == "not_interested":
            status_filter = "not_for_me"
        query = query.filter(UserBookStatusModel.status == status_filter)
    
    # Order by most recently updated
    query = query.order_by(UserBookStatusModel.updated_at.desc())
    
    statuses = query.all()
    
    # Try to join with books table to get title/author
    results = []
    for status_obj in statuses:
        # Try to find the book
        book = None
        try:
            # Try UUID first
            try:
                book_uuid = UUID(status_obj.book_id)
                book = db.query(Book).filter(Book.id == book_uuid).first()
            except (ValueError, TypeError):
                # If not a UUID, try external_id or other fields
                book = db.query(Book).filter(
                    (Book.external_id == status_obj.book_id) | 
                    (Book.id == status_obj.book_id)
                ).first()
        except Exception as e:
            logger.debug("Could not find book for book_id=%s: %s", status_obj.book_id, str(e))
        
        result = BookStatusResponse(
            book_id=status_obj.book_id,
            status=status_obj.status,
            updated_at=status_obj.updated_at.isoformat() if status_obj.updated_at else "",
            title=book.title if book else None,
            author_name=book.author_name if book else None,
        )
        results.append(result)
    
    return results

