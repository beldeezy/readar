"""A reader's attempts and results, with context retained as plans evolve."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database import get_db
from app.models import ReadingReflection, User
from app.routers.reading_progress import local_today
from app.routers.reading_takeaways import _owned, _save
from app.schemas.reading_reflections import ReflectionCreate, ReflectionText, ReflectionResponse, ReflectionList, ReflectionSaved, ReopenAction
from app.schemas.reading_takeaways import TakeawayResponse

router = APIRouter(prefix="/reading/takeaways", tags=["reading-reflections"])
FIELDS = ("attempted_on", "outcome", "result", "next_step", "completed")


def _check_revision(entry, expected):
    if entry.revision != expected:
        raise HTTPException(status_code=409, detail="This action changed in another session. Load the latest version before saving again.")


def _changed(entry):
    entry.revision += 1
    entry.updated_at = datetime.now(timezone.utc)


def _reflection(db, takeaway_id, reflection_id):
    row = db.query(ReadingReflection).filter_by(id=reflection_id, takeaway_id=takeaway_id).populate_existing().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Reflection not found.")
    return row


@router.get("/{takeaway_id}/reflections", response_model=ReflectionList)
def list_reflections(takeaway_id: UUID, before: int | None = Query(default=None, ge=1),
                     limit: int = Query(default=20, ge=1, le=100), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _owned(db, user.id, takeaway_id)
    query = db.query(ReadingReflection).filter_by(takeaway_id=takeaway_id)
    if before is not None:
        query = query.filter(ReadingReflection.sequence < before)
    rows = query.order_by(ReadingReflection.sequence.desc()).limit(limit + 1).all()
    return ReflectionList(items=[ReflectionResponse.model_validate(row) for row in rows[:limit]],
                          next_before=rows[limit - 1].sequence if len(rows) > limit else None)


@router.get("/{takeaway_id}/reflections/{reflection_id}", response_model=ReflectionSaved)
def get_reflection(takeaway_id: UUID, reflection_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entry = _owned(db, user.id, takeaway_id, lock="read")
    return dict(takeaway=entry, reflection=_reflection(db, takeaway_id, reflection_id))


@router.post("/{takeaway_id}/reflections", response_model=ReflectionSaved)
def create_reflection(takeaway_id: UUID, payload: ReflectionCreate, tz: str = "UTC",
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = local_today(tz)

    def operation():
        entry = _owned(db, user.id, takeaway_id, lock=True)
        existing = db.query(ReadingReflection).filter_by(takeaway_id=takeaway_id, client_id=payload.client_id).first()
        if existing:
            if any(getattr(existing, field) != getattr(payload, field) for field in FIELDS):
                raise HTTPException(status_code=409, detail={"message": "This reflection was already saved with different text. Load the saved version before editing.", "existing_id": str(existing.id)})
            return dict(takeaway=entry, reflection=existing)
        _check_revision(entry, payload.expected_revision)
        if not entry.action_text or entry.action_completed:
            raise HTTPException(status_code=409, detail="Add an action or reopen the completed action before recording another attempt.")
        if payload.attempted_on > today:
            raise HTTPException(status_code=422, detail="Choose today or an earlier attempt date.")
        entry.reflection_count += 1
        reflection = ReadingReflection(takeaway_id=takeaway_id, client_id=payload.client_id,
            sequence=entry.reflection_count, action_generation=entry.action_generation,
            action_snapshot=entry.next_step or entry.action_text, goal_snapshot=entry.goal_context,
            takeaway_snapshot=entry.takeaway, **{field: getattr(payload, field) for field in FIELDS})
        db.add(reflection)
        entry.next_step = payload.next_step
        entry.action_completed = payload.completed
        _changed(entry)
        return dict(takeaway=entry, reflection=reflection)
    return _save(db, operation, ReflectionSaved)


@router.put("/{takeaway_id}/reflections/{reflection_id}", response_model=ReflectionSaved)
def update_reflection(takeaway_id: UUID, reflection_id: UUID, payload: ReflectionText, tz: str = "UTC",
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = local_today(tz)

    def operation():
        entry = _owned(db, user.id, takeaway_id, lock=True)
        reflection = _reflection(db, takeaway_id, reflection_id)
        if all(getattr(reflection, field) == getattr(payload, field) for field in FIELDS):
            return dict(takeaway=entry, reflection=reflection)
        _check_revision(entry, payload.expected_revision)
        if payload.attempted_on > today:
            raise HTTPException(status_code=422, detail="Choose today or an earlier attempt date.")
        for field in FIELDS:
            setattr(reflection, field, getattr(payload, field))
        reflection.updated_at = datetime.now(timezone.utc)
        # History corrections must not overwrite a newer plan or an explicit reopen.
        if reflection.sequence == entry.reflection_count and reflection.action_generation == entry.action_generation:
            entry.next_step = payload.next_step
            entry.action_completed = payload.completed
        _changed(entry)
        return dict(takeaway=entry, reflection=reflection)
    return _save(db, operation, ReflectionSaved)


@router.put("/{takeaway_id}/reopen", response_model=TakeawayResponse)
def reopen_action(takeaway_id: UUID, payload: ReopenAction, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    def operation():
        entry = _owned(db, user.id, takeaway_id, lock=True)
        if not entry.action_text:
            raise HTTPException(status_code=409, detail="Add an action to this takeaway first.")
        if not entry.action_completed:
            return entry
        _check_revision(entry, payload.expected_revision)
        entry.action_completed = False
        entry.action_generation += 1
        _changed(entry)
        return entry
    return _save(db, operation)
