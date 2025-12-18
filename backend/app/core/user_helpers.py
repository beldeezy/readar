"""
Helper functions for user management with Supabase auth.
"""
from sqlalchemy.orm import Session
from app.models import User
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


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
    new_user = User(
        auth_user_id=auth_user_id,
        email=email or f"user_{auth_user_id}@readar.local",
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"Created new user for auth_user_id={auth_user_id}, local_id={new_user.id}")
    return new_user





