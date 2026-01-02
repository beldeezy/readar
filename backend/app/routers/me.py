from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.models import User
from app.schemas.user import MeResponse

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
    }

