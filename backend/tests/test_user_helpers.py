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


def test_same_email_different_auth_id_relinks(db: Session):
    """Same email + a new auth_user_id safely relinks the existing user.

    The linking logic was reworked from a hard 409 to 'safe automatic relinking':
    when only the auth_user_id changes (Supabase 'sub' rotation) but the email
    matches, the existing row is updated to the new auth_user_id.
    """
    email = "relink@example.com"
    auth_user_id_1 = str(uuid4())
    auth_user_id_2 = str(uuid4())

    user1 = get_or_create_user_by_auth_id(db=db, auth_user_id=auth_user_id_1, email=email)
    assert user1.auth_user_id == auth_user_id_1

    relinked = get_or_create_user_by_auth_id(db=db, auth_user_id=auth_user_id_2, email=email)

    # Same underlying row, now pointing at the new auth_user_id (no 409, no new row).
    assert relinked.id == user1.id
    assert relinked.auth_user_id == auth_user_id_2
    assert relinked.email == email.lower()


def test_change_email_for_same_auth_id_raises_409(db: Session):
    """Changing the email on an existing auth_user_id is unsafe -> 409.

    Email is treated as stable per user; only the auth_user_id is allowed to drift.
    The frontend handles this 'email_mismatch_cannot_link' code explicitly.
    """
    auth_user_id = str(uuid4())

    user1 = get_or_create_user_by_auth_id(db=db, auth_user_id=auth_user_id, email="old@example.com")
    assert user1.email == "old@example.com"

    with pytest.raises(HTTPException) as exc_info:
        get_or_create_user_by_auth_id(db=db, auth_user_id=auth_user_id, email="new@example.com")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "email_mismatch_cannot_link"

    # Original row unchanged.
    db.refresh(user1)
    assert user1.email == "old@example.com"


def test_email_conflict_orphans_other_row(db: Session):
    """When a user with no email claims an email already held by another active
    user, the other row's email is orphaned (set NULL) so the unique constraint holds.
    """
    auth_user_id_1 = str(uuid4())
    auth_user_id_2 = str(uuid4())
    contested_email = "contested@example.com"

    # user1: has an auth_user_id but no email yet.
    user1 = User(auth_user_id=auth_user_id_1, email=None, subscription_status=SubscriptionStatus.FREE)
    db.add(user1)
    db.commit()
    db.refresh(user1)

    # user2: an active user that currently owns the contested email.
    user2 = get_or_create_user_by_auth_id(db=db, auth_user_id=auth_user_id_2, email=contested_email)
    assert user2.email == contested_email.lower()

    # user1 (looked up by auth_user_id) now claims the contested email.
    updated_user1 = get_or_create_user_by_auth_id(db=db, auth_user_id=auth_user_id_1, email=contested_email)

    assert updated_user1.id == user1.id
    assert updated_user1.email == contested_email.lower()

    # user2's email was orphaned; its auth_user_id is untouched.
    db.refresh(user2)
    assert user2.email is None
    assert user2.auth_user_id == auth_user_id_2


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


def test_same_email_recall_is_idempotent(db: Session):
    """Re-calling with the same auth_user_id and email returns the same row, no error."""
    auth_user_id = str(uuid4())
    email = "stable@example.com"

    user1 = get_or_create_user_by_auth_id(db=db, auth_user_id=auth_user_id, email=email)
    assert user1.email == email.lower()

    user2 = get_or_create_user_by_auth_id(db=db, auth_user_id=auth_user_id, email=email)

    assert user2.id == user1.id
    assert user2.email == email.lower()
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

