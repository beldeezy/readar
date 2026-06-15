from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.user import (
    MeResponse,
    NotificationPreferences,
    NotificationPreferencesUpdate,
)
from app.core.admin import parse_admin_allowlist, is_admin_email
from app.core.config import settings

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)):
    """
    Get current user information.

    Returns user details including admin status based on ADMIN_EMAIL_ALLOWLIST.
    """
    # Parse admin allowlist from environment and check if user is admin
    admin_allowlist = parse_admin_allowlist(settings.ADMIN_EMAIL_ALLOWLIST)
    user_is_admin = is_admin_email(current_user.email, admin_allowlist)

    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "is_admin": user_is_admin,
    }


@router.get("/notification-preferences", response_model=NotificationPreferences)
def get_notification_preferences(current_user: User = Depends(get_current_user)):
    """Get the current user's email notification preferences."""
    return current_user


@router.patch("/notification-preferences", response_model=NotificationPreferences)
def update_notification_preferences(
    payload: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's email notification preferences (partial)."""
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user
