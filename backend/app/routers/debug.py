# backend/app/routers/debug.py

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from sqlalchemy.orm import Session

from app.database import get_db
from app import models

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/catalog-stats")
def catalog_stats(
    user_id: UUID = Query(..., description="User to inspect"),
    db: Session = Depends(get_db),
):
    """
    Small debug endpoint to see what signal we have for a given user
    and whether there is any catalog data at all.
    """
    books_count = db.query(models.Book).count()
    interactions_count = (
        db.query(models.UserBookInteraction)
        .filter(models.UserBookInteraction.user_id == user_id)
        .count()
    )
    history_count = (
        db.query(models.ReadingHistoryEntry)
        .filter(models.ReadingHistoryEntry.user_id == user_id)
        .count()
    )
    onboarding = (
        db.query(models.OnboardingProfile)
        .filter(models.OnboardingProfile.user_id == user_id)
        .one_or_none()
    )

    return {
        "books_count": books_count,
        "interactions_count": interactions_count,
        "history_count": history_count,
        "has_onboarding": onboarding is not None,
    }

