"""RD-60/61: a relevant return action and an explicit, private finish/check-in.

No emails, automatic reading logs, streaks, or competition credit are created.
"""
from datetime import date, datetime, timedelta, timezone
import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import func, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database import get_db
from app.models import (Book, OnboardingProfile, ReadingCompletion, ReadingHistoryEntry,
                        ReadingJourneyPreference, ReadingLog, ReadingTakeaway, User,
                        UserBookInteraction, UserBookStatusModel)
from app.routers.friendly_pairing import _lock as pairing_lock
from app.routers.reading_progress import local_today

router = APIRouter(prefix="/reading", tags=["reading-journey"])
logger = logging.getLogger(__name__)


class FinishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    rating: int | None = Field(default=None, ge=1, le=5, strict=True)
    reflection: str = Field(default="", max_length=2000)
    next_challenge: str | None = Field(default=None, min_length=1, max_length=2000)
    expected_challenge: str | None = Field(default=None, max_length=20000)


class PreferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    show_next_action: StrictBool
    snooze_days: Literal[0, 1, 7] = 0


class CompletionResponse(BaseModel):
    book_id: str
    title: str
    completed_on: date
    rating: int | None
    reflection: str
    challenge_before: str
    challenge_after: str


def completion_response(row, book):
    return CompletionResponse(book_id=str(row.book_id), title=book.title,
                              completed_on=row.completed_on, rating=row.rating,
                              reflection=row.reflection, challenge_before=row.challenge_before,
                              challenge_after=row.challenge_after)


def utc_now():
    return datetime.now(timezone.utc)


def _next_action(db, user_id, today, tz):
    # An untried idea is a more useful reason to return than a page-visit reminder.
    pending = db.query(ReadingTakeaway).filter(
        ReadingTakeaway.user_id == user_id, ReadingTakeaway.action_text != "",
        ReadingTakeaway.action_completed.is_(False),
    ).order_by(ReadingTakeaway.updated_at, ReadingTakeaway.id).first()
    if pending:
        return dict(kind="action", title="Put one idea into practice", detail=pending.action_text,
                    href="#reading-takeaways", label="Revisit my actions")
    shelves = db.query(UserBookStatusModel).filter(
        UserBookStatusModel.user_id == user_id,
        UserBookStatusModel.status.in_(["currently_reading", "reading_next", "waiting_for_book"]),
    ).order_by(UserBookStatusModel.updated_at.desc(), UserBookStatusModel.id).all()
    for state in ("currently_reading", "reading_next", "waiting_for_book"):
        for shelf in shelves:
            if shelf.status != state:
                continue
            try:
                book = db.get(Book, UUID(shelf.book_id))
            except ValueError:
                book = db.query(Book).filter_by(external_id=shelf.book_id).first()
            if book is None:
                continue
            if state == "currently_reading":
                last = db.query(ReadingLog).filter_by(user_id=user_id, book_id=book.id).order_by(ReadingLog.reading_date.desc()).first()
                anchor_date = last.reading_date if last else local_today(tz, shelf.updated_at.replace(tzinfo=timezone.utc))
                stalled = (today - anchor_date).days >= 3
                return dict(kind="restart" if stalled else "reading",
                            title="Pick it up at your pace" if stalled else "Your next reading moment",
                            detail=f"Continue {book.title}. A little reading is a useful next step.",
                            href=f"#reading-book-{book.id}", label="Continue reading")
            return dict(kind=state, title="Ready for your next chapter?" if state == "reading_next" else "Your book is waiting here",
                        detail=f"{book.title} is saved. Start whenever your copy is ready.",
                        href=f"#reading-book-{book.id}", label="See my book")
    finished = db.query(ReadingCompletion).filter_by(user_id=user_id).first()
    return dict(kind="finished" if finished else "new", title="What would help you next?" if finished else "Find a book worth starting",
                detail="Choose a book for the challenge you want to work on next." if finished else "Your recommendations are ready when you are.",
                href="/recommendations", label="Find my next book")


@router.get("/journey")
def get_journey(tz: str = Query(default="UTC"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = local_today(tz, utc_now())
    preference = db.get(ReadingJourneyPreference, user.id)
    show = preference.show_next_action if preference else True
    snoozed = preference.snoozed_until if preference else None
    profile = db.query(OnboardingProfile).filter_by(user_id=user.id).first()
    completed = db.query(ReadingCompletion, Book).join(Book, Book.id == ReadingCompletion.book_id).filter(
        ReadingCompletion.user_id == user.id,
    ).order_by(ReadingCompletion.created_at.desc(), ReadingCompletion.id).limit(50).all()
    return dict(today=today, show_next_action=show, snoozed_until=snoozed,
                challenge=profile.biggest_challenge if profile else "",
                next_action=_next_action(db, user.id, today, tz) if show and (not snoozed or snoozed <= today) else None,
                completions=[completion_response(row, book) for row, book in completed])


@router.put("/journey/preferences")
def save_preferences(payload: PreferenceRequest, tz: str = Query(default="UTC"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = local_today(tz, utc_now())
    values = dict(show_next_action=payload.show_next_action,
                  snoozed_until=today + timedelta(days=payload.snooze_days) if payload.snooze_days else None)
    try:
        db.execute(insert(ReadingJourneyPreference).values(user_id=user.id, **values).on_conflict_do_update(
            index_elements=[ReadingJourneyPreference.user_id], set_=values))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not save reading reminder preferences")
        raise HTTPException(status_code=500, detail="We couldn't save that preference. Please try again.")
    return values


@router.post("/books/{book_id}/finish", response_model=CompletionResponse)
def finish_book(book_id: UUID, payload: FinishRequest, tz: str = Query(default="UTC"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = local_today(tz, utc_now())
    book = db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found.")
    try:
        # Same lock order as progress. A finish and a progress write cannot race.
        pairing_lock(db)
        existing = db.query(ReadingCompletion).filter_by(user_id=user.id, book_id=book_id).first()
        if existing:
            if existing.request_id != payload.request_id:
                raise HTTPException(status_code=409, detail="This book is already finished. Refresh Reading to see it.")
            response = completion_response(existing, book)
            db.commit()
            return response
        if db.query(ReadingCompletion).filter_by(user_id=user.id, request_id=payload.request_id).first():
            raise HTTPException(status_code=409, detail="This save belongs to another book. Refresh Reading.")
        ids = [str(book.id)] + ([book.external_id] if book.external_id else [])
        shelves = db.query(UserBookStatusModel).filter(
            UserBookStatusModel.user_id == user.id, UserBookStatusModel.book_id.in_(ids),
        ).with_for_update().all()
        if not any(row.status == "currently_reading" for row in shelves):
            raise HTTPException(status_code=409, detail="Start this book in Reading before marking it finished.")
        profile = db.query(OnboardingProfile).filter_by(user_id=user.id).with_for_update().first()
        before = profile.biggest_challenge if profile else ""
        after = payload.next_challenge.strip() if payload.next_challenge is not None else before
        if payload.next_challenge is not None:
            if not after:
                raise HTTPException(status_code=422, detail="Enter a challenge, or keep your current one.")
            if not profile:
                raise HTTPException(status_code=409, detail="Complete your onboarding before updating your challenge.")
            if before != payload.expected_challenge:
                raise HTTPException(status_code=409, detail="Your challenge changed in another session. Refresh Reading before saving.")
            profile.biggest_challenge = after
        row = ReadingCompletion(user_id=user.id, book_id=book.id, request_id=payload.request_id,
                                completed_on=today, rating=payload.rating, reflection=payload.reflection.strip(),
                                challenge_before=before, challenge_after=after)
        db.add(row)
        for shelf in shelves:
            shelf.status = "finished"
            shelf.updated_at = datetime.utcnow()
        history = db.query(ReadingHistoryEntry).filter(ReadingHistoryEntry.user_id == user.id, or_(
            ReadingHistoryEntry.catalog_book_id == book.id,
            (func.lower(ReadingHistoryEntry.title) == book.title.lower()) &
            (func.lower(func.coalesce(ReadingHistoryEntry.author, "")) == (book.author_name or "").lower()),
        )).first()
        if not history:
            history = ReadingHistoryEntry(user_id=user.id, title=book.title, author=book.author_name or "", source="readar")
            db.add(history)
        history.catalog_book_id = book.id
        history.shelf = "read"
        history.date_read = today.isoformat()
        if payload.rating is not None:
            history.my_rating = payload.rating
        db.query(UserBookInteraction).filter_by(user_id=user.id, book_id=book.id).delete(synchronize_session=False)
        db.flush()
        response = completion_response(row, book)
        db.commit()
        return response
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Could not finish book %s", book_id)
        raise HTTPException(status_code=500, detail="We couldn't save your finish. Your answers are still here; please try again.")
