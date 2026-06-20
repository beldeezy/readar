"""
Book status endpoints for persisting user book status and powering Profile dashboard.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, cast, func, String
from pydantic import BaseModel
from typing import Optional, List, Literal
from uuid import UUID
from datetime import datetime
import logging

from app.database import get_db
from app.core.auth import get_current_user
from app.models import User, Book, UserBookStatusModel, UserBookInteraction, ReadingHistoryEntry
from app.utils.instrumentation import log_event

logger = logging.getLogger(__name__)
router = APIRouter(tags=["book-status"])

# Rating we record when a book is marked read in-app (Goodreads scale 1–5).
READ_RATING = {"read_liked": 5.0, "read_disliked": 2.0}


def _lookup_book(db: Session, book_id: str) -> Optional[Book]:
    """Resolve a status book_id (UUID or external id) to a catalog Book."""
    try:
        return db.query(Book).filter(Book.id == UUID(book_id)).first()
    except (ValueError, TypeError):
        # Not a UUID, so it can only be an external id. Comparing the UUID
        # Book.id column against a non-UUID string errors on Postgres.
        return db.query(Book).filter(Book.external_id == book_id).first()


def _record_read_in_history(db: Session, user_id, book: Book, status_value: str) -> None:
    """
    Upsert a 'read' ReadingHistoryEntry for a book the user marked read in-app,
    so it counts toward total_books_read / reading confidence / the 50-book goal.
    Keyed on (user_id, title, author) to merge with any Goodreads import.
    """
    title = book.title
    author = book.author_name or ""
    rating = READ_RATING.get(status_value)
    existing = (
        db.query(ReadingHistoryEntry)
        .filter(
            ReadingHistoryEntry.user_id == user_id,
            func.lower(ReadingHistoryEntry.title) == title.lower(),
            func.lower(cast(ReadingHistoryEntry.author, String)) == author.lower(),
        )
        .first()
    )
    if existing:
        existing.shelf = "read"
        existing.my_rating = rating
        existing.catalog_book_id = book.id
    else:
        db.add(
            ReadingHistoryEntry(
                user_id=user_id,
                title=title,
                author=author,
                my_rating=rating,
                shelf="read",
                source="readar",
                catalog_book_id=book.id,
            )
        )


def _regen_reading_profile(user_id) -> None:
    """Background task: rebuild the user's reading profile from history."""
    from app.database import SessionLocal
    from app.services.reading_profile_service import generate_reading_profile

    db = SessionLocal()
    try:
        generate_reading_profile(db=db, user_id=user_id)
    except Exception as e:
        logger.warning("Reading profile regen failed for user_id=%s: %s", user_id, e)
    finally:
        db.close()


class SetBookStatusRequest(BaseModel):
    """Request body for setting book status."""
    book_id: str
    status: str  # one of: interested | currently_reading | read_liked | read_disliked | not_for_me
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
    background_tasks: BackgroundTasks,
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
    valid_statuses = ["interested", "currently_reading", "read_liked", "read_disliked", "not_for_me"]
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

        # "currently_reading" is a transient shelf state and must not feed the
        # recommendation engine. If the book had a prior graded/interest
        # interaction, clear it so the Knowledge Map / scoring stays accurate.
        if status_value == "currently_reading":
            _delete_interaction(db, user.id, payload.book_id)
            db.commit()

        # Marking a book read feeds the user's reading history (powers the
        # "Books read" count, reading confidence, and the 50-book goal), then
        # rebuilds the reading profile in the background.
        if status_value in READ_RATING:
            book = _lookup_book(db, payload.book_id)
            if book is not None:
                try:
                    _record_read_in_history(db, user.id, book, status_value)
                    db.commit()
                    background_tasks.add_task(_regen_reading_profile, user.id)
                except Exception as e:
                    db.rollback()
                    logger.warning(
                        "Failed to record reading history for book_id=%s: %s",
                        payload.book_id, e,
                    )

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


def _delete_interaction(db: Session, user_id, book_id: str) -> None:
    """
    Delete the UserBookInteraction row for this user/book if present.

    UserBookInteraction.book_id is a UUID FK, while book status uses a free-form
    string id, so only attempt deletion when the id parses as a UUID.
    """
    try:
        book_uuid = UUID(book_id)
    except (ValueError, TypeError):
        return
    db.query(UserBookInteraction).filter(
        and_(
            UserBookInteraction.user_id == user_id,
            UserBookInteraction.book_id == book_uuid,
        )
    ).delete(synchronize_session=False)


@router.delete("/book-status/{book_id}", status_code=status.HTTP_200_OK)
async def delete_book_status(
    book_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Remove a book from the user's shelves entirely.

    Deletes the dashboard status row AND any recommendation-engine interaction
    for the book, so the two stores can never drift out of sync.
    """
    try:
        db.query(UserBookStatusModel).filter(
            and_(
                UserBookStatusModel.user_id == user.id,
                UserBookStatusModel.book_id == book_id,
            )
        ).delete(synchronize_session=False)
        _delete_interaction(db, user.id, book_id)
        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to delete book status: book_id=%s, user_id=%s, error=%s",
            book_id, user.id, str(e), exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove book from shelves",
        )


StatusLiteral = Literal["interested", "currently_reading", "read_liked", "read_disliked", "not_for_me", "not_interested"]

@router.get("/profile/book-status", response_model=List[BookStatusResponse])
async def get_book_status_list(
    status: Optional[StatusLiteral] = Query(default=None),
    status_filter_legacy: Optional[str] = Query(default=None, alias="status_filter"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get list of books with their statuses for the Profile dashboard.
    
    Query params:
    - status: optional filter (interested|currently_reading|read_liked|read_disliked|not_for_me|not_interested)
    - status_filter: legacy alias for status (backwards compatibility)
    
    Returns array of book statuses, optionally joined with book titles/authors if available.
    """
    query = db.query(UserBookStatusModel).filter(
        UserBookStatusModel.user_id == user.id
    )
    
    # Apply status filter if provided (support both new 'status' and legacy 'status_filter')
    status_val = status or status_filter_legacy
    if status_val:
        # Map "not_interested" to "not_for_me" to handle both frontend and backend naming
        if status_val == "not_interested":
            status_val = "not_for_me"
        query = query.filter(UserBookStatusModel.status == status_val)
    
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
                # Not a UUID -> can only be an external id. (Comparing the UUID
                # Book.id column to a non-UUID string errors on Postgres.)
                book = db.query(Book).filter(Book.external_id == status_obj.book_id).first()
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

