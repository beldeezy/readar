"""Tests for user helper functions."""
import pytest
import os
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
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


def test_email_relink_when_flag_enabled(db: Session, monkeypatch):
    """Test that email relink works when ALLOW_EMAIL_RELINK is enabled."""
    # Enable email relink
    monkeypatch.setenv("ALLOW_EMAIL_RELINK", "true")
    
    email = "relink@example.com"
    auth_user_id_1 = str(uuid4())
    auth_user_id_2 = str(uuid4())
    
    # Create user with first auth_user_id
    user1 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id_1,
        email=email,
    )
    
    assert user1.auth_user_id == auth_user_id_1
    assert user1.email == email.lower()  # Email should be normalized to lowercase
    
    # Try to get/create with different auth_user_id but same email
    # Should relink the email to the new auth_user_id
    user2 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id_2,
        email=email,
    )
    
    # Should be the same user, but with updated auth_user_id
    assert user2.id == user1.id
    assert user2.auth_user_id == auth_user_id_2
    assert user2.email == email.lower()
    
    # Verify in database
    db.refresh(user2)
    assert user2.auth_user_id == auth_user_id_2


def test_email_relink_raises_409_when_flag_disabled(db: Session, monkeypatch):
    """Test that email relink raises 409 when ALLOW_EMAIL_RELINK is disabled."""
    # Disable email relink (default)
    monkeypatch.setenv("ALLOW_EMAIL_RELINK", "false")
    
    email = "norelink@example.com"
    auth_user_id_1 = str(uuid4())
    auth_user_id_2 = str(uuid4())
    
    # Create user with first auth_user_id
    user1 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id_1,
        email=email,
    )
    
    assert user1.auth_user_id == auth_user_id_1
    
    # Try to get/create with different auth_user_id but same email
    # Should raise 409
    with pytest.raises(HTTPException) as exc_info:
        get_or_create_user_by_auth_id(
            db=db,
            auth_user_id=auth_user_id_2,
            email=email,
        )
    
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "email_already_linked_to_different_account"
    
    # Verify original user is unchanged
    db.refresh(user1)
    assert user1.auth_user_id == auth_user_id_1


def test_email_relink_default_behavior_is_disabled(db: Session):
    """Test that email relink is disabled by default (no env var set)."""
    email = "default@example.com"
    auth_user_id_1 = str(uuid4())
    auth_user_id_2 = str(uuid4())
    
    # Create user with first auth_user_id
    user1 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id_1,
        email=email,
    )
    
    assert user1.auth_user_id == auth_user_id_1
    
    # Try to get/create with different auth_user_id but same email
    # Should raise 409 (default behavior, no env var)
    with pytest.raises(HTTPException) as exc_info:
        get_or_create_user_by_auth_id(
            db=db,
            auth_user_id=auth_user_id_2,
            email=email,
        )
    
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "email_already_linked_to_different_account"


def test_email_conflict_orphans_other_row(db: Session):
    """Test that when updating email on existing user, conflicting email is orphaned."""
    auth_user_id_1 = str(uuid4())
    auth_user_id_2 = str(uuid4())
    email_1 = "user1@example.com"
    email_2 = "user2@example.com"
    
    # Create user1 with email_1
    user1 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id_1,
        email=email_1,
    )
    
    # Create user2 with email_2
    user2 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id_2,
        email=email_2,
    )
    
    assert user1.email == email_1.lower()
    assert user2.email == email_2.lower()
    
    # Update user1's email to email_2 (which is already taken by user2)
    # This should orphan user2's email (set to NULL) and assign email_2 to user1
    updated_user1 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id_1,
        email=email_2,
    )
    
    assert updated_user1.id == user1.id
    assert updated_user1.email == email_2.lower()
    
    # Verify user2's email was orphaned (set to NULL)
    db.refresh(user2)
    assert user2.email is None
    assert user2.auth_user_id == auth_user_id_2  # auth_user_id should remain unchanged


def test_legacy_user_linking(db: Session):
    """Test that legacy user (email exists but no auth_user_id) gets linked."""
    email = "legacy@example.com"
    auth_user_id = str(uuid4())
    
    # Create a legacy user (no auth_user_id)
    legacy_user = User(
        email=email,
        subscription_status=SubscriptionStatus.FREE,
    )
    db.add(legacy_user)
    db.commit()
    db.refresh(legacy_user)
    
    assert legacy_user.auth_user_id is None
    
    # Call get_or_create_user_by_auth_id - should link the legacy user
    linked_user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id,
        email=email,
    )
    
    assert linked_user.id == legacy_user.id
    assert linked_user.auth_user_id == auth_user_id
    assert linked_user.email == email.lower()


def test_email_update_on_existing_user(db: Session):
    """Test that email updates when user exists by auth_user_id."""
    auth_user_id = str(uuid4())
    email_1 = "old@example.com"
    email_2 = "new@example.com"
    
    # Create user with email_1
    user1 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id,
        email=email_1,
    )
    
    assert user1.email == email_1.lower()
    
    # Update email to email_2
    user2 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id,
        email=email_2,
    )
    
    assert user2.id == user1.id
    assert user2.email == email_2.lower()
    assert user2.auth_user_id == auth_user_id


def test_auto_repair_email_drift(db: Session):
    """Test that email drift is auto-repaired by repurposing existing row."""
    email = "drift@example.com"
    old_auth_user_id = str(uuid4())
    new_auth_user_id = str(uuid4())
    
    # Create user with email and old_auth_user_id (simulating drift)
    drifted_user = User(
        email=email,
        auth_user_id=old_auth_user_id,
        subscription_status=SubscriptionStatus.FREE,
    )
    db.add(drifted_user)
    db.commit()
    db.refresh(drifted_user)
    
    assert drifted_user.auth_user_id == old_auth_user_id
    assert drifted_user.email == email.lower()
    
    # Call get_or_create_user_by_auth_id with new_auth_user_id and same email
    # Should auto-repair by updating the existing row's auth_user_id
    repaired_user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=new_auth_user_id,
        email=email,
    )
    
    # Assert returned user has new auth_user_id and same email
    assert repaired_user.id == drifted_user.id
    assert repaired_user.auth_user_id == new_auth_user_id
    assert repaired_user.email == email.lower()
    
    # Assert only one row exists for this email
    users_with_email = db.query(User).filter(
        func.lower(User.email) == email.lower()
    ).all()
    assert len(users_with_email) == 1
    assert users_with_email[0].id == repaired_user.id
    assert users_with_email[0].auth_user_id == new_auth_user_id
    
    # Assert no row exists with old_auth_user_id
    old_user = db.query(User).filter(User.auth_user_id == old_auth_user_id).one_or_none()
    assert old_user is None

