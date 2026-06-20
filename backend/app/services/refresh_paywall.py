"""
Server-side daily recommendation-refresh ("spin") metering.

Free users get FREE_DAILY_REFRESHES explicit refreshes per UTC day; premium
(subscription_status == active) is unlimited. This replaces the bypassable
client-side localStorage counter with an authoritative per-user counter.
"""
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models import User, SubscriptionStatus

FREE_DAILY_REFRESHES = 3


class RefreshLimitReached(Exception):
    """Raised when a free user exceeds the daily refresh allowance."""

    def __init__(self, limit: int, used: int):
        self.limit = limit
        self.used = used
        super().__init__(f"daily refresh limit reached ({used}/{limit})")


def _today() -> date:
    return datetime.now(timezone.utc).date()


def is_premium(user: User) -> bool:
    return user.subscription_status == SubscriptionStatus.ACTIVE


def refresh_status(user: User) -> dict:
    """
    Non-mutating view of the user's refresh allowance. Treats a stale
    daily_refresh_date (not today) as a fresh day with 0 used.
    """
    if is_premium(user):
        return {"is_premium": True, "limit": None, "used": 0, "remaining": None}
    used = (user.daily_refresh_count or 0) if user.daily_refresh_date == _today() else 0
    return {
        "is_premium": False,
        "limit": FREE_DAILY_REFRESHES,
        "used": used,
        "remaining": max(0, FREE_DAILY_REFRESHES - used),
    }


def consume_refresh(db: Session, user: User) -> dict:
    """
    Record one explicit refresh ("spin") for a free user, resetting the counter
    on a new day. Premium users are a no-op. Commits on success.

    Raises RefreshLimitReached when the free allowance is already exhausted.
    Returns the post-consume status dict.
    """
    if is_premium(user):
        return refresh_status(user)

    today = _today()
    if user.daily_refresh_date != today:
        user.daily_refresh_date = today
        user.daily_refresh_count = 0

    used = user.daily_refresh_count or 0
    if used >= FREE_DAILY_REFRESHES:
        raise RefreshLimitReached(FREE_DAILY_REFRESHES, used)

    user.daily_refresh_count = used + 1
    db.commit()
    return refresh_status(user)
