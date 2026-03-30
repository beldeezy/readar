"""
Reading DNA profile generation service.

Analyzes a user's Goodreads reading history to produce:
  - structured_tags: weighted insight tag dict {tag_key: weight}
  - profile_summary: 2-3 sentence LLM description of reading patterns
  - reading_confidence: 0.0-1.0 multiplier scaling how seriously we weight
    reading-history preference signals in the recommendation engine

The reading_confidence multiplier addresses the "premature high-rating" problem:
newer readers often rate early books highly simply from the experience of finishing
a book, not from a broad comparative context. The more books a user has read, the
more we trust their ratings as a genuine signal.
"""
import json
import os
import re
import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime

import anthropic
from sqlalchemy.orm import Session

from app.models import ReadingHistoryEntry, UserReadingProfile

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Tag prefix allowlist — must match recommendation engine vocabulary
VALID_TAG_PREFIXES = {"business_stage", "functional", "theme"}

PROFILE_SYSTEM_PROMPT = """You are a reading analyst for a business book recommendation engine.

You will receive a user's Goodreads reading history (books they have read, with ratings 1-5).

Your task:
1. Generate 5-10 weighted insight tags characterizing this reader's interests and business focus.
2. Write a 2-3 sentence "Reading DNA" profile summarizing their patterns.

TAG FORMAT: "category:value"

Allowed categories and values:

business_stage: idea | pre-revenue | early-revenue | scaling

functional: pricing | marketing | sales | operations | product | leadership |
  client_acquisition | service_delivery | plg | growth | metrics | analytics |
  hiring | finance | strategy | fundraising | culture | productivity |
  negotiation | communication

theme: (free-form, lowercase with underscores)
  Examples: theme:systems_thinking, theme:pricing_strategy, theme:customer_discovery,
  theme:mindset, theme:team_building, theme:decision_making

WEIGHTS: 0.0-1.0 reflecting how strongly this tag characterizes the reader.
Weight higher tags that appear across multiple highly-rated books.

Return ONLY valid JSON — no markdown, no explanation:
{
  "structured_tags": {
    "functional:sales": 0.8,
    "business_stage:early-revenue": 0.7,
    "theme:pricing_strategy": 0.5
  },
  "profile_summary": "This reader gravitates toward early-stage growth and sales execution..."
}"""


def get_reading_confidence(total_books_read: int) -> float:
    """
    Scale preference signal weight based on library size.

    Small libraries receive low confidence to prevent premature ratings from
    over-steering recommendations. Thresholds:

        < 5 books  → 0.15  (minimal — not enough context)
        5–14       → 0.35  (low — early reader)
        15–29      → 0.55  (moderate)
        30–49      → 0.75  (good)
        50+        → 1.0   (full trust — seasoned reader)
    """
    if total_books_read < 5:
        return 0.15
    elif total_books_read < 15:
        return 0.35
    elif total_books_read < 30:
        return 0.55
    elif total_books_read < 50:
        return 0.75
    return 1.0


def _build_book_list_text(entries: List[ReadingHistoryEntry]) -> str:
    lines = []
    for e in entries:
        rating = f"{int(e.my_rating)}/5" if e.my_rating and e.my_rating > 0 else "unrated"
        date = f" ({e.date_read})" if e.date_read else ""
        lines.append(f"- {e.title} by {e.author or 'Unknown'} — {rating}{date}")
    return "\n".join(lines) if lines else "No books recorded."


def _call_claude_for_profile(entries: List[ReadingHistoryEntry]) -> tuple[Optional[dict], Optional[str]]:
    """
    Call Claude Haiku to generate structured_tags and profile_summary.
    Returns (structured_tags dict, profile_summary str) or (None, None) on failure.
    """
    if not ANTHROPIC_API_KEY:
        return None, None

    book_list_text = _build_book_list_text(entries)
    user_prompt = (
        f"Analyze this reader's Goodreads history and return their Reading DNA profile.\n\n"
        f"Books read ({len(entries)} total):\n{book_list_text}\n\n"
        f"Return ONLY the JSON object."
    )

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            timeout=30.0,
            system=PROFILE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = message.content[0].text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        data = json.loads(text)
    except Exception as e:
        logger.warning("Claude profile generation failed: %s", e)
        return None, None

    # Validate and sanitize structured_tags
    raw_tags = data.get("structured_tags", {})
    structured_tags: dict = {}
    for key, weight in raw_tags.items():
        if not isinstance(key, str) or not isinstance(weight, (int, float)):
            continue
        key = key.strip().lower()
        parts = key.split(":", 1)
        if len(parts) == 2 and parts[0] in VALID_TAG_PREFIXES:
            structured_tags[key] = round(min(1.0, max(0.0, float(weight))), 3)

    profile_summary = str(data.get("profile_summary", ""))[:500] or None
    return structured_tags or None, profile_summary


def generate_reading_profile(db: Session, user_id: UUID) -> Optional[UserReadingProfile]:
    """
    Generate or update the UserReadingProfile for a user from their reading history.

    Called as a background task after a Goodreads CSV import.
    Returns the updated profile record, or None on failure.
    """
    read_entries = (
        db.query(ReadingHistoryEntry)
        .filter(
            ReadingHistoryEntry.user_id == user_id,
            ReadingHistoryEntry.shelf == "read",
        )
        .all()
    )

    total_books_read = len(read_entries)
    reading_confidence = get_reading_confidence(total_books_read)

    rated = [e for e in read_entries if e.my_rating and e.my_rating > 0]
    avg_rating = round(sum(e.my_rating for e in rated) / len(rated), 2) if rated else None

    structured_tags, profile_summary = None, None
    if total_books_read > 0:
        structured_tags, profile_summary = _call_claude_for_profile(read_entries)

    # Upsert
    profile = db.query(UserReadingProfile).filter(UserReadingProfile.user_id == user_id).first()
    if profile is None:
        profile = UserReadingProfile(user_id=user_id)
        db.add(profile)

    profile.total_books_read = total_books_read
    profile.avg_rating = avg_rating
    profile.reading_confidence = reading_confidence
    if structured_tags is not None:
        profile.structured_tags = structured_tags
    if profile_summary is not None:
        profile.profile_summary = profile_summary
    profile.generated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(profile)
        logger.info(
            "Reading profile updated for user_id=%s: %d books, confidence=%.2f",
            user_id, total_books_read, reading_confidence,
        )
        return profile
    except Exception as e:
        logger.warning("Failed to save reading profile for user_id=%s: %s", user_id, e)
        db.rollback()
        return None
