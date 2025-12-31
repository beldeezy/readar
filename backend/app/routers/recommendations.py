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
from app.utils.instrumentation import log_event, log_event_best_effort
from app.utils.timing import now_ms, log_elapsed
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["recommendations"])

@router.get("/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(
    limit: int = Query(5, ge=1, le=5),
    debug: bool = Query(False, description="Include debug fields in response"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Timing: start of request
    t0 = now_ms()
    
    # Hard clamp to avoid any weirdness if this endpoint is reused elsewhere
    if limit > 5:
        limit = 5
    
    user_id = user.id
    request_id = str(uuid_lib.uuid4())
    
    # Timing: after auth/user lookup
    if settings.DEBUG:
        t1 = log_elapsed(t0, f"req_id={request_id} user={user_id} auth_lookup", logger.debug)
    else:
        t1 = now_ms()
    
    logger.info("Fetching recommendations for user %s (auth_user_id=%s)", user_id, user.auth_user_id)

    try:
        # Timing: before recommendation engine call
        if settings.DEBUG:
            t2 = log_elapsed(t1, f"req_id={request_id} user={user_id} before_recommendations", logger.debug)
        else:
            t2 = now_ms()
        
        items = recommendation_engine.get_personalized_recommendations(
            db=db,
            user_id=user_id,
            limit=limit,
            debug=debug,
        )
        
        # Timing: after recommendation engine call
        if settings.DEBUG:
            t3 = log_elapsed(t2, f"req_id={request_id} user={user_id} recommendations_engine", logger.debug)
        else:
            t3 = now_ms()
    except NotEnoughSignalError as e:
        # User has zero signal - fall back to generic recommendations
        logger.info(
            "User %s has no signal, falling back to generic recommendations: %s",
            user_id, str(e)
        )
        if settings.DEBUG:
            t_fallback = log_elapsed(t2, f"req_id={request_id} user={user_id} before_fallback", logger.debug)
        items = recommendation_engine.get_generic_recommendations(
            db=db,
            limit=limit,
        )
        if settings.DEBUG:
            t3 = log_elapsed(t_fallback, f"req_id={request_id} user={user_id} fallback_recommendations", logger.debug)
        else:
            t3 = now_ms()
    except Exception as e:
        # Log full traceback to server console with detailed context
        error_type = type(e).__name__
        error_message = str(e) if str(e) else "An unexpected error occurred"
        logger.exception(
            "[DEBUG GET /api/recommendations ERROR] "
            f"user_id={user_id}, "
            f"auth_user_id={user.auth_user_id}, "
            f"error_type={error_type}, "
            f"error={error_message}"
        )
        # Surface detail to the client
        raise HTTPException(
            status_code=500,
            detail={
                "detail": "internal_error",
                "error_type": error_type,
                "error": error_message,
            },
        )
    
    # Timing: before event logging
    if settings.DEBUG:
        t4 = log_elapsed(t3, f"req_id={request_id} user={user_id} before_event_log", logger.debug)
    else:
        t4 = now_ms()
    
    # Log impression event
    book_ids = [item.book_id for item in items]
    top_book_id = book_ids[0] if book_ids else None
    log_event(
        db=db,
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
    db.commit()
    
    # Timing: before response serialization
    if settings.DEBUG:
        t5 = log_elapsed(t4, f"req_id={request_id} user={user_id} event_log_commit", logger.debug)
        t6 = log_elapsed(t5, f"req_id={request_id} user={user_id} response_serialize", logger.debug)
        total = now_ms() - t0
        logger.debug(f"req_id={request_id} user={user_id} total={total:.2f}ms limit={limit} count={len(items)}")
    
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
    
    # Log impression event
    book_ids = [item.book_id for item in items]
    top_book_id = book_ids[0] if book_ids else None
    log_event(
        db=db,
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
    db.commit()
    
    # Log recommendation_viewed event (best-effort, non-blocking)
    try:
        log_event_best_effort(
            event_name="recommendation_viewed",
            user_id=user_id,
            properties={
                "request_id": request_id,
                "count": len(items),
            },
            request_id=request_id,
        )
    except Exception:
        # Silently ignore instrumentation failures
        pass
    
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

