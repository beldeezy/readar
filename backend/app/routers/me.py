from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.models import User

router = APIRouter(tags=["auth"])


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "auth_user_id": user.auth_user_id,
        "email": user.email,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }

