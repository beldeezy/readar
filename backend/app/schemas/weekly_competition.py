from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, StrictBool, field_validator
from app.schemas.friendly_pairing import PairingCommand


class CompetitionConsent(PairingCommand):
    timezone: str = Field(strict=True, min_length=1, max_length=64)
    share_progress: StrictBool
    expected_reading_revision: int = Field(strict=True, ge=0)

    @field_validator('share_progress')
    @classmethod
    def explicit_consent(cls, value):
        if not value:
            raise ValueError('Choose to share weekly reading summaries before joining.')
        return value


class CompetitionRule(BaseModel):
    unit: Literal['pages', 'chapters']
    daily_target: int
    total_units: int


class CompetitionScore(BaseModel):
    days: int
    progress_percent: float
    points: float


class CompetitionRoundView(BaseModel):
    starts_on: date
    ends_on: date
    status: Literal['scheduled', 'active', 'finished', 'ended']
    you: CompetitionScore
    partner: CompetitionScore | None = None
    result: Literal['pending', 'ahead', 'behind', 'even', 'win', 'loss', 'shared_win', 'quiet', 'ended']


class CompetitionResponse(BaseModel):
    state: Literal['unavailable', 'not_joined', 'waiting', 'scheduled', 'active']
    revision: int
    timezone: str | None = None
    reading_revision: int | None = None
    consented: bool = False
    partner_consented: bool = False
    eligibility_error: str | None = None
    rule: CompetitionRule | None = None
    current: CompetitionRoundView | None = None
    history: list[CompetitionRoundView] = Field(default_factory=list)
    all_time_points: float = 0
    wins: int = 0
    shared_wins: int = 0
