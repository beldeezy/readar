# backend/app/routers/admin_debug.py

from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import recommendation_engine

router = APIRouter(tags=["admin_debug"])


@router.get("/insight-review")
def insight_review(
    user_id: UUID = Query(..., description="User ID to generate recommendations for"),
    db: Session = Depends(get_db),
):
    """
    Debug endpoint to review book recommendations with score factors breakdown.
    Shows which books are ranking for which challenges and identifies books with
    low/no insight match quality.
    """
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

