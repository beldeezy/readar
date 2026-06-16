"""
Recommendations re-engagement email.

Selects opted-in, onboarded users (respecting a frequency cap), generates a few
fresh recommendations per user, and emails them a "your next reads" nudge.
Driven by the background scheduler (weekly) and an admin trigger endpoint.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import User, OnboardingProfile
from app.services.recommendation_engine import get_recommendations_for_user
from app.utils.email import send_recommendations_email
from app.utils.instrumentation import log_event_best_effort

logger = logging.getLogger(__name__)

# Don't email the same user more often than this.
MIN_DAYS_BETWEEN_EMAILS = 6
BOOKS_PER_EMAIL = 3


def send_recommendation_emails(
    db: Session,
    force: bool = False,
    max_users: Optional[int] = None,
    only_user_id=None,
) -> dict:
    """
    Send the recommendations re-engagement email to eligible users.

    :param force: ignore the frequency cap (use for admin testing).
    :param max_users: cap how many users to process this run.
    :param only_user_id: restrict to a single user (admin testing).
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MIN_DAYS_BETWEEN_EMAILS)

    q = (
        db.query(User)
        .join(OnboardingProfile, OnboardingProfile.user_id == User.id)
        .filter(
            User.email.isnot(None),
            User.notify_email_recommendations.is_(True),
        )
    )
    if only_user_id is not None:
        q = q.filter(User.id == only_user_id)
    if not force:
        q = q.filter(
            (User.last_recommendations_email_at.is_(None))
            | (User.last_recommendations_email_at < cutoff)
        )
    if max_users:
        q = q.limit(max_users)

    users = q.all()
    sent = skipped = errors = 0

    for user in users:
        try:
            recs = get_recommendations_for_user(user.id, db, limit=BOOKS_PER_EMAIL)
            if not recs:
                skipped += 1
                continue

            profile = (
                db.query(OnboardingProfile)
                .filter(OnboardingProfile.user_id == user.id)
                .one_or_none()
            )
            name = (profile.full_name.split()[0] if profile and profile.full_name else None)

            result = send_recommendations_email(user.email, name, recs[:BOOKS_PER_EMAIL])

            if result.get("status") == "success":
                sent += 1
            elif result.get("status") == "skipped":
                skipped += 1
            else:
                errors += 1
                continue  # don't stamp the cap on a failed send

            # Stamp the frequency cap and log (even on "skipped" no-op sends so a
            # misconfigured Resend doesn't loop the same users every run).
            user.last_recommendations_email_at = now
            db.commit()
            log_event_best_effort(
                event_name="recommendation_email_sent",
                user_id=user.id,
                properties={"book_count": len(recs[:BOOKS_PER_EMAIL]), "status": result.get("status")},
            )
        except Exception as e:
            db.rollback()
            errors += 1
            logger.warning("Re-engagement email failed for user_id=%s: %s", user.id, e)

    summary = {"eligible": len(users), "sent": sent, "skipped": skipped, "errors": errors}
    logger.info("Re-engagement email run: %s", summary)
    return summary
