# backend/app/scripts/generate_descriptions.py
"""
Generate structured book descriptions using Claude Haiku.

Descriptions follow a codified criteria optimized for the recommendation engine:
- Length: 500-1000 characters (3-5 sentences)
- Structure: Core premise → Outcome/value → Supporting detail with frameworks
- Must include: concrete outcome, business stage/challenge language, author credibility
- Must avoid: marketing fluff, full spoilers, generic language
"""

import os
import time
import logging
from typing import Optional

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

SYSTEM_PROMPT = """You write structured book descriptions for a business book recommendation engine.

Your descriptions must follow this exact criteria:

LENGTH: 500-1000 characters (3-5 sentences).

STRUCTURE (always follow this order):
1. Core premise (1 sentence): What the book is fundamentally about — the central argument or framework.
2. Outcome/value (1-2 sentences): What a reader gains — concrete skills, mental models, or strategic capabilities. Use language that maps to business challenges (e.g., "helps founders who struggle with..." or "gives operators a framework for...").
3. Supporting detail (1-2 sentences): Mention key frameworks, models, or the author's credibility signal (e.g., "Drawing from 20 years leading Pixar..." or "Based on interviews with 200+ founders...").

MUST INCLUDE:
- At least one concrete outcome (what someone can DO after reading)
- Business stage or challenge language (startup, scaling, leadership, sales, etc.)
- Author credibility signal (experience, research, role)

MUST AVOID:
- Marketing fluff ("groundbreaking", "must-read", "game-changing")
- Full plot/content spoilers
- Generic language that could apply to any business book
- Superlatives and hyperbole
- Quotation marks around the description

Write in third person. Be specific and direct."""

USER_PROMPT_TEMPLATE = """Write a description for this book:

Title: {title}
Author: {author}
{extra_context}

Remember: 500-1000 characters, 3-5 sentences. Core premise → Outcome/value → Supporting detail."""


def _build_extra_context(book: models.Book) -> str:
    """Build additional context from existing book metadata."""
    parts = []

    if book.categories:
        parts.append(f"Categories: {', '.join(book.categories)}")

    if book.published_year:
        parts.append(f"Published: {book.published_year}")

    if book.page_count:
        parts.append(f"Pages: {book.page_count}")

    if book.business_stage_tags:
        parts.append(f"Business stages: {', '.join(book.business_stage_tags)}")

    if book.functional_tags:
        parts.append(f"Functional areas: {', '.join(book.functional_tags)}")

    if book.theme_tags:
        parts.append(f"Themes: {', '.join(book.theme_tags)}")

    if book.promise:
        parts.append(f"Promise: {book.promise}")

    if book.best_for:
        parts.append(f"Best for: {book.best_for}")

    return "\n".join(parts) if parts else ""


def _generate_description(title: str, author: str, extra_context: str) -> Optional[str]:
    """Call Claude Haiku to generate a description."""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        title=title,
        author=author,
        extra_context=extra_context,
    )

    import re

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                timeout=30.0,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
            )
            text = message.content[0].text.strip()

            # Remove wrapping quotes if present
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1].strip()

            # Remove markdown headers/bold titles that Haiku sometimes adds
            text = re.sub(r'^#+\s+.*\n+', '', text).strip()
            text = re.sub(r'^\*\*[^*]+\*\*\s*\n+', '', text).strip()
            text = re.sub(r'^\*\*([^*]+)\*\*', r'\1', text).strip()

            return text

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


def _is_placeholder(description: Optional[str], author_name: str) -> bool:
    """Check if a description needs replacement."""
    if not description:
        return True
    if description == "No description available.":
        return True
    if description.startswith(f"A book by {author_name}"):
        return True
    return False


def generate_descriptions(
    limit: Optional[int] = None,
    dry_run: bool = False,
    all_books: bool = False,
) -> None:
    """
    Generate descriptions for books missing quality descriptions.

    :param limit: Max number of books to process.
    :param dry_run: If True, print descriptions but don't save to DB.
    :param all_books: If True, regenerate even for books with existing descriptions.
    """
    db: Session = SessionLocal()
    try:
        query = db.query(models.Book).order_by(models.Book.created_at.asc())

        if not all_books:
            # Only books with placeholder descriptions
            query = query.filter(
                models.Book.description.in_([
                    "No description available.",
                    "",
                ])
                | models.Book.description.is_(None)
                | models.Book.description.like("A book by %")
            )

        if limit:
            query = query.limit(limit)

        books = query.all()
        logger.info("Found %d book(s) needing descriptions", len(books))

        generated = 0
        failed = 0

        for i, book in enumerate(books, 1):
            logger.info("[%d/%d] Generating description for '%s' by %s",
                        i, len(books), book.title, book.author_name)

            extra_context = _build_extra_context(book)
            description = _generate_description(book.title, book.author_name, extra_context)

            if not description:
                failed += 1
                continue

            char_count = len(description)
            logger.info("  Generated (%d chars): %s", char_count, description[:100] + "...")

            if dry_run:
                print(f"\n{'='*60}")
                print(f"TITLE: {book.title}")
                print(f"AUTHOR: {book.author_name}")
                print(f"CHARS: {char_count}")
                print(f"DESCRIPTION:\n{description}")
                print(f"{'='*60}")
            else:
                book.description = description

            generated += 1

            # Batch commit every 25 books to avoid losing progress
            if not dry_run and generated % 25 == 0:
                db.commit()
                logger.info("  ** Batch committed %d descriptions so far **", generated)

            # Delay between calls to stay under rate limits
            if i < len(books):
                time.sleep(1.0)

        if not dry_run:
            db.commit()
            logger.info("Final commit — %d description(s) saved to database", generated)

        logger.info("Done. Generated: %d, Failed: %d", generated, failed)

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate book descriptions using Claude Haiku."
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max number of books to process.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print descriptions without saving to DB.",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Regenerate descriptions for all books, not just placeholders.",
    )
    args = parser.parse_args()

    generate_descriptions(
        limit=args.limit,
        dry_run=args.dry_run,
        all_books=args.all,
    )
