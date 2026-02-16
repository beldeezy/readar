# backend/app/routers/admin_debug.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from uuid import UUID
from app.database import get_db
from app.services import recommendation_engine
from app.core.auth import require_admin_user
from app.models import User, Book, BookSource, RecommendationEvent
from app.core.config import settings

# Admin-only router - all endpoints require admin authentication
router = APIRouter(tags=["admin_debug"], dependencies=[Depends(require_admin_user)])


@router.get("/insight-review")
def insight_review(
    current_user: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    """
    Debug endpoint to review book recommendations with score factors breakdown.
    Shows which books are ranking for which challenges and identifies books with
    low/no insight match quality.

    Admin-only endpoint. Uses the current admin user's ID.
    Admin validation is handled by router-level dependency.
    """
    user_id = current_user.id
    
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


@router.get("/catalog-stats")
def catalog_stats(
    current_user: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    """
    Diagnostic endpoint: check catalog state in the database.

    Returns:
        - books_count: total books
        - sources_count: total sources
        - recent_books: last 10 books created
        - database_url: masked DB URL (for verification)
    """
    # Count books
    books_count = db.query(func.count(Book.id)).scalar()

    # Count sources
    sources_count = db.query(func.count(BookSource.id)).scalar()

    # Recent books
    recent_books = db.query(Book).order_by(Book.created_at.desc()).limit(10).all()
    recent_list = [
        {
            "id": str(book.id),
            "title": book.title,
            "author_name": book.author_name,
            "published_year": book.published_year,
            "created_at": book.created_at.isoformat() if book.created_at else None,
        }
        for book in recent_books
    ]

    # Sample sources
    recent_sources = db.query(BookSource).order_by(BookSource.created_at.desc()).limit(5).all()
    sources_list = [
        {
            "id": str(source.id),
            "book_id": str(source.book_id),
            "source_name": source.source_name,
            "source_year": source.source_year,
            "source_rank": source.source_rank,
            "source_category": source.source_category,
        }
        for source in recent_sources
    ]

    return {
        "books_count": books_count,
        "sources_count": sources_count,
        "recent_books": recent_list,
        "recent_sources": sources_list,
        "database_url": settings.get_masked_database_url(),
    }


@router.get("/recommendation-events")
def get_recommendation_events(
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[str] = Query(None),
    book_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    current_user: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    """
    Admin-only endpoint to retrieve recommendation events for debugging and analytics.

    Query params:
    - limit: Maximum number of events to return (default 100, max 1000)
    - user_id: Filter by user UUID (optional)
    - book_id: Filter by book UUID (optional)
    - event_type: Filter by event type (recommendation_shown, save_interested, etc.) (optional)

    Returns list of events with book title and user email joined.
    """
    # Build query
    query = db.query(RecommendationEvent).join(Book).join(User)

    # Apply filters
    if user_id:
        try:
            user_uuid = UUID(user_id)
            query = query.filter(RecommendationEvent.user_id == user_uuid)
        except ValueError:
            # Invalid UUID format - skip filter
            pass

    if book_id:
        try:
            book_uuid = UUID(book_id)
            query = query.filter(RecommendationEvent.book_id == book_uuid)
        except ValueError:
            # Invalid UUID format - skip filter
            pass

    if event_type:
        query = query.filter(RecommendationEvent.event_type == event_type)

    # Order by created_at descending (most recent first)
    query = query.order_by(RecommendationEvent.created_at.desc())

    # Apply limit
    events = query.limit(limit).all()

    # Format response with joined data
    results = []
    for event in events:
        # Get book and user from relationships
        book = db.query(Book).filter(Book.id == event.book_id).first()
        user = db.query(User).filter(User.id == event.user_id).first()

        results.append({
            "id": str(event.id),
            "user_id": str(event.user_id),
            "user_email": user.email if user else None,
            "book_id": str(event.book_id),
            "book_title": book.title if book else None,
            "event_type": event.event_type,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "recommendation_session_id": event.recommendation_session_id,
            "metadata": event.event_metadata,
        })

    return {
        "count": len(results),
        "events": results,
    }

