from pydantic import BaseModel, ConfigDict, field_validator
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


def normalize_business_stage_string(value: str) -> str:
    """
    Normalize a string to match BusinessStage enum values.
    - Strips whitespace
    - Lowercases
    - Replaces underscores and spaces with hyphens (since enum values use hyphens)
    """
    return value.strip().lower().replace("_", "-").replace(" ", "-")


class OnboardingPayload(BaseModel):
    # Made optional for chat interface (no longer collecting full_name)
    full_name: Optional[str] = None
    age: Optional[int] = None
    occupation: Optional[str] = None
    entrepreneur_status: Optional[str] = None
    # Made optional for chat interface (no longer collecting location)
    location: Optional[str] = None
    economic_sector: Optional[str] = None
    industry: Optional[str] = None
    business_model: Optional[str] = None
    business_experience: Optional[str] = None
    areas_of_business: Optional[list[str]] = None
    business_stage: Optional[BusinessStage] = None
    org_size: Optional[str] = None
    is_student: Optional[bool] = None
    biggest_challenge: Optional[str] = None
    vision_6_12_months: Optional[str] = None
    blockers: Optional[str] = None
    current_gross_revenue: Optional[RevenueRange] = None
    has_prior_reading_history: Optional[bool] = None
    book_preferences: Optional[List[OnboardingBookPreference]] = None

    @field_validator("business_stage", mode="before")
    @classmethod
    def normalize_business_stage(cls, value):
        """
        Normalize business_stage input to accept case-insensitive strings.
        Accepts: "PRE_REVENUE", "pre_revenue", "pre-revenue", " Pre Revenue " -> BusinessStage.PRE_REVENUE (value: "pre-revenue")
        """
        if value is None:
            return None

        # If already an Enum instance, return it
        if isinstance(value, BusinessStage):
            return value

        # If string, normalize and match against enum values
        if isinstance(value, str):
            normalized = normalize_business_stage_string(value)

            # Try to match by enum value first (e.g., "pre-revenue")
            for stage in BusinessStage:
                if stage.value == normalized:
                    return stage

            # Try to match by enum name (e.g., "PRE_REVENUE" -> "pre-revenue" after normalization)
            # This handles cases where the input is the enum name
            value_upper = value.strip().upper()
            for stage in BusinessStage:
                if stage.name == value_upper:
                    return stage

            # If no match, raise ValueError with allowed values
            allowed_values = [stage.value for stage in BusinessStage]
            raise ValueError(
                f"Invalid business_stage value: {value!r}. "
                f"Allowed values are: {', '.join(allowed_values)}"
            )

        # For any other type, try to convert to string and normalize
        return cls.normalize_business_stage(str(value))


class OnboardingPatchPayload(BaseModel):
    """Payload for incremental/partial updates to onboarding profile (PATCH requests)"""
    entrepreneur_status: Optional[str] = None
    economic_sector: Optional[str] = None
    industry: Optional[str] = None
    business_model: Optional[str] = None
    business_experience: Optional[str] = None
    areas_of_business: Optional[list[str]] = None
    business_stage: Optional[BusinessStage] = None
    org_size: Optional[str] = None
    biggest_challenge: Optional[str] = None
    vision_6_12_months: Optional[str] = None
    current_gross_revenue: Optional[RevenueRange] = None

    @field_validator("business_stage", mode="before")
    @classmethod
    def normalize_business_stage(cls, value):
        """Same normalization as OnboardingPayload"""
        if value is None:
            return None

        if isinstance(value, BusinessStage):
            return value

        if isinstance(value, str):
            normalized = normalize_business_stage_string(value)

            for stage in BusinessStage:
                if stage.value == normalized:
                    return stage

            value_upper = value.strip().upper()
            for stage in BusinessStage:
                if stage.name == value_upper:
                    return stage

            allowed_values = [stage.value for stage in BusinessStage]
            raise ValueError(
                f"Invalid business_stage value: {value!r}. "
                f"Allowed values are: {', '.join(allowed_values)}"
            )

        return cls.normalize_business_stage(str(value))


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

