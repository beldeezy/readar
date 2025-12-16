from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app import models
from app.services import recommendation_engine
from app.services.recommendation_engine import NotEnoughSignalError
from app.schemas.recommendation import RecommendationItem, RecommendationRequest
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)

router = APIRouter(tags=["recommendations"])

@router.get("/recommendations", response_model=List[RecommendationItem])
def get_recommendations(
    user_id: UUID = Query(...),
    limit: int = Query(5, ge=1, le=5),
    debug: bool = Query(False, description="Include debug fields in response"),
    db: Session = Depends(get_db),
):
    # Hard clamp to avoid any weirdness if this endpoint is reused elsewhere
    if limit > 5:
        limit = 5
    
    logger.info("Fetching recommendations for user %s", user_id)

    # Ensure user exists (dev placeholder if missing)
    user = db.query(models.User).filter(models.User.id == user_id).one_or_none()
    if user is None:
        logger.warning(
            "User %s not found; creating placeholder user for recommendations.",
            user_id,
        )
        placeholder_email = f"dev+{user_id}@readar.local"
        placeholder_password_hash = get_password_hash("placeholder_password")
        user = models.User(
            id=user_id,
            email=placeholder_email,
            password_hash=placeholder_password_hash,
        )
        db.add(user)
        db.flush()

    try:
        items = recommendation_engine.get_personalized_recommendations(
            db=db,
            user_id=user_id,
            limit=limit,
            debug=debug,
        )
        return items
    except NotEnoughSignalError as e:
        # User has zero signal - fall back to generic recommendations
        logger.info(
            "User %s has no signal, falling back to generic recommendations: %s",
            user_id, str(e)
        )
        items = recommendation_engine.get_generic_recommendations(
            db=db,
            limit=limit,
        )
        return items
    except Exception as e:
        # Log full traceback to server console
        logger.exception("Error while generating recommendations for user %s", user_id)
        # Surface detail to the client
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recommendations: {e}",
        )


@router.post("/recommendations", response_model=List[RecommendationItem])
def get_recommendations_post(
    request: RecommendationRequest = RecommendationRequest(),
    user_id: UUID = Query(..., description="User ID to generate recommendations for"),
    debug: bool = Query(False, description="Include debug fields in response"),
    db: Session = Depends(get_db)
):
    """
    Generate book recommendations for a user (POST endpoint for backward compatibility).
    
    Dev-friendly behavior:
    - If the user does not exist yet, create a minimal placeholder User so the
      recommendation engine and FKs don't explode.
    """
    # 1) Ensure a User row exists for this id
    user = db.query(models.User).filter(models.User.id == user_id).one_or_none()
    if user is None:
        logger.warning(
            "User %s not found; creating placeholder user for recommendations.",
            user_id,
        )

        # Create placeholder user with required fields
        placeholder_email = f"dev+{user_id}@readar.local"
        placeholder_password_hash = get_password_hash("placeholder_password")

        user = models.User(
            id=user_id,
            email=placeholder_email,
            password_hash=placeholder_password_hash,
        )
        db.add(user)
        db.flush()  # ensure the row exists

    # 2) Call the recommendation engine with graceful fallback
    # Clamp max_results to 5
    effective_limit = min(request.max_results or 5, 5)
    
    try:
        items = recommendation_engine.get_personalized_recommendations(
            db=db,
            user_id=user_id,
            limit=effective_limit,
            debug=debug,
        )
        return items
    except NotEnoughSignalError as e:
        # User has zero signal - fall back to generic recommendations
        logger.info(
            "User %s has no signal, falling back to generic recommendations: %s",
            user_id, str(e)
        )
        try:
            fallback_items = recommendation_engine.get_generic_recommendations(
                db=db,
                limit=effective_limit,
            )
            return fallback_items
        except Exception as inner_e:
            logger.exception(
                "Failed to get generic recommendations for user %s: %s",
                user_id,
                inner_e,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get recommendations: {inner_e}",
            )
    except ValueError as e:
        logger.warning(
            "ValueError from recommendation engine for user %s: %s. "
            "Falling back to generic recommendations.",
            user_id,
            e,
        )
        try:
            fallback_items = recommendation_engine.get_generic_recommendations(
                db=db,
                limit=effective_limit,
            )
            return fallback_items
        except Exception as inner_e:
            logger.exception(
                "Failed to get generic recommendations for user %s: %s",
                user_id,
                inner_e,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get recommendations: {inner_e}",
            )
    except Exception as e:
        logger.exception("Failed to get recommendations for user %s", user_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recommendations: {e}",
        )

