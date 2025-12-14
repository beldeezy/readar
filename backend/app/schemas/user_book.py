from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models import UserBookStatus


class UserBookInteractionCreate(BaseModel):
    book_id: str
    status: UserBookStatus
    rating: Optional[int] = None
    notes: Optional[str] = None


class UserBookInteractionResponse(BaseModel):
    id: str
    user_id: str
    book_id: str
    status: UserBookStatus
    rating: Optional[int]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

