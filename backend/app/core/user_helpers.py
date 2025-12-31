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
    endpoint_path: str = "",
    email_verified: bool = False,
) -> User:
    """
    Get or create a local User record from Supabase auth_user_id.
    
    Supabase Auth is the source of truth. This function ensures our app-level users row
    is always keyed by auth_user_id (Supabase "sub").
    
    Safe Automatic Relinking:
    - If user not found by auth_user_id but found by email (case-insensitive match),
      automatically relinks the existing user to the current auth_user_id.
    - This handles cases where Supabase auth_user_id changes but email remains the same.
    
    Logic:
    1. Find user by auth_user_id first (primary lookup) - return if found
    2. If not found AND email exists, query by email with row lock (FOR UPDATE)
    3. If found by email:
       - Legacy user (no auth_user_id) → link to current auth_user_id
       - Different auth_user_id → SAFE RELINK (update auth_user_id)
    4. If not found, create new user
    
    Idempotent and safe under concurrent requests with row locking and IntegrityError handling.
    
    Args:
        db: Database session
        auth_user_id: Supabase auth user ID (JWT sub claim)
        email: Email from JWT token (for relinking)
        endpoint_path: Endpoint path for logging (e.g., "POST /api/onboarding")
        email_verified: Whether email is verified in token (for guardrails)
    
    Returns:
        User object (existing or newly created)
    
    Raises:
        HTTPException(409): Only for truly unsafe conflicts (auth_user_id already linked to different email)
    """
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # Normalize email once
    normalized_email = email.lower().strip() if email else None
    
    # Step A: Try to find existing user by auth_user_id (primary lookup)
    user = db.query(User).filter(User.auth_user_id == auth_user_id).one_or_none()
    
    if user:
        if DEBUG:
            logger.info(f"[get_or_create_user_by_auth_id] found_by_auth_user_id: auth_user_id={auth_user_id}, user_id={user.id}")
        
        # Check for email mismatch: if token email differs from DB email, this is unsafe
        normalized_db_email = user.email.lower().strip() if user.email else None
        if normalized_email and normalized_db_email and normalized_email != normalized_db_email:
            # Unsafe: auth_user_id already linked to different email
            logger.error(
                f"[AUTH_EMAIL_MISMATCH] endpoint={endpoint_path}, "
                f"token_auth_user_id={auth_user_id}, token_email={normalized_email}, "
                f"db_email={normalized_db_email}, user_id={user.id}"
            )
            raise HTTPException(
                status_code=409,
                detail="email_mismatch_cannot_link"
            )
        
        # Update email if provided and different (safe case: email matches or user has no email)
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
    # Check if a row exists by email (with row lock to prevent races)
    existing_by_email = None
    if normalized_email:
        # Use FOR UPDATE to lock the row during relink operation
        existing_by_email = db.query(User).filter(
            func.lower(User.email) == normalized_email
        ).with_for_update().one_or_none()
    
    # Step B: User does NOT exist by auth_user_id
    # Check if a row exists by email
    existing_by_email = None
    if normalized_email:
        existing_by_email = db.query(User).filter(
            func.lower(User.email) == normalized_email
        ).one_or_none()
    
    if existing_by_email:
        if not existing_by_email.auth_user_id:
            # Case 2a: Legacy row (no auth_user_id) - link it to this auth_user_id
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
            # Case 2b: Email exists with different auth_user_id - SAFE AUTOMATIC RELINK
            # Guardrails: require email to be present and match (case-insensitive)
            if not normalized_email:
                # No email claim - cannot safely relink
                logger.error(
                    f"[AUTH_RELINK_BLOCKED] endpoint={endpoint_path}, "
                    f"token_auth_user_id={auth_user_id}, "
                    f"db_user_id={existing_by_email.id}, "
                    f"db_auth_user_id={existing_by_email.auth_user_id}, "
                    f"reason=email_claim_missing"
                )
                raise HTTPException(
                    status_code=409,
                    detail="email_claim_missing_cannot_link"
                )
            
            # Verify email matches (case-insensitive) - this is the safety check
            if existing_by_email.email and existing_by_email.email.lower() != normalized_email:
                # This shouldn't happen due to our query, but double-check
                logger.error(
                    f"[AUTH_RELINK_BLOCKED] endpoint={endpoint_path}, "
                    f"token_auth_user_id={auth_user_id}, token_email={normalized_email}, "
                    f"db_user_id={existing_by_email.id}, db_auth_user_id={existing_by_email.auth_user_id}, "
                    f"db_email={existing_by_email.email}, reason=email_mismatch"
                )
                raise HTTPException(
                    status_code=409,
                    detail="email_mismatch_cannot_link"
                )
            
            # Check if auth_user_id already exists (unsafe conflict)
            conflicting_user = db.query(User).filter(
                User.auth_user_id == auth_user_id
            ).one_or_none()
            
            if conflicting_user and conflicting_user.id != existing_by_email.id:
                # Unsafe: auth_user_id already linked to different email
                logger.error(
                    f"[AUTH_CONFLICT_409] endpoint={endpoint_path}, "
                    f"token_auth_user_id={auth_user_id}, token_email={normalized_email}, "
                    f"existing_user_id={conflicting_user.id}, existing_email={conflicting_user.email}, "
                    f"relink_target_user_id={existing_by_email.id}, relink_target_email={existing_by_email.email}"
                )
                raise HTTPException(
                    status_code=409,
                    detail="auth_user_id_already_linked_to_different_email"
                )
            
            # Safe relink: update existing user's auth_user_id
            old_auth_user_id = existing_by_email.auth_user_id
            existing_by_email.auth_user_id = auth_user_id
            
            try:
                db.commit()
                db.refresh(existing_by_email)
                
                # Audit log: structured relink event
                logger.warning(
                    f"[AUTH_RELINK] endpoint={endpoint_path}, "
                    f"email={normalized_email}, "
                    f"old_auth_user_id={old_auth_user_id}, "
                    f"new_auth_user_id={auth_user_id}, "
                    f"user_id={existing_by_email.id}, "
                    f"email_verified={email_verified}"
                )
                
                if DEBUG:
                    logger.info(f"[get_or_create_user_by_auth_id] relinked_user: user_id={existing_by_email.id}, auth_user_id={auth_user_id}")
                
                return existing_by_email
            except IntegrityError as e:
                # Race condition: another thread may have created this auth_user_id
                db.rollback()
                # Re-fetch by auth_user_id
                user = db.query(User).filter(User.auth_user_id == auth_user_id).one_or_none()
                if user:
                    if DEBUG:
                        logger.info(f"[get_or_create_user_by_auth_id] race_refetch_after_relink: auth_user_id={auth_user_id}, user_id={user.id}")
                    return user
                # If still not found, check if it's a unique constraint violation on auth_user_id
                # This would indicate a true conflict
                raise
    
    # Step C: No user found by auth_user_id or email - create new user
    # If no email provided, we cannot create a user (should not happen in normal flow)
    if not normalized_email:
        logger.error(
            f"[AUTH_CREATE_BLOCKED] endpoint={endpoint_path}, "
            f"token_auth_user_id={auth_user_id}, "
            f"reason=email_claim_missing"
        )
        raise HTTPException(
            status_code=400,
            detail="email_claim_missing_cannot_create_user"
        )
    
    normalized_status = _normalize_subscription_status(SubscriptionStatus.FREE)
    final_email = normalized_email
    
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





