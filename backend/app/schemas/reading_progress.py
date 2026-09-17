from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ReadingSettingsRequest(BaseModel):
    unit: Literal["pages", "chapters"]
    starting_position: int = Field(ge=0, le=100000, strict=True)
    total_units: Optional[int] = Field(default=None, ge=1, le=100000, strict=True)
    daily_goal: int = Field(ge=1, le=1000, strict=True)
    expected_revision: int = Field(ge=0, strict=True)


class ReadingLogRequest(BaseModel):
    position: int = Field(ge=0, le=100000, strict=True)
    expected_revision: int = Field(ge=0, strict=True)


class ReadingLogResponse(BaseModel):
    reading_date: date
    position: int
    units_read: int
    goal_target: int
    goal_met: bool
    updated_at: datetime


class ReadingProgressResponse(BaseModel):
    book_id: str
    unit: Literal["pages", "chapters"]
    starting_position: int
    total_units: Optional[int]
    daily_goal: int
    revision: int
    current_position: int
    percent_complete: Optional[float]
    today: date
    today_units: int
    today_goal: int
    goal_met: bool
    logs: list[ReadingLogResponse]
