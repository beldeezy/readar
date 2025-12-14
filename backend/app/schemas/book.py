from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models import BookDifficulty


class BookResponse(BaseModel):
    id: str
    external_id: Optional[str]
    title: str
    subtitle: Optional[str]
    author_name: str
    description: str
    thumbnail_url: Optional[str]
    cover_image_url: Optional[str]
    page_count: Optional[int]
    published_year: Optional[int]
    categories: Optional[list[str]]
    business_stage_tags: Optional[list[str]]
    functional_tags: Optional[list[str]]
    theme_tags: Optional[list[str]]
    difficulty: Optional[BookDifficulty]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BookCreate(BaseModel):
    external_id: Optional[str] = None
    title: str
    subtitle: Optional[str] = None
    author_name: str
    description: str
    thumbnail_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    page_count: Optional[int] = None
    published_year: Optional[int] = None
    categories: Optional[list[str]] = None
    business_stage_tags: Optional[list[str]] = None
    functional_tags: Optional[list[str]] = None
    theme_tags: Optional[list[str]] = None
    difficulty: Optional[BookDifficulty] = None

