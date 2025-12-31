"""Tests for user helper functions."""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.models import User, SubscriptionStatus
from app.core.user_helpers import get_or_create_user_by_auth_id, _normalize_subscription_status


def test_get_or_create_user_by_auth_id_creates_user_with_default_subscription_status(db: Session):
    """Test that get_or_create_user_by_auth_id creates a user with FREE subscription status."""
    auth_user_id = str(uuid4())
    email = "test@example.com"
    
    # Create user
    user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id,
        email=email,
    )
    
    # Verify user was created
    assert user is not None
    assert user.auth_user_id == auth_user_id
    assert user.email == email
    assert user.subscription_status == SubscriptionStatus.FREE
    
    # Verify it's persisted correctly (lowercase "free" in DB)
    assert user.subscription_status.value == "free"
    
    # Verify we can retrieve it from DB
    db.refresh(user)
    assert user.subscription_status == SubscriptionStatus.FREE


def test_get_or_create_user_by_auth_id_returns_existing_user(db: Session):
    """Test that get_or_create_user_by_auth_id returns existing user."""
    auth_user_id = str(uuid4())
    email = "test@example.com"
    
    # Create user first time
    user1 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id,
        email=email,
    )
    
    # Get same user second time
    user2 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id,
        email=email,
    )
    
    # Should be the same user
    assert user1.id == user2.id
    assert user1.subscription_status == SubscriptionStatus.FREE


def test_normalize_subscription_status_with_enum():
    """Test _normalize_subscription_status with enum object."""
    result = _normalize_subscription_status(SubscriptionStatus.FREE)
    assert result == SubscriptionStatus.FREE
    assert result.value == "free"


def test_normalize_subscription_status_with_lowercase_string():
    """Test _normalize_subscription_status with lowercase string value."""
    result = _normalize_subscription_status("free")
    assert result == SubscriptionStatus.FREE
    assert result.value == "free"


def test_normalize_subscription_status_with_uppercase_string():
    """Test _normalize_subscription_status with uppercase string (guards against "FREE")."""
    result = _normalize_subscription_status("FREE")
    assert result == SubscriptionStatus.FREE
    assert result.value == "free"


def test_normalize_subscription_status_with_enum_name():
    """Test _normalize_subscription_status with enum name string."""
    result = _normalize_subscription_status("ACTIVE")
    assert result == SubscriptionStatus.ACTIVE
    assert result.value == "active"

