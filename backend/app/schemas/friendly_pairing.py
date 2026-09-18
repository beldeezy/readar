from datetime import datetime
from typing import Literal
from uuid import UUID
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class PairingCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    request_id: UUID
    expected_revision: int = Field(strict=True, ge=0)


class JoinPairing(PairingCommand):
    reading_name: str = Field(strict=True, min_length=1, max_length=32)
    book_id: UUID
    share_with_partner: StrictBool

    @field_validator('share_with_partner')
    @classmethod
    def require_consent(cls, value):
        if not value:
            raise ValueError('Choose to share your reading name and selected book before joining.')
        return value

    @field_validator('reading_name')
    @classmethod
    def safe_reading_name(cls, value):
        if '@' in value or any(unicodedata.category(char).startswith('C') or char in '\r\n' for char in value):
            raise ValueError('Use a short reading name, without an email address or control characters.')
        return value


class SharedReader(BaseModel):
    reading_name: str
    book_title: str
    book_author: str


class PairingResponse(BaseModel):
    status: Literal['inactive', 'waiting', 'paired', 'ended']
    revision: int
    progress_sharing: bool = False
    you: SharedReader | None = None
    selected_book_id: UUID | None = None
    queued_at: datetime | None = None
    pairing_id: UUID | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    ended_by_you: bool | None = None
    partner: SharedReader | None = None
