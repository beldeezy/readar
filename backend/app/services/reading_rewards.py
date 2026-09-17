"""Private reading rewards, derived from saved logs rather than incremented on save."""
from datetime import date, timedelta

from sqlalchemy import and_

from app.models import ReadingLog, ReadingProgress
from app.schemas.reading_rewards import ReadingRewardsResponse

POINTS_PER_DAY = 10


def summarize_rewards(qualified_dates: set[date], today: date, tz: str) -> ReadingRewardsResponse:
    # Travel may put a previously logged date ahead of the reader's local today.
    dates = sorted(day for day in qualified_dates if day <= today)
    qualified = set(dates)
    best = run = 0
    previous = None
    for day in dates:
        run = run + 1 if previous and (day - previous).days == 1 else 1
        best = max(best, run)
        previous = day
    today_qualified = today in qualified
    current = run if dates and (today - dates[-1]).days <= 1 else 0
    state = "active" if today_qualified else "continue" if current else "restart" if dates else "new"
    return ReadingRewardsResponse(
        today=today, timezone=tz, points_per_day=POINTS_PER_DAY,
        total_points=len(dates) * POINTS_PER_DAY, qualifying_days=len(dates),
        current_streak=current, best_streak=best, today_qualified=today_qualified,
        last_qualified_date=dates[-1] if dates else None, state=state,
        recent_days=[dict(reading_date=day, qualified=day in qualified)
                     for day in (today - timedelta(days=offset) for offset in range(6, -1, -1))],
    )


def get_reading_rewards(db, user_id, today: date, tz: str) -> ReadingRewardsResponse:
    # One SELECT yields a consistent settings/log snapshot under READ COMMITTED.
    # Include paused/completed/removed shelf books: their reading still counts.
    rows = db.query(
        ReadingLog.book_id, ReadingLog.reading_date, ReadingLog.position,
        ReadingLog.goal_target, ReadingProgress.starting_position,
    ).join(ReadingProgress, and_(
        ReadingProgress.user_id == ReadingLog.user_id,
        ReadingProgress.book_id == ReadingLog.book_id,
    )).filter(ReadingLog.user_id == user_id, ReadingLog.reading_date <= today).order_by(
        ReadingLog.book_id, ReadingLog.reading_date,
    ).all()
    qualified = set()
    previous_by_book = {}
    for row in rows:
        previous = previous_by_book.get(row.book_id, row.starting_position)
        if row.position - previous >= row.goal_target:
            qualified.add(row.reading_date)
        previous_by_book[row.book_id] = row.position
    return summarize_rewards(qualified, today, tz)
