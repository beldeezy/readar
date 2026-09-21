from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.reading_takeaways import TakeawayResponse


class ReflectionText(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    attempted_on: date
    outcome: Literal["helped", "mixed", "did_not_help", "too_soon"]
    result: str = Field(min_length=1, max_length=4000, strict=True)
    next_step: str = Field(default="", max_length=2000, strict=True)
    completed: bool = Field(default=False, strict=True)
    expected_revision: int = Field(ge=1, strict=True)

    @model_validator(mode="after")
    def require_next_step(self):
        if not self.completed and not self.next_step:
            raise ValueError("Add a next step or mark the action completed.")
        return self


class ReflectionCreate(ReflectionText):
    client_id: UUID


class ReopenAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1, strict=True)


class ReflectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sequence: int
    attempted_on: date
    outcome: str
    result: str
    next_step: str
    completed: bool
    action_snapshot: str
    goal_snapshot: str
    takeaway_snapshot: str
    created_at: datetime
    updated_at: datetime


class ReflectionList(BaseModel):
    items: list[ReflectionResponse]
    next_before: int | None


class ReflectionSaved(BaseModel):
    takeaway: TakeawayResponse
    reflection: ReflectionResponse
