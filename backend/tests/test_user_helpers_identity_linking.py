"""Tests for safe automatic identity linking in user_helpers."""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import User, SubscriptionStatus
from app.core.user_helpers import get_or_create_user_by_auth_id


def test_fresh_user_creates_new_user(db: Session):
    """Test 1: Fresh user - no user by auth_user_id, no user by email → creates user → 200"""
    auth_user_id = str(uuid4())
    email = "fresh@example.com"
    
    # No user exists
    assert db.query(User).filter(User.auth_user_id == auth_user_id).one_or_none() is None
    assert db.query(User).filter(User.email == email).one_or_none() is None
    
    # Create user
    user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id,
        email=email,
        endpoint_path="POST /api/onboarding",
        email_verified=True,
    )
    
    # Verify user was created
    assert user is not None
    assert user.auth_user_id == auth_user_id
    assert user.email == email.lower()  # Normalized to lowercase
    assert user.subscription_status == SubscriptionStatus.FREE
    
    # Verify persisted
    db.refresh(user)
    assert user.auth_user_id == auth_user_id
    assert user.email == email.lower()


def test_normal_login_same_identity(db: Session):
    """Test 2: Normal login same identity - user exists by auth_user_id → returns user → 200"""
    auth_user_id = str(uuid4())
    email = "existing@example.com"
    
    # Create user first
    user1 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id,
        email=email,
    )
    
    # Login again with same auth_user_id
    user2 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id,
        email=email,
        endpoint_path="POST /api/onboarding",
        email_verified=True,
    )
    
    # Should be the same user
    assert user1.id == user2.id
    assert user2.auth_user_id == auth_user_id
    assert user2.email == email.lower()


def test_safe_automatic_relink(db: Session):
    """Test 3: The problematic case (must pass now) - DB user exists by email with old auth_user_id,
    token has same email with NEW auth_user_id → relink occurs, returns user, no 409"""
    email = "relink@example.com"
    old_auth_user_id = str(uuid4())
    new_auth_user_id = str(uuid4())
    
    # Create user with old auth_user_id
    old_user = User(
        email=email,
        auth_user_id=old_auth_user_id,
        subscription_status=SubscriptionStatus.FREE,
    )
    db.add(old_user)
    db.commit()
    db.refresh(old_user)
    
    assert old_user.auth_user_id == old_auth_user_id
    assert old_user.email == email.lower()
    
    # Now try to get/create with new auth_user_id but same email
    # This should trigger safe automatic relink
    relinked_user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=new_auth_user_id,
        email=email,
        endpoint_path="POST /api/onboarding",
        email_verified=True,
    )
    
    # Should be the same user row, but with updated auth_user_id
    assert relinked_user.id == old_user.id
    assert relinked_user.auth_user_id == new_auth_user_id
    assert relinked_user.email == email.lower()
    
    # Verify old auth_user_id no longer exists
    old_user_check = db.query(User).filter(User.auth_user_id == old_auth_user_id).one_or_none()
    assert old_user_check is None
    
    # Verify new auth_user_id exists
    new_user_check = db.query(User).filter(User.auth_user_id == new_auth_user_id).one_or_none()
    assert new_user_check is not None
    assert new_user_check.id == old_user.id


def test_unsafe_conflict_auth_user_id_already_linked(db: Session):
    """Test 4: Unsafe conflict - row exists with auth_user_id A and email a@example.com,
    token has auth_user_id A but email b@example.com → 409 email_mismatch_cannot_link"""
    auth_user_id = str(uuid4())
    email_a = "a@example.com"
    email_b = "b@example.com"
    
    # Create user with auth_user_id and email_a
    existing_user = User(
        email=email_a,
        auth_user_id=auth_user_id,
        subscription_status=SubscriptionStatus.FREE,
    )
    db.add(existing_user)
    db.commit()
    db.refresh(existing_user)
    
    # Now try to get/create with same auth_user_id but different email
    # This should raise 409 because auth_user_id is already linked to different email
    with pytest.raises(HTTPException) as exc_info:
        get_or_create_user_by_auth_id(
            db=db,
            auth_user_id=auth_user_id,
            email=email_b,
            endpoint_path="POST /api/onboarding",
            email_verified=True,
        )
    
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "email_mismatch_cannot_link"
    
    # Verify original user unchanged
    db.refresh(existing_user)
    assert existing_user.auth_user_id == auth_user_id
    assert existing_user.email == email_a.lower()


def test_relink_without_email_raises_error(db: Session):
    """Test that relink without email claim raises error."""
    email = "noemail@example.com"
    old_auth_user_id = str(uuid4())
    new_auth_user_id = str(uuid4())
    
    # Create user with old auth_user_id
    old_user = User(
        email=email,
        auth_user_id=old_auth_user_id,
        subscription_status=SubscriptionStatus.FREE,
    )
    db.add(old_user)
    db.commit()
    
    # Try to relink without email (empty string)
    # This should raise 400 because we can't create a user without email
    with pytest.raises(HTTPException) as exc_info:
        get_or_create_user_by_auth_id(
            db=db,
            auth_user_id=new_auth_user_id,
            email="",  # No email claim
            endpoint_path="POST /api/onboarding",
            email_verified=False,
        )
    
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "email_claim_missing_cannot_create_user"


def test_create_user_without_email_raises_error(db: Session):
    """Test that creating new user without email raises error."""
    auth_user_id = str(uuid4())
    
    # Try to create user without email
    with pytest.raises(HTTPException) as exc_info:
        get_or_create_user_by_auth_id(
            db=db,
            auth_user_id=auth_user_id,
            email="",  # No email claim
            endpoint_path="POST /api/onboarding",
            email_verified=False,
        )
    
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "email_claim_missing_cannot_create_user"


def test_legacy_user_linking_still_works(db: Session):
    """Test that legacy users (no auth_user_id) still get linked correctly."""
    email = "legacy@example.com"
    auth_user_id = str(uuid4())
    
    # Create legacy user (no auth_user_id)
    legacy_user = User(
        email=email,
        subscription_status=SubscriptionStatus.FREE,
    )
    db.add(legacy_user)
    db.commit()
    db.refresh(legacy_user)
    
    assert legacy_user.auth_user_id is None
    
    # Link legacy user
    linked_user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id,
        email=email,
        endpoint_path="POST /api/onboarding",
        email_verified=True,
    )
    
    # Should be the same user, now with auth_user_id
    assert linked_user.id == legacy_user.id
    assert linked_user.auth_user_id == auth_user_id
    assert linked_user.email == email.lower()


def test_relink_case_insensitive_email(db: Session):
    """Test that relink works with case-insensitive email matching."""
    email_upper = "CASE@EXAMPLE.COM"
    email_lower = "case@example.com"
    old_auth_user_id = str(uuid4())
    new_auth_user_id = str(uuid4())
    
    # Create user with lowercase email
    old_user = User(
        email=email_lower,
        auth_user_id=old_auth_user_id,
        subscription_status=SubscriptionStatus.FREE,
    )
    db.add(old_user)
    db.commit()
    db.refresh(old_user)
    
    # Try to relink with uppercase email (should match case-insensitively)
    relinked_user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=new_auth_user_id,
        email=email_upper,
        endpoint_path="POST /api/onboarding",
        email_verified=True,
    )
    
    # Should relink successfully
    assert relinked_user.id == old_user.id
    assert relinked_user.auth_user_id == new_auth_user_id
    assert relinked_user.email == email_lower  # Normalized to lowercase


def test_concurrent_relink_attempts(db: Session):
    """Test 5 (optional): Concurrency - two requests attempt to relink at same time → one wins cleanly, no duplicates.
    
    Note: This is a simplified test. True concurrency testing would require threading/multiprocessing.
    """
    email = "concurrent@example.com"
    old_auth_user_id = str(uuid4())
    new_auth_user_id_1 = str(uuid4())
    new_auth_user_id_2 = str(uuid4())
    
    # Create user with old auth_user_id
    old_user = User(
        email=email,
        auth_user_id=old_auth_user_id,
        subscription_status=SubscriptionStatus.FREE,
    )
    db.add(old_user)
    db.commit()
    db.refresh(old_user)
    
    # First relink attempt
    relinked_user_1 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=new_auth_user_id_1,
        email=email,
        endpoint_path="POST /api/onboarding",
        email_verified=True,
    )
    
    assert relinked_user_1.id == old_user.id
    assert relinked_user_1.auth_user_id == new_auth_user_id_1
    
    # Second relink attempt (simulating concurrent request)
    # This should find the user already relinked and return it
    # OR if it tries to relink again, should handle gracefully
    relinked_user_2 = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=new_auth_user_id_2,
        email=email,
        endpoint_path="POST /api/onboarding",
        email_verified=True,
    )
    
    # Should be the same user, now with second auth_user_id
    assert relinked_user_2.id == old_user.id
    assert relinked_user_2.auth_user_id == new_auth_user_id_2
    
    # Verify only one user exists with this email
    users_with_email = db.query(User).filter(User.email == email.lower()).all()
    assert len(users_with_email) == 1
    assert users_with_email[0].id == old_user.id

