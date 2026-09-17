"""Private, reader-authored ideas with durable book and goal context."""
from datetime import datetime, timezone
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database import get_db
from app.models import Book, OnboardingProfile, ReadingTakeaway, User
from app.schemas.reading_takeaways import TakeawayCreate, TakeawayList, TakeawayResponse, TakeawayUpdate

router = APIRouter(prefix="/reading/takeaways", tags=["reading-takeaways"])
logger = logging.getLogger(__name__)
TEXT_FIELDS = ("takeaway", "action_text", "goal_context")


def _owned(db, user_id, takeaway_id, lock=False):
    query = db.query(ReadingTakeaway).filter_by(id=takeaway_id, user_id=user_id)
    if lock:
        query = query.populate_existing().with_for_update()
    entry = query.first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Takeaway not found.")
    return entry


def _suggested_goal(profile):
    if not profile:
        return ""
    for field in ("future_vision", "vision_6_12_months", "primary_problems", "biggest_challenge"):
        value = (getattr(profile, field, None) or "").strip()
        # Never silently truncate a reader's context into a different meaning.
        if value and len(value) <= 2000:
            return value
    return ""


def _save(db, operation):
    try:
        entry = operation()
        db.flush()
        response = TakeawayResponse.model_validate(entry)
        db.commit()
        return response
    except HTTPException:
        db.rollback()
        raise
    except Exception as error:
        db.rollback()
        # SQL exception traces may contain note text in bound parameters.
        logger.error("Could not save reading takeaway (%s)", type(error).__name__)
        raise HTTPException(status_code=500, detail="We couldn't save your takeaway. Your draft is still here; please try again.")


@router.get("", response_model=TakeawayList)
def list_takeaways(before: UUID | None = None, limit: int = Query(default=50, ge=1, le=100),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(ReadingTakeaway).filter_by(user_id=user.id)
    if before:
        anchor = _owned(db, user.id, before)
        query = query.filter(or_(ReadingTakeaway.created_at < anchor.created_at,
                                 and_(ReadingTakeaway.created_at == anchor.created_at, ReadingTakeaway.id < anchor.id)))
    rows = query.order_by(ReadingTakeaway.created_at.desc(), ReadingTakeaway.id.desc()).limit(limit + 1).all()
    profile = db.query(OnboardingProfile).filter_by(user_id=user.id).first()
    return TakeawayList(items=[TakeawayResponse.model_validate(row) for row in rows[:limit]],
                        suggested_goal=_suggested_goal(profile), next_cursor=rows[limit - 1].id if len(rows) > limit else None)


@router.get("/{takeaway_id}", response_model=TakeawayResponse)
def get_takeaway(takeaway_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _owned(db, user.id, takeaway_id)


@router.post("", response_model=TakeawayResponse)
def create_takeaway(payload: TakeawayCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    def operation():
        book = db.get(Book, payload.book_id)
        if book is None:
            raise HTTPException(status_code=404, detail="Book not found.")
        values = payload.model_dump()
        db.execute(insert(ReadingTakeaway).values(**values, user_id=user.id, book_title=book.title,
                   book_author=book.author_name or "").on_conflict_do_nothing(constraint="uq_reading_takeaway_user_client"))
        entry = db.query(ReadingTakeaway).filter_by(user_id=user.id, client_id=payload.client_id).populate_existing().with_for_update().one()
        if entry.book_id != payload.book_id or any(getattr(entry, field) != getattr(payload, field) for field in TEXT_FIELDS):
            raise HTTPException(status_code=409, detail={
                "message": "This draft was already saved with different text. Load the saved version before editing it.",
                "existing_id": str(entry.id),
            })
        return entry
    return _save(db, operation)


@router.put("/{takeaway_id}", response_model=TakeawayResponse)
def update_takeaway(takeaway_id: UUID, payload: TakeawayUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    def operation():
        entry = _owned(db, user.id, takeaway_id, lock=True)
        if all(getattr(entry, field) == getattr(payload, field) for field in TEXT_FIELDS):
            return entry  # Safe retry after a committed response was lost.
        if entry.revision != payload.expected_revision:
            raise HTTPException(status_code=409, detail="This takeaway changed in another session. Load the latest version before saving again.")
        for field in TEXT_FIELDS:
            setattr(entry, field, getattr(payload, field))
        entry.revision += 1
        entry.updated_at = datetime.now(timezone.utc)
        return entry
    return _save(db, operation)
