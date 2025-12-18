# backend/app/routers/debug.py

from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.core.supabase_auth import get_supabase_user
from app.core.user_helpers import get_or_create_user_by_auth_id

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/catalog-stats")
async def catalog_stats(
    current_user: dict = Depends(get_supabase_user),
    db: Session = Depends(get_db),
):
    """
    Small debug endpoint to see what signal we have for the current user
    and whether there is any catalog data at all.
    """
    # Get or create local user from Supabase auth_user_id
    user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=current_user["auth_user_id"],
        email=current_user.get("email", ""),
    )
    user_id = user.id
    
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

