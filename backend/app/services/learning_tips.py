"""
Learning-tips email.

For each opted-in, onboarded user who is currently reading a book, generate a
short, actionable tip (via Claude) that ties that book's promise/frameworks to
the user's biggest challenge, and email it. Frequency-capped to roughly biweekly.
Driven by the background scheduler and an admin trigger endpoint.

Mirrors app/services/reengagement.py.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import cast, String
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import User, OnboardingProfile, UserBookStatusModel, Book
from app.utils.email import send_learning_tip_email
from app.utils.instrumentation import log_event_best_effort

logger = logging.getLogger(__name__)

# Biweekly cadence: the job may run weekly, but this per-user cap enforces ~14 days.
MIN_DAYS_BETWEEN_TIPS = 13
CURRENTLY_READING_STATUS = "currently_reading"


def _generate_learning_tip(book: Book, challenge: str) -> Optional[dict]:
    """
    Ask Claude for a {focus, insight, action} tip tying this book to the user's
    biggest challenge. Falls back to the book's title/author/description when the
    curated insight fields (promise/frameworks) are missing. Returns None on error.
    """
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        logger.info("[learning-tips] ANTHROPIC_API_KEY not set — skipping tip generation")
        return None

    promise = (book.promise or "").strip()
    frameworks = ", ".join(book.core_frameworks) if book.core_frameworks else ""
    description = (book.description or "").strip()

    # Prefer curated insights; fall back to raw metadata for un-enriched books.
    if promise or frameworks:
        book_context = f"Promise: {promise}\nKey frameworks: {frameworks or 'n/a'}"
    else:
        book_context = f"Description: {description[:600] or 'n/a'}"

    prompt = f"""You are a sharp reading coach for entrepreneurs. A founder is currently reading this book:

Title: {book.title}
Author: {book.author_name or 'Unknown'}
{book_context}

The founder's biggest challenge right now is:
"{challenge}"

Write ONE short, concrete learning tip that helps them apply an idea from THIS book to THAT challenge.
- focus: 2-4 words naming the idea/lever (e.g. "Pricing for value").
- insight: 1-2 sentences connecting a specific idea or framework from the book to their challenge. Second person ("you", "your business"). Specific, not generic praise.
- action: one concrete thing they can do this week. Imperative, single sentence.
Avoid hype words. Don't restate the book's summary."""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            tools=[{
                "name": "learning_tip",
                "description": "Store the learning tip fields.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "focus": {"type": "string", "description": "2-4 words naming the idea/lever."},
                        "insight": {"type": "string", "description": "1-2 sentences tying a book idea to the challenge."},
                        "action": {"type": "string", "description": "One concrete action for this week, imperative."},
                    },
                    "required": ["focus", "insight", "action"],
                },
            }],
            tool_choice={"type": "tool", "name": "learning_tip"},
            messages=[{"role": "user", "content": prompt}],
        )
        block = next(
            (b for b in message.content if b.type == "tool_use" and b.name == "learning_tip"),
            None,
        )
        if not block:
            logger.warning("[learning-tips] no tool_use block for book=%s", book.id)
            return None
        return {
            "focus": (block.input.get("focus") or "").strip(),
            "insight": (block.input.get("insight") or "").strip(),
            "action": (block.input.get("action") or "").strip(),
        }
    except Exception as e:
        logger.warning("[learning-tips] tip generation failed for book=%s: %s", book.id, e)
        return None


def _current_book_for_user(db: Session, user_id) -> Optional[Book]:
    """Most recently updated 'currently_reading' book for a user, resolved to a catalog Book."""
    status_row = (
        db.query(UserBookStatusModel)
        .filter(
            UserBookStatusModel.user_id == user_id,
            UserBookStatusModel.status == CURRENTLY_READING_STATUS,
        )
        .order_by(UserBookStatusModel.updated_at.desc())
        .first()
    )
    if not status_row:
        return None
    # book_id is stored as String; Book.id is UUID — compare on the string form.
    return (
        db.query(Book)
        .filter(cast(Book.id, String) == str(status_row.book_id))
        .first()
    )


def send_learning_tip_emails(
    db: Session,
    force: bool = False,
    max_users: Optional[int] = None,
    only_user_id=None,
) -> dict:
    """
    Send the learning-tips email to eligible users.

    :param force: ignore the frequency cap (admin testing).
    :param max_users: cap how many users to process this run.
    :param only_user_id: restrict to a single user (admin testing).
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MIN_DAYS_BETWEEN_TIPS)

    q = (
        db.query(User)
        .join(OnboardingProfile, OnboardingProfile.user_id == User.id)
        .filter(
            User.email.isnot(None),
            User.notify_email_learning_tips.is_(True),
        )
    )
    if only_user_id is not None:
        q = q.filter(User.id == only_user_id)
    if not force:
        q = q.filter(
            (User.last_learning_tip_email_at.is_(None))
            | (User.last_learning_tip_email_at < cutoff)
        )
    if max_users:
        q = q.limit(max_users)

    users = q.all()
    sent = skipped = errors = 0

    for user in users:
        try:
            book = _current_book_for_user(db, user.id)
            if not book:
                skipped += 1
                continue

            profile = (
                db.query(OnboardingProfile)
                .filter(OnboardingProfile.user_id == user.id)
                .one_or_none()
            )
            challenge = (profile.biggest_challenge if profile else "") or ""
            if not challenge.strip():
                skipped += 1
                continue

            tip = _generate_learning_tip(book, challenge)
            if not tip or not (tip.get("insight") or tip.get("action")):
                skipped += 1
                continue

            name = (profile.full_name.split()[0] if profile and profile.full_name else None)
            result = send_learning_tip_email(
                user.email, name, book.title, book.author_name, tip
            )

            if result.get("status") == "success":
                sent += 1
            elif result.get("status") == "skipped":
                skipped += 1
            else:
                errors += 1
                continue  # don't stamp the cap on a failed send

            # Stamp the cap even on no-op "skipped" sends so a misconfigured Resend
            # doesn't reprocess the same users every run.
            user.last_learning_tip_email_at = now
            db.commit()
            log_event_best_effort(
                event_name="learning_tip_email_sent",
                user_id=user.id,
                properties={"book_id": str(book.id), "status": result.get("status")},
            )
        except Exception as e:
            db.rollback()
            errors += 1
            logger.warning("Learning-tip email failed for user_id=%s: %s", user.id, e)

    summary = {"eligible": len(users), "sent": sent, "skipped": skipped, "errors": errors}
    logger.info("Learning-tip email run: %s", summary)
    return summary
