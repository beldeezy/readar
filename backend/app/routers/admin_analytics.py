# backend/app/routers/admin_analytics.py
"""
Admin analytics: a single aggregated snapshot of the funnel, monetization,
engagement, and recent activity. Powers the admin Analytics page.

Mounted under /api so the standard frontend client (with its auth header) can
reach it at /api/admin/analytics. Admin-gated via require_admin_user.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database import get_db
from app.core.auth import require_admin_user
from app.models import (
    User,
    Book,
    OnboardingProfile,
    UserBookStatusModel,
    ReadingHistoryEntry,
    EventLog,
    SubscriptionStatus,
)
from app.services.reengagement import send_recommendation_emails

router = APIRouter(tags=["admin_analytics"], dependencies=[Depends(require_admin_user)])


def _rate(numerator: int, denominator: int):
    return round(numerator / denominator, 4) if denominator else None


@router.post("/admin/send-recommendation-emails")
def trigger_recommendation_emails(
    force: bool = Query(False, description="Ignore the per-user frequency cap."),
    max_users: Optional[int] = Query(None, description="Cap users processed this run."),
    only_email: Optional[str] = Query(None, description="Send to just this user's email (testing)."),
    db: Session = Depends(get_db),
):
    """Manually trigger the recommendations re-engagement email (admin/testing)."""
    only_user_id = None
    if only_email:
        user = db.query(User).filter(func.lower(User.email) == only_email.lower()).first()
        if not user:
            return {"status": "error", "message": f"No user with email {only_email}"}
        only_user_id = user.id
        force = True  # a targeted test send should bypass the cap
    return send_recommendation_emails(db, force=force, max_users=max_users, only_user_id=only_user_id)


@router.get("/admin/analytics")
def get_analytics(
    days: int = Query(30, ge=1, le=365, description="Lookback window for time series."),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    # ── Funnel (lifetime) ────────────────────────────────────────────────
    total_users = db.query(func.count(User.id)).scalar() or 0
    onboarded = db.query(func.count(distinct(OnboardingProfile.user_id))).scalar() or 0
    activated = db.query(func.count(distinct(UserBookStatusModel.user_id))).scalar() or 0
    paid = (
        db.query(func.count(User.id))
        .filter(User.subscription_status == SubscriptionStatus.ACTIVE)
        .scalar()
        or 0
    )

    funnel = [
        {"stage": "Signed up", "count": total_users, "pct_of_top": 1.0},
        {"stage": "Onboarded", "count": onboarded, "pct_of_top": _rate(onboarded, total_users)},
        {"stage": "Activated (saved a book)", "count": activated, "pct_of_top": _rate(activated, total_users)},
        {"stage": "Paid", "count": paid, "pct_of_top": _rate(paid, total_users)},
    ]

    # ── Monetization (from event log) ────────────────────────────────────
    def ev_count(name: str) -> int:
        return db.query(func.count(EventLog.id)).filter(EventLog.event_name == name).scalar() or 0

    def ev_users(name: str) -> int:
        return (
            db.query(func.count(distinct(EventLog.user_id)))
            .filter(EventLog.event_name == name, EventLog.user_id.isnot(None))
            .scalar()
            or 0
        )

    def ev_sessions(name: str) -> int:
        # Distinct anonymous sessions — the right unit for pre-auth funnel steps.
        return (
            db.query(func.count(distinct(EventLog.session_id)))
            .filter(EventLog.event_name == name, EventLog.session_id.isnot(None))
            .scalar()
            or 0
        )

    refresh_used = ev_count("refresh_used")
    limit_hits = ev_count("refresh_limit_hit")
    limit_hit_users = ev_users("refresh_limit_hit")
    upgrade_clicks = ev_count("upgrade_prompt_click")
    upgrade_click_users = ev_users("upgrade_prompt_click")

    monetization = {
        "refresh_used": refresh_used,
        "refresh_limit_hit": limit_hits,
        "refresh_limit_hit_users": limit_hit_users,
        "upgrade_prompt_click": upgrade_clicks,
        "upgrade_prompt_click_users": upgrade_click_users,
        # Of users who hit the wall, how many clicked upgrade
        "wall_to_click_rate": _rate(upgrade_click_users, limit_hit_users),
        "paid_users": paid,
        "free_users": total_users - paid,
    }

    # ── Engagement ───────────────────────────────────────────────────────
    status_rows = (
        db.query(UserBookStatusModel.status, func.count(UserBookStatusModel.id))
        .group_by(UserBookStatusModel.status)
        .all()
    )
    engagement = {
        "shelf_statuses": {row[0]: row[1] for row in status_rows},
        "books_read": db.query(func.count(ReadingHistoryEntry.id))
        .filter(ReadingHistoryEntry.shelf == "read")
        .scalar()
        or 0,
        "users_with_shelves": activated,
        "catalog_size": db.query(func.count(Book.id)).scalar() or 0,
    }

    # ── Recent activity (time series) ────────────────────────────────────
    signup_rows = (
        db.query(func.date(User.created_at), func.count(User.id))
        .filter(User.created_at >= since)
        .group_by(func.date(User.created_at))
        .all()
    )
    signups_by_day = {str(d): c for d, c in signup_rows}

    event_rows = (
        db.query(EventLog.event_name, func.count(EventLog.id))
        .group_by(EventLog.event_name)
        .all()
    )
    event_totals = {name: c for name, c in event_rows}

    # ── Onboarding funnel (sessions, stitched by anon session_id) ─────────
    started = ev_sessions("onboarding_started")
    onboarding_funnel = [
        {"stage": "Started chat", "count": started, "pct_of_top": 1.0 if started else None},
        {"stage": "Finished chat", "count": ev_sessions("onboarding_chat_completed"), "pct_of_top": _rate(ev_sessions("onboarding_chat_completed"), started)},
        {"stage": "Clicked finish", "count": ev_sessions("onboarding_finish_clicked"), "pct_of_top": _rate(ev_sessions("onboarding_finish_clicked"), started)},
        {"stage": "Prompted to sign in", "count": ev_sessions("onboarding_signin_prompted"), "pct_of_top": _rate(ev_sessions("onboarding_signin_prompted"), started)},
        {"stage": "Completed (saved)", "count": ev_users("onboarding_completed"), "pct_of_top": _rate(ev_users("onboarding_completed"), started)},
        {"stage": "Imported history", "count": ev_sessions("onboarding_import_completed"), "pct_of_top": _rate(ev_sessions("onboarding_import_completed"), started)},
    ]

    return {
        "generated_at": now.isoformat(),
        "window_days": days,
        "funnel": funnel,
        "onboarding_funnel": onboarding_funnel,
        "monetization": monetization,
        "engagement": engagement,
        "signups_by_day": signups_by_day,
        "event_totals": event_totals,
    }
