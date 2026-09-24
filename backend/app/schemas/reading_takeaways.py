from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class TakeawayText(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    takeaway: str = Field(min_length=1, max_length=4000, strict=True)
    action_text: str = Field(default="", max_length=2000, strict=True)
    goal_context: str = Field(min_length=1, max_length=2000, strict=True)


class TakeawayCreate(TakeawayText):
    book_id: UUID
    client_id: UUID


class TakeawayUpdate(TakeawayText):
    expected_revision: int = Field(ge=1, strict=True)


class TakeawayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    book_id: UUID
    book_title: str
    book_author: str
    takeaway: str
    action_text: str
    goal_context: str
    action_status: Literal["idea", "pending", "completed"]
    next_step: str
    reflection_count: int
    revision: int
    created_at: datetime
    updated_at: datetime


class TakeawayList(BaseModel):
    items: list[TakeawayResponse]
    suggested_goal: str
    next_cursor: UUID | None
