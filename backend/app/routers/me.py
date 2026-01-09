from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.models import User
from app.schemas.user import MeResponse
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

