from uuid import UUID
from typing import List
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app import models
from app.services import recommendation_engine
from app.services.recommendation_engine import NotEnoughSignalError
from app.schemas.recommendation import RecommendationItem, RecommendationRequest, RecommendationsResponse
from app.schemas.onboarding import OnboardingPayload
from app.core.auth import get_current_user
from app.models import User
from app.utils.instrumentation import log_event_best_effort

logger = logging.getLogger(__name__)

router = APIRouter(tags=["recommendations"])

@router.get("/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(
    limit: int = Query(5, ge=1, le=5),
    debug: bool = Query(False, description="Include debug fields in response"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Hard clamp to avoid any weirdness if this endpoint is reused elsewhere
    if limit > 5:
        limit = 5
    
    user_id = user.id
    request_id = str(uuid_lib.uuid4())
    
    logger.info("Fetching recommendations for user %s (auth_user_id=%s)", user_id, user.auth_user_id)

    try:
        items = recommendation_engine.get_personalized_recommendations(
            db=db,
            user_id=user_id,
            limit=limit,
            debug=debug,
        )
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
    except Exception as e:
        # Log full traceback to server console
        logger.exception("Error while generating recommendations for user %s", user_id)
        # Surface detail to the client
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recommendations: {e}",
        )
    
    # Log impression event (best-effort, non-blocking)
    book_ids = [item.book_id for item in items]
    top_book_id = book_ids[0] if book_ids else None
    log_event_best_effort(
        event_name="recommendations_impression",
        user_id=user_id,
        properties={
            "request_id": request_id,
            "count": len(items),
            "top_book_id": top_book_id,
            "book_ids": book_ids,
        },
        request_id=request_id,
    )
    
    return RecommendationsResponse(request_id=request_id, items=items)


@router.post("/recommendations", response_model=RecommendationsResponse)
async def get_recommendations_post(
    request: RecommendationRequest = RecommendationRequest(),
    debug: bool = Query(False, description="Include debug fields in response"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate book recommendations for the authenticated user (POST endpoint for backward compatibility).
    """
    user_id = user.id
    request_id = str(uuid_lib.uuid4())

    # Clamp max_results to 5
    effective_limit = min(request.max_results or 5, 5)
    
    try:
        items = recommendation_engine.get_personalized_recommendations(
            db=db,
            user_id=user_id,
            limit=effective_limit,
            debug=debug,
        )
    except NotEnoughSignalError as e:
        # User has zero signal - fall back to generic recommendations
        logger.info(
            "User %s has no signal, falling back to generic recommendations: %s",
            user_id, str(e)
        )
        try:
            items = recommendation_engine.get_generic_recommendations(
                db=db,
                limit=effective_limit,
            )
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
            items = recommendation_engine.get_generic_recommendations(
                db=db,
                limit=effective_limit,
            )
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
    
    # Log impression event (best-effort, non-blocking)
    book_ids = [item.book_id for item in items]
    top_book_id = book_ids[0] if book_ids else None
    log_event_best_effort(
        event_name="recommendations_impression",
        user_id=user_id,
        properties={
            "request_id": request_id,
            "count": len(items),
            "top_book_id": top_book_id,
            "book_ids": book_ids,
        },
        request_id=request_id,
    )
    
    return RecommendationsResponse(request_id=request_id, items=items)


@router.post("/recommendations/preview", response_model=List[RecommendationItem])
async def get_preview_recommendations(
    payload: OnboardingPayload,
    limit: int = Query(5, ge=1, le=5),
    debug: bool = Query(False, description="Include debug fields in response"),
    db: Session = Depends(get_db),
):
    """
    Generate preview recommendations from onboarding payload without requiring authentication.
    This endpoint is used to show recommendations before the user logs in.
    
    Note: This does NOT create or mutate user rows. It only generates recommendations
    based on the provided onboarding data.
    """
    # Hard clamp to avoid any weirdness
    if limit > 5:
        limit = 5
    
    logger.info("Generating preview recommendations (no auth required)")
    
    try:
        items = recommendation_engine.get_recommendations_from_payload(
            db=db,
            payload=payload,
            limit=limit,
            debug=debug,
        )
        return items
    except NotEnoughSignalError as e:
        # Fall back to generic recommendations
        logger.info(
            "Preview recommendations failed, falling back to generic: %s",
            str(e)
        )
        items = recommendation_engine.get_generic_recommendations(
            db=db,
            limit=limit,
            business_stage=payload.business_stage.value if hasattr(payload.business_stage, 'value') else str(payload.business_stage),
            business_model=payload.business_model,
        )
        return items
    except Exception as e:
        # Log full traceback to server console
        logger.exception("Error while generating preview recommendations")
        # Surface detail to the client
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get preview recommendations: {e}",
        )

