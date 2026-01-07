from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models import User, OnboardingProfile, UserBookInteraction, Book, UserBookStatus, BusinessStage
from app.schemas.onboarding import OnboardingPayload, OnboardingProfileResponse
from app.core.auth import get_current_user
from app.utils.instrumentation import log_event_best_effort
from datetime import datetime
import uuid
import logging
import traceback
import os


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
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create or update onboarding profile for the authenticated user.

    Extracts full_name from Supabase user metadata if not provided in payload.
    """
    # Debug logging (only when DEBUG env var is set)
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    user_id = user.id
    if DEBUG:
        payload_dict_debug = payload.model_dump()
        logger.info(
            "[DEBUG POST /api/onboarding] "
            f"user_id={user_id}, "
            f"payload_keys={list(payload_dict_debug.keys())}, "
            f"business_stage={payload_dict_debug.get('business_stage', 'N/A')}, "
            f"entrepreneur_status={payload_dict_debug.get('entrepreneur_status', 'N/A')}, "
            f"subscription_status={user.subscription_status.value if hasattr(user, 'subscription_status') else 'N/A'}"
        )

    try:
        # Extract book_preferences before creating profile (since OnboardingProfile doesn't have this field)
        book_preferences = payload.book_preferences
        # Use exclude_unset=True to only include fields that were explicitly provided in the request
        # This prevents overwriting existing fields with None/empty values
        payload_dict = payload.model_dump(exclude={"book_preferences"}, exclude_unset=True)

        # Extract full_name from Supabase user metadata if not provided or empty
        if not payload_dict.get("full_name") or not payload_dict["full_name"].strip():
            # Try to get from JWT payload stored in request.state
            jwt_payload = getattr(request.state, "supabase_jwt_payload", {})
            user_metadata = jwt_payload.get("user_metadata", {})

            # Try multiple possible fields in order of preference
            full_name = (
                user_metadata.get("full_name") or
                user_metadata.get("name") or
                jwt_payload.get("name") or
                user.email.split("@")[0] if user.email else "User"  # Fallback to email username
            )

            if DEBUG:
                logger.info(f"[DEBUG] Extracted full_name from metadata: {full_name}")

            payload_dict["full_name"] = full_name

        # Note: business_stage is already normalized by Pydantic validator in OnboardingPayload schema

        # Check if profile already exists
        existing_profile = db.query(OnboardingProfile).filter(
            OnboardingProfile.user_id == user_id
        ).first()

        if existing_profile:
            # Update existing profile with only the fields that were provided
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
        
        # Log onboarding completion event (best-effort, non-blocking)
        log_event_best_effort(
            event_name="onboarding_completed",
            user_id=user_id,
            properties={
                "business_model": existing_profile.business_model,
                "business_stage": existing_profile.business_stage.value if hasattr(existing_profile.business_stage, 'value') else str(existing_profile.business_stage),
                "org_size": existing_profile.org_size,
            },
        )
        
        return OnboardingProfileResponse.model_validate(existing_profile)
    except HTTPException:
        # Re-raise HTTPExceptions as-is (they're already properly formatted)
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        error_type = type(e).__name__
        error_message = str(e) if str(e) else "An unexpected error occurred"
        
        # Debug logging with full stacktrace
        logger.exception(
            f"[DEBUG POST /api/onboarding ERROR] "
            f"user_id={user_id}, "
            f"error_type={error_type}, "
            f"error={error_message}"
        )
        
        # Return JSON response with error details (safe, no secrets)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "detail": "internal_error",
                "error_type": error_type,
                "error": error_message,
            },
        )


@router.get("", response_model=OnboardingProfileResponse)
async def get_onboarding(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get onboarding profile for the authenticated user.
    """
    # Debug logging (only when DEBUG env var is set)
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    user_id = user.id
    if DEBUG:
        logger.info(f"[DEBUG GET /api/onboarding] user_id={user_id}")
    
    try:
        profile = db.query(OnboardingProfile).filter(
            OnboardingProfile.user_id == user.id
        ).first()
        
        if not profile:
            if DEBUG:
                logger.warning(f"[DEBUG GET /api/onboarding] user_id={user_id} - profile not found (404)")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding profile not found",
            )
        
        if DEBUG:
            logger.info(f"[DEBUG GET /api/onboarding] user_id={user_id} - profile found (200)")
        
        return OnboardingProfileResponse.model_validate(profile)
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        # Log any unexpected DB errors
        logger.exception(
            f"[DEBUG GET /api/onboarding ERROR] user_id={user_id}, "
            f"error_type={type(e).__name__}, error={str(e)}"
        )
        raise


@router.patch("", response_model=OnboardingProfileResponse)
async def patch_onboarding(
    payload: OnboardingPatchPayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Incrementally update onboarding profile for the authenticated user.
    This endpoint supports partial updates - only provided fields will be updated.
    """
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    user_id = user.id
    if DEBUG:
        logger.info(f"[DEBUG PATCH /api/onboarding] user_id={user_id}, payload={payload.model_dump(exclude_unset=True)}")

    try:
        # Get or create profile
        profile = db.query(OnboardingProfile).filter(
            OnboardingProfile.user_id == user_id
        ).first()

        if not profile:
            # Create new profile with only the provided fields
            # Use exclude_unset=True to only include fields explicitly set in the request
            payload_dict = payload.model_dump(exclude_unset=True)
            profile = OnboardingProfile(
                user_id=user_id,
                **payload_dict
            )
            db.add(profile)
        else:
            # Update existing profile with only provided fields
            # Use exclude_unset=True to avoid overwriting existing data with None/empty values
            payload_dict = payload.model_dump(exclude_unset=True)
            for key, value in payload_dict.items():
                setattr(profile, key, value)
            profile.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(profile)

        return OnboardingProfileResponse.model_validate(profile)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.exception(
            f"[DEBUG PATCH /api/onboarding ERROR] user_id={user_id}, "
            f"error_type={type(e).__name__}, error={str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "detail": "internal_error",
                "error_type": type(e).__name__,
                "error": str(e),
            },
        )


@router.post("/book-interactions", status_code=status.HTTP_200_OK)
async def save_book_interactions(
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Save book interactions (used during chat onboarding for book calibration step).
    Expects payload: { "books": [{ "external_id": str, "status": str }, ...] }
    """
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    user_id = user.id

    try:
        books_data = payload.get("books", [])

        if DEBUG:
            logger.info(f"[DEBUG POST /api/onboarding/book-interactions] user_id={user_id}, book_count={len(books_data)}")

        status_map = {
            "read_liked": UserBookStatus.READ_LIKED,
            "read_disliked": UserBookStatus.READ_DISLIKED,
            "interested": UserBookStatus.INTERESTED,
            "not_interested": UserBookStatus.NOT_INTERESTED,
        }

        for book_data in books_data:
            external_id = book_data.get("external_id")
            status_str = book_data.get("status")

            if not external_id or not status_str:
                continue

            # Find book by external_id
            book = db.query(Book).filter(Book.external_id == external_id).first()
            if not book:
                logger.warning(f"Book not found for external_id: {external_id}")
                continue

            status_enum = status_map.get(status_str)
            if not status_enum:
                logger.warning(f"Invalid status: {status_str}")
                continue

            # Create or update interaction
            existing = db.query(UserBookInteraction).filter(
                UserBookInteraction.user_id == user_id,
                UserBookInteraction.book_id == book.id
            ).first()

            if existing:
                existing.status = status_enum
                existing.updated_at = datetime.utcnow()
            else:
                interaction = UserBookInteraction(
                    user_id=user_id,
                    book_id=book.id,
                    status=status_enum
                )
                db.add(interaction)

        db.commit()
        return {"success": True, "message": "Book interactions saved"}
    except Exception as e:
        db.rollback()
        logger.exception(f"[DEBUG POST /api/onboarding/book-interactions ERROR] user_id={user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

