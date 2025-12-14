from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime
from uuid import UUID
from app.models import BusinessStage


class OnboardingBookPreference(BaseModel):
    book_id: str
    status: Literal[
        "read_liked",
        "read_disliked",
        "interested",
        "not_interested",
    ]


RevenueRange = Literal[
    "pre_revenue",
    "lt_100k",
    "100k_300k",
    "300k_500k",
    "500k_1m",
    "1m_3m",
    "3m_5m",
    "5m_10m",
    "10m_30m",
    "30m_100m",
    "100m_plus",
]


class OnboardingPayload(BaseModel):
    full_name: str
    age: Optional[int] = None
    occupation: Optional[str] = None
    entrepreneur_status: Optional[str] = None
    location: Optional[str] = None
    economic_sector: Optional[str] = None
    industry: Optional[str] = None
    business_model: str
    business_experience: Optional[str] = None
    areas_of_business: Optional[list[str]] = None
    business_stage: BusinessStage
    org_size: Optional[str] = None
    is_student: Optional[bool] = None
    biggest_challenge: str
    vision_6_12_months: Optional[str] = None
    blockers: Optional[str] = None
    current_gross_revenue: Optional[RevenueRange] = None
    has_prior_reading_history: Optional[bool] = None
    book_preferences: Optional[List[OnboardingBookPreference]] = None


class OnboardingProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: UUID
    full_name: str
    age: Optional[int]
    occupation: Optional[str]
    entrepreneur_status: Optional[str]
    location: Optional[str]
    economic_sector: Optional[str]
    industry: Optional[str]
    business_model: str
    business_experience: Optional[str]
    areas_of_business: Optional[list[str]]
    business_stage: BusinessStage
    org_size: Optional[str]
    is_student: Optional[bool]
    biggest_challenge: str
    vision_6_12_months: Optional[str]
    blockers: Optional[str]
    current_gross_revenue: Optional[RevenueRange]
    has_prior_reading_history: Optional[bool]
    created_at: datetime
    updated_at: datetime

