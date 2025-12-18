# backend/app/routers/admin_debug.py

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import recommendation_engine
from app.core.supabase_auth import get_admin_user
from app.core.user_helpers import get_or_create_user_by_auth_id

# Admin-only router - all endpoints require admin authentication
router = APIRouter(tags=["admin_debug"])


@router.get("/insight-review")
async def insight_review(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Debug endpoint to review book recommendations with score factors breakdown.
    Shows which books are ranking for which challenges and identifies books with
    low/no insight match quality.
    
    Admin-only endpoint. Uses the current admin user's ID.
    Admin validation is handled by router-level dependency.
    """
    # Get admin user from request state (set by router dependency)
    # Since the router has get_admin_user as a dependency, we need to call it again
    # to get the user dict, or we can extract from request state if we modify the dependency
    # For now, call it again (it's cached/validated by the router dependency)
    admin_user = await get_admin_user(request)
    
    # Get or create local user from Supabase auth_user_id
    user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=admin_user["auth_user_id"],
        email=admin_user.get("email", ""),
    )
    user_id = user.id
    
    recs = recommendation_engine.get_personalized_recommendations(
        db=db,
        user_id=user_id,
        limit=100,  # Get more results for review
        debug=True,
    )
    
    summary = []
    for rec in recs:
        sf = rec.score_factors or {}
        summary.append({
            "title": rec.title,
            "challenge_fit": sf.get("challenge_fit", 0.0),
            "stage_fit": sf.get("stage_fit", 0.0),
            "promise_match": sf.get("promise_match", 0.0),
            "framework_match": sf.get("framework_match", 0.0),
            "outcome_match": sf.get("outcome_match", 0.0),
            "total_score": sf.get("total", 0.0),
        })
    
    return sorted(summary, key=lambda x: x["total_score"], reverse=True)

