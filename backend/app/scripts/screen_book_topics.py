# backend/app/scripts/screen_book_topics.py
"""
Screen catalog books for topic fit (RD-23).

WHY
---
User Goodreads imports land in the SHARED `books` table and become recommendable
to everyone. generate_tags.py will happily assign confident, plausible tags to a
book that has nothing to do with entrepreneurship — observed in the live catalog:

    "Calculus for the Practical Man"        -> operations, finance, metrics
    "Microserfs" (a novel)                  -> culture, leadership, productivity
    a Portland Trail Blazers season diary   -> leadership, culture, hiring

So "has tags" is not the same as "belongs in a founder's recommendations". This
script records a separate verdict per book.

THE THREE-WAY VERDICT MATTERS
-----------------------------
A binary "is this a business book?" gate would wrongly exclude much of the
curated canon — Atomic Habits, Deep Work, Mindset, So Good They Can't Ignore You
and How to Win Friends are all deliberately in the canon and none of them is a
business book. Hence ADJACENT: not about business, but genuinely load-bearing for
a founder. Only OFF_TOPIC is ever filtered out.

FAILS OPEN
----------
Unscreened books (topic_fit IS NULL) stay recommendable. Running this script is
what activates the gate, book by book — nothing changes until it does.

Run (resumable; repeat with --limit to work through a large catalog):
    python -m app.scripts.screen_book_topics --dry-run --limit 20
    python -m app.scripts.screen_book_topics --limit 200
    python -m app.scripts.screen_book_topics --rescreen        # redo everything
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional

import anthropic
from sqlalchemy import or_

from app.database import SessionLocal
from app import models
from app.models import (
    TOPIC_FIT_ADJACENT,
    TOPIC_FIT_CORE,
    TOPIC_FIT_OFF,
    TOPIC_FIT_VALUES,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("Missing ANTHROPIC_API_KEY. Add it to backend/.env")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

MODEL = "claude-haiku-4-5-20251001"
BATCH_COMMIT_EVERY = 25


SYSTEM_PROMPT = """You screen books for Readar, a recommendation engine that tells entrepreneurs which book to read next to solve a specific business problem.

Classify ONE book into exactly one bucket.

core
  Squarely about building, running, growing or funding a business.
  Strategy, sales, marketing, pricing, operations, product, finance, hiring,
  leadership of a company, entrepreneurship itself.
  Examples: The E-Myth Revisited, Predictable Revenue, Profit First, Obviously Awesome.

adjacent
  NOT a business book, but carries real, direct value for a founder: personal
  effectiveness, mindset, habits, focus, decision-making, negotiation,
  communication, psychology of persuasion, or a substantive biography/account of
  a company or founder that teaches business lessons.
  Examples: Atomic Habits, Deep Work, Mindset, So Good They Can't Ignore You,
  How to Win Friends and Influence People, Never Split the Difference, Bad Blood.
  BE GENEROUS HERE. Many of the best founder books are not business books.

off_topic
  A reader would gain nothing *as an entrepreneur*. Fiction and novels, academic
  or technical textbooks in unrelated fields, sports writing, relationships and
  parenting, cooking, travel, religious or devotional texts, hobby guides, exam
  prep, and pure reference works.
  Examples: Microserfs (a novel), Calculus for the Practical Man, a book about a
  basketball season, Eight Dates (a marriage book).

RULES
1. Return ONLY valid JSON. No markdown, no prose, no code fences.
2. Shape: {"topic_fit": "core"|"adjacent"|"off_topic", "reason": "<max 100 chars>"}
3. When genuinely torn between adjacent and off_topic, choose adjacent — wrongly
   hiding a good founder book costs more than leaving a marginal one in.
4. A technical/academic textbook is off_topic even if its subject (game theory,
   statistics, economics) sounds business-adjacent. Readar recommends books a
   founder reads to act, not to study.
5. Judge the book itself, not its tags. Existing tags may be wrong — that is
   exactly what you are here to catch."""


USER_PROMPT_TEMPLATE = """Title: {title}
Author: {author}
Description: {description}
{extra_context}

Classify this book."""


def _build_extra_context(book: models.Book) -> str:
    parts = []
    if book.categories:
        parts.append(f"Categories: {', '.join(book.categories)}")
    if book.published_year:
        parts.append(f"Published: {book.published_year}")
    if book.functional_tags:
        parts.append(f"Existing tags (may be wrong): {', '.join(book.functional_tags)}")
    return "\n".join(parts)


def _validate(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Coerce the model's reply into a known verdict, or reject it."""
    verdict = data.get("topic_fit")
    if not isinstance(verdict, str) or verdict.strip().lower() not in TOPIC_FIT_VALUES:
        return None
    reason = data.get("reason")
    return {
        "topic_fit": verdict.strip().lower(),
        "reason": (str(reason)[:100] if reason else None),
    }


def _screen(book: models.Book) -> Optional[Dict[str, Any]]:
    """Call Claude Haiku for a single verdict. Returns None if unusable."""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        title=book.title,
        author=book.author_name or "Unknown",
        description=(book.description or "")[:800],
        extra_context=_build_extra_context(book),
    )

    for attempt in range(3):
        try:
            message = client.messages.create(
                model=MODEL,
                max_tokens=150,
                timeout=30.0,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = message.content[0].text.strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            result = _validate(json.loads(text))
            if result:
                return result
            logger.warning("Unrecognized verdict for '%s': %s", book.title, text[:120])
            return None

        except json.JSONDecodeError as e:
            logger.warning("JSON parse error for '%s' (attempt %d): %s", book.title, attempt + 1, e)
            if attempt < 2:
                time.sleep(2)
        except anthropic.RateLimitError:
            wait = 10 * (attempt + 1)
            logger.warning("Rate limited (attempt %d) — waiting %ds", attempt + 1, wait)
            time.sleep(wait)
        except Exception as e:
            logger.error("Claude API error for '%s': %s", book.title, e)
            if attempt < 2:
                time.sleep(5)
            else:
                return None

    logger.error("All retries exhausted for '%s'", book.title)
    return None


def screen_books(
    limit: Optional[int] = None,
    dry_run: bool = False,
    rescreen: bool = False,
) -> None:
    """
    Screen books for topic fit.

    :param limit: Max books to process this run (resumable — repeat to continue).
    :param dry_run: Print verdicts without writing to the DB.
    :param rescreen: Re-screen books that already have a verdict.
    """
    db = SessionLocal()
    try:
        q = db.query(models.Book)
        if not rescreen:
            q = q.filter(models.Book.topic_fit.is_(None))
        # Only books that could actually be recommended are worth spending a
        # call on; untagged stubs are already excluded by candidate_books_query.
        q = q.filter(
            or_(
                models.Book.functional_tags.isnot(None),
                models.Book.business_stage_tags.isnot(None),
                models.Book.theme_tags.isnot(None),
            )
        ).order_by(models.Book.created_at)

        if limit:
            q = q.limit(limit)
        books = q.all()

        if not books:
            logger.info("No books to screen. Done.")
            return

        logger.info("Screening %d book(s)%s", len(books), " (dry run)" if dry_run else "")
        counts = {TOPIC_FIT_CORE: 0, TOPIC_FIT_ADJACENT: 0, TOPIC_FIT_OFF: 0}
        processed = 0
        failed = 0

        for i, book in enumerate(books, 1):
            verdict = _screen(book)
            if not verdict:
                failed += 1
                continue

            fit, reason = verdict["topic_fit"], verdict["reason"]
            counts[fit] += 1
            marker = "  EXCLUDE" if fit == TOPIC_FIT_OFF else ""
            logger.info("[%d/%d] %-9s %s%s", i, len(books), fit, book.title[:52], marker)
            if reason and fit == TOPIC_FIT_OFF:
                logger.info("           reason: %s", reason)

            if not dry_run:
                try:
                    book.topic_fit = fit
                    book.topic_fit_reason = reason
                    db.flush()
                except Exception as e:
                    logger.error("  DB error for '%s': %s", book.title, e)
                    db.rollback()
                    failed += 1
                    continue

            processed += 1
            if not dry_run and processed % BATCH_COMMIT_EVERY == 0:
                db.commit()
                logger.info("  ** committed %d **", processed)

            if i < len(books):
                time.sleep(1.0)

        if not dry_run:
            db.commit()

        total = sum(counts.values()) or 1
        logger.info(
            "Done. screened=%d failed=%d | core=%d adjacent=%d off_topic=%d (%.0f%% excluded)",
            processed, failed,
            counts[TOPIC_FIT_CORE], counts[TOPIC_FIT_ADJACENT], counts[TOPIC_FIT_OFF],
            100.0 * counts[TOPIC_FIT_OFF] / total,
        )
        if dry_run:
            logger.info("Dry run — nothing written.")

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Screen catalog books for entrepreneurial topic fit (RD-23)."
    )
    parser.add_argument("--limit", type=int, default=None,
                        help="Max books to process this run. Resumable.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print verdicts without saving.")
    parser.add_argument("--rescreen", action="store_true",
                        help="Re-screen books that already have a verdict.")
    args = parser.parse_args()

    screen_books(limit=args.limit, dry_run=args.dry_run, rescreen=args.rescreen)
