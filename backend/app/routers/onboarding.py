from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models import User, OnboardingProfile, UserBookInteraction, Book, UserBookStatus
from app.schemas.onboarding import OnboardingPayload, OnboardingProfileResponse
from app.core.auth import get_current_user
from app.core.user_helpers import get_or_create_user_by_auth_id
from datetime import datetime
import uuid
import logging
import traceback


def is_uuid(s: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        UUID(s)
        return True
    except (ValueError, TypeError):
        return False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("", response_model=OnboardingProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_onboarding(
    payload: OnboardingPayload,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create or update onboarding profile for the authenticated user.
    """
    # Get or create local user from Supabase auth_user_id
    user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=current_user["auth_user_id"],
        email=current_user.get("email", ""),
    )
    user_id = user.id
    
    try:
        # Extract book_preferences before creating profile (since OnboardingProfile doesn't have this field)
        book_preferences = payload.book_preferences
        payload_dict = payload.model_dump(exclude={"book_preferences"})
        
        # Check if profile already exists
        existing_profile = db.query(OnboardingProfile).filter(
            OnboardingProfile.user_id == user_id
        ).first()
        
        if existing_profile:
            # Update existing profile
            for key, value in payload_dict.items():
                setattr(existing_profile, key, value)
            existing_profile.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing_profile)
        else:
            # Create new profile
            new_profile = OnboardingProfile(
                user_id=user_id,
                **payload_dict
            )
            db.add(new_profile)
            db.commit()
            db.refresh(new_profile)
            existing_profile = new_profile
        
        # Handle book preferences - create or update UserBookInteraction records
        if book_preferences:
            for pref in book_preferences:
                # Verify book exists - handle both UUID and external_id
                if is_uuid(pref.book_id):
                    # Lookup by UUID
                    book = db.query(Book).filter(Book.id == UUID(pref.book_id)).first()
                else:
                    # Lookup by external_id (for backward compatibility with slugs/external IDs)
                    book = db.query(Book).filter(Book.external_id == pref.book_id).first()
                
                if not book:
                    # Skip invalid book IDs but don't fail the whole request
                    logger.warning(f"Book not found for book_id: {pref.book_id}")
                    continue
                
                # Map string status to UserBookStatus enum
                status_map = {
                    "read_liked": UserBookStatus.READ_LIKED,
                    "read_disliked": UserBookStatus.READ_DISLIKED,
                    "interested": UserBookStatus.INTERESTED,
                    "not_interested": UserBookStatus.NOT_INTERESTED,
                }
                status_enum = status_map.get(pref.status)
                if not status_enum:
                    continue
                
                # Check if interaction already exists (use book.id which is the UUID)
                existing_interaction = db.query(UserBookInteraction).filter(
                    UserBookInteraction.user_id == user_id,
                    UserBookInteraction.book_id == book.id
                ).first()
                
                if existing_interaction:
                    # Update existing interaction
                    existing_interaction.status = status_enum
                    existing_interaction.updated_at = datetime.utcnow()
                else:
                    # Create new interaction (use book.id which is the UUID)
                    new_interaction = UserBookInteraction(
                        user_id=user_id,
                        book_id=book.id,
                        status=status_enum
                    )
                    db.add(new_interaction)
            
            db.commit()
        
        return OnboardingProfileResponse.model_validate(existing_profile)
    except HTTPException:
        # Re-raise HTTPExceptions as-is (they're already properly formatted)
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        logger.exception("Failed to save onboarding for user %s", user_id)
        # Return a readable error message instead of 500
        error_message = str(e) if str(e) else "An unexpected error occurred"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to save onboarding: {error_message}",
        )


@router.get("", response_model=OnboardingProfileResponse)
async def get_onboarding(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get onboarding profile for the authenticated user.
    """
    # Get local user from Supabase auth_user_id
    user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=current_user["auth_user_id"],
        email=current_user.get("email", ""),
    )
    
    profile = db.query(OnboardingProfile).filter(
        OnboardingProfile.user_id == user.id
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding profile not found",
        )
    
    return OnboardingProfileResponse.model_validate(profile)

