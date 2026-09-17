from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database import get_db
from app.models import User
from app.routers.reading_progress import local_today
from app.schemas.reading_rewards import ReadingRewardsResponse
from app.services.reading_rewards import get_reading_rewards

router = APIRouter(prefix="/reading", tags=["reading-rewards"])


@router.get("/rewards", response_model=ReadingRewardsResponse)
def rewards(tz: str = Query(default="UTC"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_reading_rewards(db, user.id, local_today(tz), tz)
