# backend/app/scripts/generate_tags.py
"""
Generate structured metadata tags for books using Claude Haiku.

Populates: business_stage_tags, functional_tags, theme_tags,
           promise, best_for, core_frameworks, outcomes, difficulty

Tags follow a controlled vocabulary that maps directly to the
recommendation engine's scoring functions.
"""

import json
import os
import re
import time
import logging
from typing import Optional, Dict, Any

import anthropic
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app import models

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("Missing ANTHROPIC_API_KEY. Add it to backend/.env")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Controlled vocabulary ────────────────────────────────────────────
# These MUST match what the recommendation engine checks against.

VALID_BUSINESS_STAGES = {"idea", "pre-revenue", "early-revenue", "scaling"}

VALID_FUNCTIONAL_TAGS = {
    "pricing", "marketing", "sales", "operations", "product",
    "leadership", "client_acquisition", "service_delivery",
    "plg", "growth", "metrics", "analytics", "hiring",
    "finance", "strategy", "fundraising", "culture",
    "productivity", "negotiation", "communication",
}

# Canon tags — only for books truly foundational to that business model
VALID_CANON_TAGS = {"services_canon", "saas_canon"}

# Must match BookDifficulty enum: light, medium, deep
VALID_DIFFICULTY = {"light", "medium", "deep"}

# Map from common AI-generated values to our enum
DIFFICULTY_MAP = {
    "beginner": "light",
    "intermediate": "medium",
    "advanced": "deep",
    "light": "light",
    "medium": "medium",
    "deep": "deep",
}

# ── Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a metadata tagger for a business book recommendation engine.

Your job is to analyze a book and return structured JSON tags that help the engine match books to entrepreneurs based on their business stage, focus areas, and challenges.

IMPORTANT RULES:
1. Return ONLY valid JSON. No markdown, no explanation, no extra text.
2. Use ONLY the allowed values specified below. Do not invent new tags.
3. Assign tags conservatively — only tag what the book genuinely covers.
4. A book can have multiple business_stage_tags if it spans stages.
5. canon tags (services_canon, saas_canon) are RARE — only for books widely considered essential reading for that business model (e.g., "Built to Sell" for services, "Inspired" for SaaS).

ALLOWED VALUES:

business_stage_tags (pick 1-3):
  idea, pre-revenue, early-revenue, scaling

functional_tags (pick 1-5 from this list):
  pricing, marketing, sales, operations, product, leadership,
  client_acquisition, service_delivery, plg, growth, metrics,
  analytics, hiring, finance, strategy, fundraising, culture,
  productivity, negotiation, communication

  Special canon tags (use VERY sparingly — only for truly canonical books):
  services_canon, saas_canon

theme_tags (free-form, 1-4 short lowercase tags describing core themes):
  Examples: "mindset", "systems_thinking", "negotiation", "team_building",
  "customer_discovery", "lean_startup", "pricing_strategy", "copywriting",
  "habit_formation", "decision_making", "venture_capital"

difficulty: light | medium | deep

promise (1 sentence, max 120 chars): What the reader will gain.

best_for (1 sentence, max 120 chars): Who benefits most from this book.

core_frameworks (list of 1-3 strings): Named frameworks, models, or methods from the book.
  Use actual framework names if known (e.g., "Jobs To Be Done", "EOS/Traction", "Lean Canvas").
  If no named frameworks, describe the core model briefly.

outcomes (list of 1-3 strings): Concrete skills or capabilities gained.
  Be specific (e.g., "Build a repeatable sales process", "Price services for profit margins above 40%").

Return JSON in this exact format:
{
  "business_stage_tags": ["pre-revenue", "early-revenue"],
  "functional_tags": ["sales", "client_acquisition"],
  "theme_tags": ["consultative_selling", "pipeline_management"],
  "difficulty": "medium",
  "promise": "Learn to build a predictable B2B sales pipeline from scratch.",
  "best_for": "Early-stage founders who need to close their first 10 customers.",
  "core_frameworks": ["SPIN Selling", "Challenger Sale"],
  "outcomes": ["Build a repeatable outbound sales process", "Handle objections systematically"]
}"""

USER_PROMPT_TEMPLATE = """Analyze this book and return the JSON metadata tags.

Title: {title}
Author: {author}
Description: {description}
{extra_context}

Return ONLY the JSON object. No markdown fences, no explanation."""


def _build_extra_context(book: models.Book) -> str:
    """Build additional context from existing book metadata."""
    parts = []
    if book.categories:
        parts.append(f"Categories: {', '.join(book.categories)}")
    if book.published_year:
        parts.append(f"Published: {book.published_year}")
    if book.page_count:
        parts.append(f"Pages: {book.page_count}")
    return "\n".join(parts) if parts else ""


def _validate_and_clean(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize the generated tags against controlled vocabulary."""

    # business_stage_tags
    raw_stages = data.get("business_stage_tags", [])
    if isinstance(raw_stages, list):
        data["business_stage_tags"] = [
            s for s in raw_stages if s in VALID_BUSINESS_STAGES
        ]
    else:
        data["business_stage_tags"] = []

    # functional_tags
    raw_func = data.get("functional_tags", [])
    allowed_func = VALID_FUNCTIONAL_TAGS | VALID_CANON_TAGS
    if isinstance(raw_func, list):
        data["functional_tags"] = [
            t for t in raw_func if t in allowed_func
        ]
    else:
        data["functional_tags"] = []

    # theme_tags — free-form but sanitize
    raw_themes = data.get("theme_tags", [])
    if isinstance(raw_themes, list):
        data["theme_tags"] = [
            re.sub(r'[^a-z0-9_]', '_', t.lower().strip())
            for t in raw_themes[:4] if isinstance(t, str) and t.strip()
        ]
    else:
        data["theme_tags"] = []

    # difficulty — map beginner/intermediate/advanced to light/medium/deep
    diff = data.get("difficulty", "")
    data["difficulty"] = DIFFICULTY_MAP.get(diff) if diff else None

    # promise — truncate
    promise = data.get("promise", "")
    data["promise"] = (promise[:120] if isinstance(promise, str) else None) or None

    # best_for — truncate
    best_for = data.get("best_for", "")
    data["best_for"] = (best_for[:120] if isinstance(best_for, str) else None) or None

    # core_frameworks — ensure list of strings
    raw_fw = data.get("core_frameworks", [])
    if isinstance(raw_fw, list):
        data["core_frameworks"] = [str(fw)[:100] for fw in raw_fw[:3] if fw]
    else:
        data["core_frameworks"] = []

    # outcomes — ensure list of strings
    raw_out = data.get("outcomes", [])
    if isinstance(raw_out, list):
        data["outcomes"] = [str(o)[:150] for o in raw_out[:3] if o]
    else:
        data["outcomes"] = []

    return data


def _generate_tags(title: str, author: str, description: str, extra_context: str) -> Optional[Dict[str, Any]]:
    """Call Claude Haiku to generate structured tags."""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        title=title,
        author=author,
        description=description[:800],  # Cap description length for token efficiency
        extra_context=extra_context,
    )

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                timeout=30.0,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
            )
            text = message.content[0].text.strip()

            # Strip markdown code fences if present
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)

            data = json.loads(text)
            return _validate_and_clean(data)

        except json.JSONDecodeError as e:
            logger.warning("JSON parse error for '%s' (attempt %d): %s", title, attempt + 1, e)
            if attempt < 2:
                time.sleep(2)
        except anthropic.RateLimitError:
            wait = 10 * (attempt + 1)
            logger.warning("Rate limited (attempt %d) — waiting %ds", attempt + 1, wait)
            time.sleep(wait)
        except Exception as e:
            logger.error("Claude API error for '%s' by '%s': %s", title, author, e)
            if attempt < 2:
                time.sleep(5)
            else:
                return None

    logger.error("All retries exhausted for '%s' by '%s'", title, author)
    return None


def _needs_tags(book: models.Book) -> bool:
    """Check if a book needs tag generation."""
    return (
        not book.business_stage_tags
        and not book.functional_tags
        and not book.theme_tags
    )


def generate_tags(
    limit: Optional[int] = None,
    dry_run: bool = False,
    all_books: bool = False,
) -> None:
    """
    Generate structured metadata tags for books.

    :param limit: Max number of books to process.
    :param dry_run: If True, print tags but don't save to DB.
    :param all_books: If True, regenerate even for books with existing tags.
    """
    db: Session = SessionLocal()
    try:
        query = db.query(models.Book).order_by(models.Book.created_at.asc())

        if not all_books:
            # Only books without tags
            query = query.filter(
                models.Book.business_stage_tags.is_(None)
                | (models.Book.business_stage_tags == '{}')
            )

        if limit:
            query = query.limit(limit)

        books = query.all()

        # Double-check with Python-side filter for edge cases
        if not all_books:
            books = [b for b in books if _needs_tags(b)]

        logger.info("Found %d book(s) needing tags", len(books))

        generated = 0
        failed = 0

        for i, book in enumerate(books, 1):
            logger.info("[%d/%d] Generating tags for '%s' by %s",
                        i, len(books), book.title, book.author_name)

            extra_context = _build_extra_context(book)
            tags = _generate_tags(
                book.title, book.author_name,
                book.description or "", extra_context
            )

            if not tags:
                failed += 1
                continue

            if dry_run:
                print(f"\n{'='*60}")
                print(f"TITLE: {book.title}")
                print(f"AUTHOR: {book.author_name}")
                print(json.dumps(tags, indent=2))
                print(f"{'='*60}")
            else:
                try:
                    book.business_stage_tags = tags["business_stage_tags"]
                    book.functional_tags = tags["functional_tags"]
                    book.theme_tags = tags["theme_tags"]

                    # Convert difficulty string to BookDifficulty enum
                    diff_val = tags.get("difficulty")
                    if diff_val and diff_val in VALID_DIFFICULTY:
                        book.difficulty = models.BookDifficulty(diff_val)
                    else:
                        book.difficulty = None

                    book.promise = tags.get("promise")
                    book.best_for = tags.get("best_for")
                    book.core_frameworks = tags.get("core_frameworks")
                    book.outcomes = tags.get("outcomes")
                    db.flush()
                except Exception as e:
                    logger.error("  DB error for '%s': %s", book.title, e)
                    db.rollback()
                    failed += 1
                    continue

            generated += 1

            # Batch commit every 25 books
            if not dry_run and generated % 25 == 0:
                db.commit()
                logger.info("  ** Batch committed %d tagged books so far **", generated)

            # Rate limit delay
            if i < len(books):
                time.sleep(1.0)

        if not dry_run:
            db.commit()
            logger.info("Final commit — %d book(s) tagged", generated)

        logger.info("Done. Generated: %d, Failed: %d", generated, failed)

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate book metadata tags using Claude Haiku."
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max number of books to process.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print tags without saving to DB.",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Regenerate tags for all books, not just those without tags.",
    )
    args = parser.parse_args()

    generate_tags(
        limit=args.limit,
        dry_run=args.dry_run,
        all_books=args.all,
    )
