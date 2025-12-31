"""
Helper functions for user management with Supabase auth.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models import User, SubscriptionStatus
from uuid import UUID
import logging
import os

logger = logging.getLogger(__name__)


def _normalize_subscription_status(value) -> SubscriptionStatus:
    """
    Normalize subscription status to the correct enum value.
    
    Guards against case mismatches (e.g., "FREE" -> SubscriptionStatus.FREE which maps to "free").
    Accepts enum objects, enum values (strings), or enum names (strings).
    
    Rules:
    - If input is "FREE"/"Free"/"free" -> normalize to SubscriptionStatus.FREE ("free")
    - If input is None -> default to SubscriptionStatus.FREE ("free")
    - If input is unknown -> default to SubscriptionStatus.FREE ("free") and log warning
    """
    if value is None:
        return SubscriptionStatus.FREE
    
    if isinstance(value, SubscriptionStatus):
        return value
    
    if isinstance(value, str):
        value_upper = value.upper()
        value_lower = value.lower()
        
        # Try to match by enum name (e.g., "FREE" -> SubscriptionStatus.FREE)
        for status in SubscriptionStatus:
            if status.name == value_upper:
                return status
        
        # Try to match by enum value (e.g., "free" -> SubscriptionStatus.FREE)
        for status in SubscriptionStatus:
            if status.value == value_lower:
                return status
    
    # Default to FREE if we can't normalize
    logger.warning(f"Could not normalize subscription_status={value} (type={type(value)}), defaulting to FREE")
    return SubscriptionStatus.FREE


def get_or_create_user_by_auth_id(
    db: Session,
    auth_user_id: str,
    email: str = "",
) -> User:
    """
    Get or create a local User record from Supabase auth_user_id.
    
    This creates a stable mapping between Supabase users and local database users.
    On first request from a Supabase user, creates a local user row.
    
    Idempotent and safe under concurrent requests:
    1. First tries to find by auth_user_id
    2. If not found, tries to find by email (case-insensitive)
    3. If not found, creates new user with race condition handling
    """
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # Step A: Try to find existing user by auth_user_id
    user = db.query(User).filter(User.auth_user_id == auth_user_id).one_or_none()
    
    if user:
        if DEBUG:
            logger.info(f"[get_or_create_user_by_auth_id] found_by_auth_user_id: auth_user_id={auth_user_id}, user_id={user.id}")
        
        # Update email if provided and different (normalize to lowercase)
        if email:
            normalized_email = email.lower().strip()
            if user.email != normalized_email:
                user.email = normalized_email
                db.commit()
                db.refresh(user)
        return user
    
    # Step B: If not found, try to find by email (case-insensitive)
    if email:
        user = db.query(User).filter(func.lower(User.email) == func.lower(email)).one_or_none()
        
        if user:
            if DEBUG:
                logger.info(f"[get_or_create_user_by_auth_id] found_by_email_linked: email={email}, user_id={user.id}, existing_auth_user_id={user.auth_user_id}")
            
            # Link this existing account to the auth user id
            if not user.auth_user_id:
                user.auth_user_id = auth_user_id
                db.commit()
                db.refresh(user)
                if DEBUG:
                    logger.info(f"[get_or_create_user_by_auth_id] linked_existing_user: user_id={user.id}, auth_user_id={auth_user_id}")
            elif user.auth_user_id != auth_user_id:
                # Do NOT overwrite a different auth_user_id; raise 409 with safe message
                raise HTTPException(
                    status_code=409,
                    detail="email_already_linked_to_different_account"
                )
            return user
    
    # Step C: Create new user row
    # Normalize subscription_status to ensure it's the correct enum value
    normalized_status = _normalize_subscription_status(SubscriptionStatus.FREE)
    
    # Normalize email to lowercase for consistency
    normalized_email = (email.lower().strip() if email else f"user_{auth_user_id}@readar.local")
    
    new_user = User(
        auth_user_id=auth_user_id,
        email=normalized_email,
        subscription_status=normalized_status,  # Use normalized enum, not raw value
    )
    
    # Runtime safety assertion: verify the value before commit
    if hasattr(new_user, 'subscription_status'):
        actual_value = new_user.subscription_status
        if isinstance(actual_value, SubscriptionStatus):
            actual_str = actual_value.value
        else:
            actual_str = str(actual_value)
        
        # Assert that we have the correct enum value (lowercase "free")
        if actual_str != "free":
            logger.error(
                f"[SAFETY CHECK FAILED] subscription_status has wrong value: "
                f"'{actual_str}' (expected 'free'). Normalizing..."
            )
            new_user.subscription_status = _normalize_subscription_status(actual_value)
    
    db.add(new_user)
    
    try:
        db.commit()
        db.refresh(new_user)
        
        if DEBUG:
            logger.info(f"[get_or_create_user_by_auth_id] created_new: auth_user_id={auth_user_id}, user_id={new_user.id}, email={new_user.email}")
        
        logger.info(f"Created new user for auth_user_id={auth_user_id}, local_id={new_user.id}, subscription_status={new_user.subscription_status.value}")
        return new_user
        
    except IntegrityError as e:
        db.rollback()
        
        if DEBUG:
            logger.info(f"[get_or_create_user_by_auth_id] race_refetch: IntegrityError on create, re-fetching by email={email}")
        
        # Race condition safety: re-fetch by email then by auth_user_id and return if found
        if email:
            normalized_email = email.lower().strip()
            user = db.query(User).filter(func.lower(User.email) == func.lower(email)).one_or_none()
            
            if user:
                # Normalize email if needed
                if user.email != normalized_email:
                    user.email = normalized_email
                
                if not user.auth_user_id:
                    user.auth_user_id = auth_user_id
                    db.commit()
                    db.refresh(user)
                    if DEBUG:
                        logger.info(f"[get_or_create_user_by_auth_id] race_refetch_linked: user_id={user.id}, auth_user_id={auth_user_id}")
                elif user.auth_user_id != auth_user_id:
                    # Conflict: email already linked to different auth_user_id
                    raise HTTPException(
                        status_code=409,
                        detail="email_already_linked_to_different_account"
                    )
                else:
                    # Email already normalized, just commit if we changed it
                    if user.email != normalized_email:
                        db.commit()
                        db.refresh(user)
                return user
        
        # Also try by auth_user_id in case another thread created it
        user = db.query(User).filter(User.auth_user_id == auth_user_id).one_or_none()
        if user:
            if DEBUG:
                logger.info(f"[get_or_create_user_by_auth_id] race_refetch_by_auth: auth_user_id={auth_user_id}, user_id={user.id}")
            return user
        
        # If we still can't find it, re-raise the original error
        raise





