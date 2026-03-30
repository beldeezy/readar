# app/routers/reading_history.py
"""
Reading history router.

Handles Goodreads CSV ingestion, book catalog upsert, and reading profile generation.

Upload flow:
  1. Parse CSV rows → upsert ReadingHistoryEntry (merge on re-import)
  2. Match each book against catalog by ISBN or title+author
  3. If unmatched → create minimal Book record in catalog
  4. Fire background task to tag new books (Claude Haiku) + regenerate reading profile
"""
import csv
import json
import logging
import os
import re
import time
import uuid as uuid_lib
from io import TextIOWrapper
from typing import List, Optional
from uuid import UUID

import anthropic
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy import func, or_
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.core.auth import get_current_user
from app.models import Book, BookDifficulty, PendingBook, ReadingHistoryEntry, User, UserReadingProfile
from app.services.reading_profile_service import generate_reading_profile
from app.utils.email import send_weekly_pending_books_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reading-history", tags=["reading_history"])

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Controlled vocabulary — must match generate_tags.py and recommendation engine
VALID_BUSINESS_STAGES = {"idea", "pre-revenue", "early-revenue", "scaling"}
VALID_FUNCTIONAL_TAGS = {
    "pricing", "marketing", "sales", "operations", "product", "leadership",
    "client_acquisition", "service_delivery", "plg", "growth", "metrics",
    "analytics", "hiring", "finance", "strategy", "fundraising", "culture",
    "productivity", "negotiation", "communication",
}
DIFFICULTY_MAP = {"beginner": "light", "intermediate": "medium", "advanced": "deep",
                  "light": "light", "medium": "medium", "deep": "deep"}

TAG_SYSTEM_PROMPT = """You are a metadata tagger for a business book recommendation engine.
Analyze each book and return structured JSON tags to help match books to entrepreneurs.

RULES:
1. Return ONLY valid JSON. No markdown, no explanation.
2. Use ONLY the allowed values below.
3. Tag conservatively — only what the book genuinely covers.

ALLOWED VALUES:
business_stage_tags (1-3): idea, pre-revenue, early-revenue, scaling
functional_tags (1-5): pricing, marketing, sales, operations, product, leadership,
  client_acquisition, service_delivery, plg, growth, metrics, analytics, hiring,
  finance, strategy, fundraising, culture, productivity, negotiation, communication
theme_tags (1-4, free-form lowercase_underscore)
difficulty: light | medium | deep
promise (max 120 chars): What the reader gains.
best_for (max 120 chars): Who benefits most.

Return JSON:
{
  "business_stage_tags": [...],
  "functional_tags": [...],
  "theme_tags": [...],
  "difficulty": "...",
  "promise": "...",
  "best_for": "..."
}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_isbn(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if value.startswith('="') and value.endswith('"'):
        value = value[2:-1]
    elif value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    value = re.sub(r'[^0-9X]', '', value.upper())
    return value if value else None


def _find_catalog_book(db: Session, title: str, author: str,
                       isbn: str | None, isbn13: str | None) -> Optional[Book]:
    """Find an existing Book in the catalog by ISBN or normalized title+author."""
    filters = []
    if isbn:
        filters.append(Book.isbn_10 == isbn)
    if isbn13:
        filters.append(Book.isbn_13 == isbn13)
    filters.append(
        sa.and_(
            func.lower(Book.title) == title.lower(),
            func.lower(Book.author_name) == author.lower(),
        )
    )
    return db.query(Book).filter(or_(*filters)).first()


def _upsert_reading_history_entry(
    db: Session,
    user_id: UUID,
    title: str,
    author: str,
    isbn: str | None,
    isbn13: str | None,
    my_rating: float | None,
    date_read: str | None,
    shelf: str | None,
    catalog_book_id: UUID | None,
) -> tuple[ReadingHistoryEntry, bool]:
    """
    Upsert a ReadingHistoryEntry for (user_id, title, author).
    Returns (entry, created) where created=True if a new row was inserted.
    """
    existing = (
        db.query(ReadingHistoryEntry)
        .filter(
            ReadingHistoryEntry.user_id == user_id,
            func.lower(ReadingHistoryEntry.title) == title.lower(),
            func.lower(sa.cast(ReadingHistoryEntry.author, sa.String)) == author.lower(),
        )
        .first()
    )

    if existing:
        # Merge — update mutable fields
        existing.my_rating = my_rating
        existing.date_read = date_read
        existing.shelf = shelf
        if isbn:
            existing.isbn = isbn
        if isbn13:
            existing.isbn13 = isbn13
        if catalog_book_id:
            existing.catalog_book_id = catalog_book_id
        return existing, False

    entry = ReadingHistoryEntry(
        user_id=user_id,
        title=title,
        author=author,
        isbn=isbn,
        isbn13=isbn13,
        my_rating=my_rating,
        date_read=date_read,
        shelf=shelf,
        source="goodreads",
        catalog_book_id=catalog_book_id,
    )
    db.add(entry)
    return entry, True


def _create_minimal_book(
    db: Session,
    title: str,
    author: str,
    isbn: str | None,
    isbn13: str | None,
    year_published: int | None,
    num_pages: int | None,
    goodreads_id: str | None,
) -> Book:
    """
    Create a minimal Book catalog record from Goodreads CSV metadata.
    Insight tags (business_stage_tags, functional_tags, etc.) are left empty
    and filled in by the background enrichment task.
    """
    book = Book(
        title=title,
        author_name=author,
        description=f"Imported from Goodreads reading history. Tags pending enrichment.",
        isbn_10=isbn,
        isbn_13=isbn13,
        published_year=year_published,
        page_count=num_pages,
        business_stage_tags=[],
        functional_tags=[],
        theme_tags=[],
    )
    db.add(book)
    return book


def _tag_book_with_claude(title: str, author: str) -> Optional[dict]:
    """
    Call Claude Haiku to generate insight tags for a single book.
    Returns a dict of tag fields or None on failure.
    """
    if not ANTHROPIC_API_KEY:
        return None
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        user_prompt = (
            f"Analyze this book and return the JSON metadata tags.\n\n"
            f"Title: {title}\nAuthor: {author}\n\n"
            f"Return ONLY the JSON object."
        )
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            timeout=30.0,
            system=TAG_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = message.content[0].text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return json.loads(text)
    except Exception as e:
        logger.warning("Claude tagging failed for '%s': %s", title, e)
        return None


def _apply_tags_to_book(book: Book, data: dict) -> None:
    """Apply validated Claude-generated tags to a Book record."""
    raw_stages = data.get("business_stage_tags", [])
    if isinstance(raw_stages, list):
        book.business_stage_tags = [s for s in raw_stages if s in VALID_BUSINESS_STAGES]

    raw_func = data.get("functional_tags", [])
    if isinstance(raw_func, list):
        book.functional_tags = [t for t in raw_func if t in VALID_FUNCTIONAL_TAGS]

    raw_themes = data.get("theme_tags", [])
    if isinstance(raw_themes, list):
        book.theme_tags = [
            re.sub(r'[^a-z0-9_]', '_', t.lower().strip())
            for t in raw_themes[:4] if isinstance(t, str) and t.strip()
        ]

    diff = DIFFICULTY_MAP.get(data.get("difficulty", ""))
    if diff:
        book.difficulty = diff

    promise = data.get("promise", "")
    if promise:
        book.promise = promise[:120]

    best_for = data.get("best_for", "")
    if best_for:
        book.best_for = best_for[:120]


# ---------------------------------------------------------------------------
# Background enrichment task
# ---------------------------------------------------------------------------

def _enrich_books_and_profile(user_id: UUID, new_book_ids: List[UUID]) -> None:
    """
    Background task: tag newly upserted books via Claude, then regenerate
    the user's reading profile. Uses its own DB session.
    """
    db: Session = SessionLocal()
    try:
        # Tag each new book (rate-limited: 1 call/sec to stay within Haiku limits)
        for book_id in new_book_ids:
            book = db.query(Book).filter(Book.id == book_id).first()
            if not book:
                continue
            # Skip if already tagged
            if book.business_stage_tags or book.functional_tags:
                continue
            data = _tag_book_with_claude(book.title, book.author_name)
            if data:
                _apply_tags_to_book(book, data)
                try:
                    db.commit()
                    logger.info("Tagged book '%s' (%s)", book.title, book_id)
                except Exception:
                    db.rollback()
            time.sleep(0.5)  # modest rate limiting

        # Regenerate reading profile
        generate_reading_profile(db=db, user_id=user_id)

    except Exception as e:
        logger.exception("Background enrichment failed for user_id=%s: %s", user_id, e)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload-csv")
async def upload_reading_history_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a Goodreads CSV file to import reading history.

    Batched for performance — avoids per-row DB round trips:
      1. Load full catalog + user's existing entries into memory (2 queries)
      2. Parse all CSV rows in memory
      3. Flush new Book records once to obtain IDs
      4. Upsert ReadingHistoryEntries
      5. Single commit
      6. Background task: tag new books + regenerate reading profile
    """
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file exported from Goodreads.")

    try:
        text_stream = TextIOWrapper(file.file, encoding="utf-8")
        reader = csv.DictReader(text_stream)
        rows = list(reader)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read CSV file. Export it from Goodreads and try again.")

    # ── Phase 1: load catalog + existing history into memory (2 queries) ──────
    all_books = db.query(Book).all()
    catalog_by_isbn10: dict = {b.isbn_10: b for b in all_books if b.isbn_10}
    catalog_by_isbn13: dict = {b.isbn_13: b for b in all_books if b.isbn_13}
    catalog_by_title_author: dict = {
        (b.title.lower().strip(), b.author_name.lower().strip()): b
        for b in all_books if b.title and b.author_name
    }

    existing_entries = (
        db.query(ReadingHistoryEntry)
        .filter(ReadingHistoryEntry.user_id == user.id)
        .all()
    )
    entry_map: dict = {
        (e.title.lower().strip(), (e.author or "").lower().strip()): e
        for e in existing_entries
    }

    # ── Phase 2: parse all rows in memory ────────────────────────────────────
    imported = 0
    skipped = 0
    new_books: List[Book] = []          # Book objects not yet in catalog
    pending_rows = []                   # parsed row data to process after flush

    for row in rows:
        title = (row.get("Title") or "").strip()
        author = (row.get("Author") or "").strip()
        if not title or not author:
            skipped += 1
            continue

        isbn = normalize_isbn(row.get("ISBN"))
        isbn13 = normalize_isbn(row.get("ISBN13"))

        year_published = None
        try:
            year_published = int((row.get("Year Published") or "").strip())
        except (ValueError, AttributeError):
            pass

        num_pages = None
        try:
            num_pages = int((row.get("Number of Pages") or "").strip())
        except (ValueError, AttributeError):
            pass

        my_rating = None
        try:
            raw_r = float((row.get("My Rating") or "").strip())
            my_rating = raw_r if raw_r > 0 else None
        except (ValueError, AttributeError):
            pass

        shelf = (row.get("Exclusive Shelf") or row.get("Bookshelves") or "").strip().lower() or None
        date_read = (row.get("Date Read") or "").strip() or None

        # Look up catalog book from in-memory dicts — no DB query
        catalog_book = (
            (isbn and catalog_by_isbn10.get(isbn))
            or (isbn13 and catalog_by_isbn13.get(isbn13))
            or catalog_by_title_author.get((title.lower(), author.lower()))
        )
        is_new = False
        if catalog_book is None:
            catalog_book = Book(
                title=title,
                author_name=author,
                description="Imported from Goodreads reading history. Tags pending enrichment.",
                isbn_10=isbn,
                isbn_13=isbn13,
                published_year=year_published,
                page_count=num_pages,
                business_stage_tags=[],
                functional_tags=[],
                theme_tags=[],
            )
            db.add(catalog_book)
            new_books.append(catalog_book)
            # Update in-memory dicts so duplicates in the same CSV deduplicate
            if isbn:
                catalog_by_isbn10[isbn] = catalog_book
            if isbn13:
                catalog_by_isbn13[isbn13] = catalog_book
            catalog_by_title_author[(title.lower(), author.lower())] = catalog_book
            is_new = True

        pending_rows.append((title, author, isbn, isbn13, my_rating, date_read, shelf, catalog_book, is_new))
        imported += 1

    # ── Phase 3: single flush to get IDs for all new Book records ─────────────
    if new_books:
        try:
            db.flush()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create catalog entries: {e}")

    # ── Phase 4: upsert ReadingHistoryEntries ─────────────────────────────────
    new_catalog_book_ids: List[UUID] = []
    for (title, author, isbn, isbn13, my_rating, date_read, shelf, catalog_book, is_new) in pending_rows:
        key = (title.lower().strip(), author.lower().strip())
        existing = entry_map.get(key)
        if existing:
            existing.my_rating = my_rating
            existing.date_read = date_read
            existing.shelf = shelf
            if isbn:
                existing.isbn = isbn
            if isbn13:
                existing.isbn13 = isbn13
            if catalog_book.id:
                existing.catalog_book_id = catalog_book.id
        else:
            entry = ReadingHistoryEntry(
                user_id=user.id,
                title=title,
                author=author,
                isbn=isbn,
                isbn13=isbn13,
                my_rating=my_rating,
                date_read=date_read,
                shelf=shelf,
                source="goodreads",
                catalog_book_id=catalog_book.id,
            )
            db.add(entry)
            entry_map[key] = entry

        if is_new and catalog_book.id:
            new_catalog_book_ids.append(catalog_book.id)

    # ── Phase 5: single commit ────────────────────────────────────────────────
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save reading history.")

    # ── Phase 6: background enrichment ────────────────────────────────────────
    background_tasks.add_task(_enrich_books_and_profile, user.id, new_catalog_book_ids)

    logger.info(
        "CSV import: user_id=%s, imported=%d, skipped=%d, new_catalog=%d",
        user.id, imported, skipped, len(new_catalog_book_ids),
    )
    return {
        "imported_count": imported,
        "skipped_count": skipped,
        "new_books_added": len(new_catalog_book_ids),
        "message": "Import complete. Book tags and reading profile are being generated in the background.",
    }


class ReadingHistoryEntryOut(BaseModel):
    id: str
    title: str
    author: Optional[str]
    my_rating: Optional[float]
    date_read: Optional[str]
    shelf: Optional[str]
    catalog_book_id: Optional[str]

    class Config:
        from_attributes = True


@router.get("/entries", response_model=List[ReadingHistoryEntryOut])
def get_reading_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all reading history entries for the current user."""
    entries = (
        db.query(ReadingHistoryEntry)
        .filter(ReadingHistoryEntry.user_id == user.id)
        .order_by(ReadingHistoryEntry.date_read.desc().nullslast())
        .all()
    )
    return [
        ReadingHistoryEntryOut(
            id=str(e.id),
            title=e.title,
            author=e.author,
            my_rating=e.my_rating,
            date_read=e.date_read,
            shelf=e.shelf,
            catalog_book_id=str(e.catalog_book_id) if e.catalog_book_id else None,
        )
        for e in entries
    ]


class ReadingProfileOut(BaseModel):
    total_books_read: int
    avg_rating: Optional[float]
    reading_confidence: float
    structured_tags: Optional[dict]
    profile_summary: Optional[str]
    generated_at: Optional[str]


@router.get("/profile", response_model=ReadingProfileOut)
def get_reading_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's Reading DNA profile."""
    profile = db.query(UserReadingProfile).filter(UserReadingProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No reading profile yet. Upload a Goodreads CSV to generate one.")
    return ReadingProfileOut(
        total_books_read=profile.total_books_read,
        avg_rating=profile.avg_rating,
        reading_confidence=profile.reading_confidence,
        structured_tags=profile.structured_tags,
        profile_summary=profile.profile_summary,
        generated_at=profile.generated_at.isoformat() if profile.generated_at else None,
    )


@router.post("/weekly-report")
async def send_weekly_report(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send weekly email report of new books added to pending queue."""
    logger.info("Weekly report triggered by user_id=%s", user.id)
    result = send_weekly_pending_books_email(db, recipient="michael@readar.ai")
    return result
