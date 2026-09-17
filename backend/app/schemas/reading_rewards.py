from datetime import date
from typing import Literal
from pydantic import BaseModel


class RewardDay(BaseModel):
    reading_date: date
    qualified: bool


class ReadingRewardsResponse(BaseModel):
    today: date
    timezone: str
    points_per_day: int
    total_points: int
    qualifying_days: int
    current_streak: int
    best_streak: int
    today_qualified: bool
    last_qualified_date: date | None
    state: Literal["new", "active", "continue", "restart"]
    recent_days: list[RewardDay]
