"""
Helper functions for user management with Supabase auth.
"""
from sqlalchemy.orm import Session
from app.models import User, SubscriptionStatus
from uuid import UUID
import logging

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
    """
    # Try to find existing user by auth_user_id
    user = db.query(User).filter(User.auth_user_id == auth_user_id).first()
    
    if user:
        # Update email if provided and different
        if email and user.email != email:
            user.email = email
            db.commit()
            db.refresh(user)
        return user
    
    # User doesn't exist, create new one
    # Note: We don't set password_hash for Supabase users
    
    # Normalize subscription_status to ensure it's the correct enum value
    # This is a safety measure to prevent "FREE" string from being passed
    normalized_status = _normalize_subscription_status(SubscriptionStatus.FREE)
    
    new_user = User(
        auth_user_id=auth_user_id,
        email=email or f"user_{auth_user_id}@readar.local",
        subscription_status=normalized_status,  # Use normalized enum, not raw value
    )
    
    # Runtime safety assertion: verify the value before commit
    if hasattr(new_user, 'subscription_status'):
        actual_value = new_user.subscription_status
        if isinstance(actual_value, SubscriptionStatus):
            actual_str = actual_value.value
        else:
            actual_str = str(actual_value)
        
        # Log in debug mode
        logger.debug(
            f"[SAFETY] Creating user with subscription_status: "
            f"enum={actual_value}, value={actual_str}, type={type(actual_value)}"
        )
        
        # Assert that we have the correct enum value (lowercase "free")
        if actual_str != "free":
            logger.error(
                f"[SAFETY CHECK FAILED] subscription_status has wrong value: "
                f"'{actual_str}' (expected 'free'). Normalizing..."
            )
            new_user.subscription_status = _normalize_subscription_status(actual_value)
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Final verification after commit
    if new_user.subscription_status.value != "free":
        logger.error(
            f"[CRITICAL] User created with wrong subscription_status: "
            f"{new_user.subscription_status.value} (expected 'free')"
        )
    
    logger.info(f"Created new user for auth_user_id={auth_user_id}, local_id={new_user.id}, subscription_status={new_user.subscription_status.value}")
    return new_user





