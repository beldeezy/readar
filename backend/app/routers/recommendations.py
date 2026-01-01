from uuid import UUID
from typing import List, Optional, Dict, Any
import uuid as uuid_lib
import os

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
from app.models import User, UserBookFeedback, UserBookInteraction, UserBookStatusModel, ReadingHistoryEntry, Book, OnboardingProfile
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
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    RECS_DEBUG = os.getenv("READAR_RECS_DEBUG", "false").lower() == "true"
    
    # Collect signal counts (always, for logging and debug)
    interactions_count = db.query(UserBookInteraction).filter(UserBookInteraction.user_id == user_id).count()
    reading_history_count = db.query(ReadingHistoryEntry).filter(ReadingHistoryEntry.user_id == user_id).count()
    onboarding_profile = db.query(OnboardingProfile).filter(OnboardingProfile.user_id == user_id).first()
    has_onboarding_profile = onboarding_profile is not None
    candidates_count = db.query(Book).count()
    
    # DEBUG: Collect diagnostic counts (legacy DEBUG mode)
    debug_info: Optional[Dict[str, Any]] = None
    if DEBUG:
        feedback_count = db.query(UserBookFeedback).filter(UserBookFeedback.user_id == user_id).count()
        status_count = db.query(UserBookStatusModel).filter(UserBookStatusModel.user_id == user_id).count()
        
        logger.info(
            f"[DEBUG GET /api/recommendations] user_id={user_id} "
            f"feedback={feedback_count} interactions={interactions_count} "
            f"status_rows={status_count} reading_history={reading_history_count} "
            f"candidates={candidates_count}"
        )
        
        debug_info = {
            "feedback": feedback_count,
            "interactions": interactions_count,
            "status_rows": status_count,
            "reading_history": reading_history_count,
            "candidates": candidates_count,
            "returned": 0,  # Will be set after items are returned
            "reason": None,  # Will be set if empty
        }
    
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
        error_msg = str(e)
        logger.info(
            "User %s has no signal, falling back to generic recommendations: %s",
            user_id, error_msg
        )
        
        # Determine reason for empty results
        reason = "no_signal"
        if "No books in catalog" in error_msg:
            reason = "no_catalog"
        elif "No scored items" in error_msg:
            reason = "no_scored_items"
        elif "No recommendations after scoring" in error_msg:
            reason = "no_matches_after_filtering"
        
        # Log empty recommendations with signal counts
        logger.info(
            f"[RECS_EMPTY] user_id={user_id} ratings={interactions_count} "
            f"history={reading_history_count} has_profile={has_onboarding_profile} reason={reason}"
        )
        
        # DEBUG: Update reason for fallback
        if DEBUG and debug_info is not None:
            debug_info["reason"] = reason
        
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
    
    # DEBUG: Update debug info and determine reason if empty
    if DEBUG and debug_info is not None:
        debug_info["returned"] = len(items)
        if len(items) == 0:
            # Determine reason for empty results
            if debug_info["candidates"] == 0:
                debug_info["reason"] = "no_catalog"
            elif debug_info["interactions"] == 0 and debug_info["reading_history"] == 0 and debug_info["status_rows"] == 0:
                debug_info["reason"] = "no_signal"
            else:
                debug_info["reason"] = "no_matches"
            
            logger.info(
                f"[DEBUG GET /api/recommendations] user_id={user_id} "
                f"returned={len(items)} reason={debug_info['reason']}"
            )
        else:
            logger.info(
                f"[DEBUG GET /api/recommendations] user_id={user_id} "
                f"returned={len(items)}"
            )
    
    # Log empty recommendations with signal counts (always log, not gated)
    # Build structured debug info when recommendations are empty (gated by READAR_RECS_DEBUG)
    recs_debug_info: Optional[Dict[str, Any]] = None
    if len(items) == 0:
        from app.services.recommendation_engine import SIGNAL_THRESHOLD
        
        # Determine reason
        reason = "unknown"
        if candidates_count == 0:
            reason = "no_catalog"
        elif interactions_count == 0 and reading_history_count == 0 and not has_onboarding_profile:
            reason = "no_signal"
        elif interactions_count == 0 and reading_history_count == 0:
            reason = "cold_start_no_interactions"
        else:
            reason = "no_matches"
        
        logger.info(
            f"[RECS_EMPTY] user_id={user_id} ratings={interactions_count} "
            f"history={reading_history_count} has_profile={has_onboarding_profile} reason={reason}"
        )
        
        # Build structured debug info when RECS_DEBUG is enabled
        if RECS_DEBUG:
            recs_debug_info = {
                "user_id": str(user_id),
                "signal_counts": {
                    "onboarding_profile": has_onboarding_profile,
                    "book_ratings": interactions_count,  # Using interactions as "ratings"
                    "reading_history_entries": reading_history_count,
                },
                "gates": {
                    "min_ratings_required": 0,  # No hard minimum, but SIGNAL_THRESHOLD applies
                    "min_history_required": 0,  # No hard minimum, but SIGNAL_THRESHOLD applies
                    "signal_threshold": SIGNAL_THRESHOLD,
                },
                "reason": reason,
            }
    
    # Build response with optional debug object
    # Priority: recs_debug_info (when empty + RECS_DEBUG) > debug_info (when DEBUG) > None
    final_debug = recs_debug_info if recs_debug_info is not None else (debug_info if DEBUG else None)
    return RecommendationsResponse(
        request_id=request_id,
        items=items,
        debug=final_debug,
    )


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
    RECS_DEBUG = os.getenv("READAR_RECS_DEBUG", "false").lower() == "true"

    # Clamp max_results to 5
    effective_limit = min(request.max_results or 5, 5)
    
    # Collect signal counts for logging
    interactions_count = db.query(UserBookInteraction).filter(UserBookInteraction.user_id == user_id).count()
    reading_history_count = db.query(ReadingHistoryEntry).filter(ReadingHistoryEntry.user_id == user_id).count()
    onboarding_profile = db.query(OnboardingProfile).filter(OnboardingProfile.user_id == user_id).first()
    has_onboarding_profile = onboarding_profile is not None
    candidates_count = db.query(Book).count()
    
    try:
        items = recommendation_engine.get_personalized_recommendations(
            db=db,
            user_id=user_id,
            limit=effective_limit,
            debug=debug,
        )
    except NotEnoughSignalError as e:
        # User has zero signal - fall back to generic recommendations
        error_msg = str(e)
        logger.info(
            "User %s has no signal, falling back to generic recommendations: %s",
            user_id, error_msg
        )
        
        # Determine reason
        reason = "no_signal"
        if "No books in catalog" in error_msg:
            reason = "no_catalog"
        elif "No scored items" in error_msg:
            reason = "no_scored_items"
        elif "No recommendations after scoring" in error_msg:
            reason = "no_matches_after_filtering"
        
        # Log empty recommendations with signal counts
        logger.info(
            f"[RECS_EMPTY] user_id={user_id} ratings={interactions_count} "
            f"history={reading_history_count} has_profile={has_onboarding_profile} reason={reason}"
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
    
    # Log empty recommendations with signal counts (always log, not gated)
    # Build structured debug info when recommendations are empty (gated by READAR_RECS_DEBUG)
    recs_debug_info: Optional[Dict[str, Any]] = None
    if len(items) == 0:
        from app.services.recommendation_engine import SIGNAL_THRESHOLD
        
        # Determine reason
        reason = "unknown"
        if candidates_count == 0:
            reason = "no_catalog"
        elif interactions_count == 0 and reading_history_count == 0 and not has_onboarding_profile:
            reason = "no_signal"
        elif interactions_count == 0 and reading_history_count == 0:
            reason = "cold_start_no_interactions"
        else:
            reason = "no_matches"
        
        logger.info(
            f"[RECS_EMPTY] user_id={user_id} ratings={interactions_count} "
            f"history={reading_history_count} has_profile={has_onboarding_profile} reason={reason}"
        )
        
        # Build structured debug info when RECS_DEBUG is enabled
        if RECS_DEBUG:
            recs_debug_info = {
                "user_id": str(user_id),
                "signal_counts": {
                    "onboarding_profile": has_onboarding_profile,
                    "book_ratings": interactions_count,  # Using interactions as "ratings"
                    "reading_history_entries": reading_history_count,
                },
                "gates": {
                    "min_ratings_required": 0,  # No hard minimum, but SIGNAL_THRESHOLD applies
                    "min_history_required": 0,  # No hard minimum, but SIGNAL_THRESHOLD applies
                    "signal_threshold": SIGNAL_THRESHOLD,
                },
                "reason": reason,
            }
    
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
    
    return RecommendationsResponse(request_id=request_id, items=items, debug=recs_debug_info)


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

