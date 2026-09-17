"""Per-reader book progress. Daily positions replace, rather than add, on retry."""
from datetime import date, datetime, timezone
import logging
from types import SimpleNamespace
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database import get_db
from app.models import Book, ReadingLog, ReadingProgress, User, UserBookStatusModel
from app.schemas.reading_progress import ReadingLogRequest, ReadingProgressResponse, ReadingSettingsRequest

router = APIRouter(prefix="/reading/books", tags=["reading-progress"])
logger = logging.getLogger(__name__)


def local_today(tz: str, now: datetime | None = None) -> date:
    try:
        zone = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=422, detail="Choose a valid time zone.")
    return (now or datetime.now(timezone.utc)).astimezone(zone).date()


def _book(db, book_id):
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found.")
    return book


def _defaults(book):
    total = book.page_count if book.page_count and 0 < book.page_count <= 100000 else None
    return dict(unit="pages", starting_position=0, total_units=total, daily_goal=10, revision=0)


def _logs(db, user_id, book_id):
    return db.query(ReadingLog).filter_by(user_id=user_id, book_id=book_id).order_by(ReadingLog.reading_date).all()


def _response(book, progress, logs, today):
    progress = progress or SimpleNamespace(**_defaults(book))
    previous = progress.starting_position
    entries = []
    today_units = 0
    for log in logs:
        units = log.position - previous
        entries.append(dict(reading_date=log.reading_date, position=log.position, units_read=units, updated_at=log.updated_at))
        if log.reading_date == today:
            today_units = units
        previous = log.position
    return ReadingProgressResponse(
        book_id=str(book.id), unit=progress.unit, starting_position=progress.starting_position,
        total_units=progress.total_units, daily_goal=progress.daily_goal, revision=progress.revision,
        current_position=previous,
        percent_complete=round(previous * 100 / progress.total_units, 1) if progress.total_units else None,
        today=today, today_units=today_units, goal_met=today_units >= progress.daily_goal,
        logs=list(reversed(entries)),
    )


def _check_revision(progress, expected):
    if progress.revision != expected:
        raise HTTPException(status_code=409, detail="Your progress changed in another session. Reload it before saving again.")


def _validate_positions(progress, positions):
    previous = progress.starting_position
    if progress.total_units is not None and previous > progress.total_units:
        raise HTTPException(status_code=422, detail="The book length must include your starting position.")
    for _, position in sorted(positions.items()):
        if position < previous:
            raise HTTPException(status_code=422, detail="Keep logged positions in date order. Correct earlier or later entries first.")
        if progress.total_units is not None and position > progress.total_units:
            raise HTTPException(status_code=422, detail="That position is beyond this book's length. Check your edition in Book settings.")
        previous = position


def _mutate(db, user, book, today, change):
    book_id = book.id
    try:
        # One lock per reader/book serializes settings and all daily log writes.
        db.execute(insert(ReadingProgress).values(user_id=user.id, book_id=book.id, **_defaults(book))
                   .on_conflict_do_nothing(constraint="uq_reading_progress_user_book"))
        progress = db.query(ReadingProgress).filter_by(user_id=user.id, book_id=book.id).populate_existing().with_for_update().one()
        ids = [str(book.id)] + ([book.external_id] if book.external_id else [])
        shelf = db.query(UserBookStatusModel).filter(
            UserBookStatusModel.user_id == user.id,
            UserBookStatusModel.book_id.in_(ids),
            UserBookStatusModel.status == "currently_reading",
        ).with_for_update().first()
        if shelf is None:
            raise HTTPException(status_code=409, detail="Start this book in Reading before saving progress.")
        logs = _logs(db, user.id, book.id)
        changed = change(progress, logs)
        if changed:
            progress.revision += 1
        db.flush()
        response = _response(book, progress, _logs(db, user.id, book.id), today)
        db.commit()
        return response
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Could not save reading progress for book %s", book_id)
        raise HTTPException(status_code=500, detail="We couldn't save your progress. Please try again.")


@router.get("/{book_id}/progress", response_model=ReadingProgressResponse)
def get_progress(book_id: UUID, tz: str = Query(default="UTC"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = local_today(tz)
    book = _book(db, book_id)
    # Shared lock keeps settings/revision and logs from different writes from
    # being combined into one response. GET never creates a progress row.
    progress = db.query(ReadingProgress).filter_by(user_id=user.id, book_id=book_id).populate_existing().with_for_update(read=True).first()
    return _response(book, progress, _logs(db, user.id, book_id) if progress else [], today)


@router.put("/{book_id}/settings", response_model=ReadingProgressResponse)
def save_settings(book_id: UUID, payload: ReadingSettingsRequest, tz: str = Query(default="UTC"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = local_today(tz)
    book = _book(db, book_id)
    values = payload.model_dump(exclude={"expected_revision"})

    def change(progress, logs):
        if all(getattr(progress, key) == value for key, value in values.items()):
            return False
        _check_revision(progress, payload.expected_revision)
        if logs and progress.unit != payload.unit:
            raise HTTPException(status_code=422, detail="Remove the existing logs before switching between pages and chapters.")
        candidate = SimpleNamespace(**values)
        _validate_positions(candidate, {log.reading_date: log.position for log in logs})
        for key, value in values.items():
            setattr(progress, key, value)
        return True

    return _mutate(db, user, book, today, change)


@router.put("/{book_id}/logs/{reading_date}", response_model=ReadingProgressResponse)
def save_log(book_id: UUID, reading_date: date, payload: ReadingLogRequest, tz: str = Query(default="UTC"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = local_today(tz)
    if reading_date > today:
        raise HTTPException(status_code=422, detail="Choose today or an earlier date.")
    book = _book(db, book_id)

    def change(progress, logs):
        existing = next((log for log in logs if log.reading_date == reading_date), None)
        if existing and existing.position == payload.position:
            # Safe retry after a committed response was lost; no new credit.
            return False
        _check_revision(progress, payload.expected_revision)
        positions = {log.reading_date: log.position for log in logs}
        positions[reading_date] = payload.position
        _validate_positions(progress, positions)
        if existing:
            existing.position = payload.position
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.add(ReadingLog(user_id=user.id, book_id=book.id, reading_date=reading_date, position=payload.position))
        return True

    return _mutate(db, user, book, today, change)


@router.delete("/{book_id}/logs/{reading_date}", response_model=ReadingProgressResponse)
def delete_log(book_id: UUID, reading_date: date, expected_revision: int = Query(ge=0), tz: str = Query(default="UTC"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = local_today(tz)
    book = _book(db, book_id)

    def change(progress, logs):
        existing = next((log for log in logs if log.reading_date == reading_date), None)
        if existing is None:
            return False
        _check_revision(progress, expected_revision)
        db.delete(existing)
        return True

    return _mutate(db, user, book, today, change)
