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
import uuid

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
    
    Supabase Auth is the source of truth. This function ensures our app-level users row
    is always keyed by auth_user_id (Supabase "sub").
    
    Logic:
    1. Find user by auth_user_id first (primary lookup)
    2. If found, update email if changed (handling conflicts by orphaning)
    3. If not found, create new user or link existing email-based row
    
    Idempotent and safe under concurrent requests with IntegrityError handling.
    """
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # Normalize email to lowercase and strip
    normalized_email = email.lower().strip() if email else None
    
    # Step A: Try to find existing user by auth_user_id (primary lookup)
    user = db.query(User).filter(User.auth_user_id == auth_user_id).one_or_none()
    
    if user:
        if DEBUG:
            logger.info(f"[get_or_create_user_by_auth_id] found_by_auth_user_id: auth_user_id={auth_user_id}, user_id={user.id}")
        
        # Update email if provided and different
        if normalized_email and user.email != normalized_email:
            # Check if another row exists with that email and different auth_user_id
            other = db.query(User).filter(
                func.lower(User.email) == normalized_email,
                User.auth_user_id != auth_user_id,
                User.auth_user_id.isnot(None)
            ).one_or_none()
            
            if other:
                # Merge strategy: orphan the other row's email
                # Since email is nullable, we can set it to NULL
                other_email_backup = other.email
                other.email = None
                db.flush()  # Flush to apply the change
                
                logger.warning(
                    f"[EMAIL_ORPHAN] Orphaned email from conflicting row: "
                    f"email={other_email_backup}, other_user_id={other.id}, "
                    f"other_auth_user_id={other.auth_user_id}, target_auth_user_id={auth_user_id}"
                )
            
            # Now set the email on the correct user
            user.email = normalized_email
            try:
                db.commit()
                db.refresh(user)
            except IntegrityError:
                # Race condition: another thread may have set this email
                db.rollback()
                # Re-fetch by auth_user_id and return
                user = db.query(User).filter(User.auth_user_id == auth_user_id).one_or_none()
                if user:
                    return user
                raise
        
        return user
    
    # Step B: User does NOT exist by auth_user_id
    # Check if a row exists by email
    existing_by_email = None
    if normalized_email:
        existing_by_email = db.query(User).filter(
            func.lower(User.email) == normalized_email
        ).one_or_none()
    
    if existing_by_email:
        if not existing_by_email.auth_user_id:
            # Legacy row: link it to this auth_user_id
            existing_by_email.auth_user_id = auth_user_id
            try:
                db.commit()
                db.refresh(existing_by_email)
                if DEBUG:
                    logger.info(f"[get_or_create_user_by_auth_id] linked_legacy_user: user_id={existing_by_email.id}, auth_user_id={auth_user_id}")
                return existing_by_email
            except IntegrityError:
                # Race condition: another thread may have set this auth_user_id
                db.rollback()
                # Re-fetch by auth_user_id
                user = db.query(User).filter(User.auth_user_id == auth_user_id).one_or_none()
                if user:
                    return user
                raise
        elif existing_by_email.auth_user_id != auth_user_id:
            # Email is already linked to a different auth_user_id
            # Check if email relink is allowed
            allow_email_relink = os.getenv("ALLOW_EMAIL_RELINK", "false").lower() == "true"
            
            if not allow_email_relink:
                # TEMP DIAGNOSTIC: Log detailed info before raising 409
                # Extract endpoint from request context if available (passed via get_current_user)
                endpoint = getattr(db, '_endpoint_context', 'unknown_endpoint')
                
                logger.error(
                    f"[409_DIAGNOSTIC] endpoint={endpoint}, "
                    f"token_auth_user_id={auth_user_id}, "
                    f"token_email={normalized_email}, "
                    f"db_user_id={existing_by_email.id}, "
                    f"db_auth_user_id={existing_by_email.auth_user_id}, "
                    f"db_email={existing_by_email.email}"
                )
                
                # Raise 409 conflict - email already linked to different account
                logger.warning(
                    f"[EMAIL_CONFLICT_409] email={normalized_email} "
                    f"is already linked to auth_user_id={existing_by_email.auth_user_id}, "
                    f"attempted auth_user_id={auth_user_id}"
                )
                raise HTTPException(
                    status_code=409,
                    detail="email_already_linked_to_different_account"
                )
            
            # Email relink is enabled: auto-repair by repurposing the existing row
            old_auth_user_id = existing_by_email.auth_user_id
            existing_by_email.auth_user_id = auth_user_id
            
            try:
                db.commit()
                db.refresh(existing_by_email)
                
                logger.warning(
                    f"[EMAIL_RELINK] Relinked email: email={normalized_email}, "
                    f"old_auth_user_id={old_auth_user_id}, new_auth_user_id={auth_user_id}, "
                    f"user_id={existing_by_email.id}"
                )
                
                if DEBUG:
                    logger.info(f"[get_or_create_user_by_auth_id] repaired_user: user_id={existing_by_email.id}, auth_user_id={auth_user_id}")
                
                return existing_by_email
            except IntegrityError:
                # Race condition: another thread may have created this auth_user_id
                db.rollback()
                # Re-fetch by auth_user_id
                user = db.query(User).filter(User.auth_user_id == auth_user_id).one_or_none()
                if user:
                    if DEBUG:
                        logger.info(f"[get_or_create_user_by_auth_id] race_refetch_after_repair: auth_user_id={auth_user_id}, user_id={user.id}")
                    return user
                raise
    
    # Step C: Create new user row
    normalized_status = _normalize_subscription_status(SubscriptionStatus.FREE)
    
    # Use normalized email or generate placeholder
    final_email = normalized_email or f"user_{auth_user_id}@readar.local"
    
    new_user = User(
        auth_user_id=auth_user_id,
        email=final_email,
        subscription_status=normalized_status,
    )
    
    # Runtime safety assertion: verify the value before commit
    if hasattr(new_user, 'subscription_status'):
        actual_value = new_user.subscription_status
        if isinstance(actual_value, SubscriptionStatus):
            actual_str = actual_value.value
        else:
            actual_str = str(actual_value)
        
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
            logger.info(f"[get_or_create_user_by_auth_id] race_refetch: IntegrityError on create, re-fetching")
        
        # Race condition safety: re-fetch by auth_user_id first (primary)
        user = db.query(User).filter(User.auth_user_id == auth_user_id).one_or_none()
        if user:
            if DEBUG:
                logger.info(f"[get_or_create_user_by_auth_id] race_refetch_by_auth: auth_user_id={auth_user_id}, user_id={user.id}")
            return user
        
        # Also try by email as fallback
        if normalized_email:
            user = db.query(User).filter(
                func.lower(User.email) == normalized_email
            ).one_or_none()
            if user:
                if DEBUG:
                    logger.info(f"[get_or_create_user_by_auth_id] race_refetch_by_email: email={normalized_email}, user_id={user.id}")
                return user
        
        # If we still can't find it, re-raise the original error
        raise





