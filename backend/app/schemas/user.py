from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.models import SubscriptionStatus


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    subscription_status: SubscriptionStatus
    created_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: str
    email: str
    is_admin: bool


class NotificationPreferences(BaseModel):
    """Email notification preferences for the current user."""
    notify_email_recommendations: bool
    notify_email_learning_tips: bool
    notify_email_product: bool

    class Config:
        from_attributes = True


class NotificationPreferencesUpdate(BaseModel):
    """Partial update for notification preferences (only provided fields change)."""
    notify_email_recommendations: Optional[bool] = None
    notify_email_learning_tips: Optional[bool] = None
    notify_email_product: Optional[bool] = None

