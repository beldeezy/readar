# backend/app/scripts/seed_books.py

"""
Seed the Readar book catalog from one or more JSON files.

Usage examples:

  # Default: seed core canon + services canon if they exist
  cd backend
  source venv/bin/activate
  python -m app.scripts.seed_books

  # Seed a specific file only
  python -m app.scripts.seed_books --file app/data/readar_canon_services_v1.json

  # Seed multiple files explicitly
  python -m app.scripts.seed_books \
    --file app/data/readar_canon_v1.json \
    --file app/data/readar_canon_services_v1.json
"""

import argparse
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session
import sqlalchemy as sa

from app.database import SessionLocal
from app import models

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_FILES = [
    BASE_DIR / "data" / "readar_canon_v1.json",
    BASE_DIR / "data" / "readar_canon_services_v1.json",
    BASE_DIR / "data" / "readar_canon_saas_v1.json",
    BASE_DIR / "data" / "books_seed.json",
]


def normalize_enum(value: Any) -> Optional[str]:
    """
    Normalize enum values from JSON before inserting into Postgres.
    
    - If value is None/empty -> return None
    - If it's a string -> strip whitespace, lowercase it
    - Return the normalized string
    """
    if value is None:
        return None
    
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized if normalized else None
    
    # For non-string values, convert to string first
    normalized = str(value).strip().lower()
    return normalized if normalized else None


def _coerce_difficulty(raw, title: str = ""):
    """
    Map JSON difficulty string -> BookDifficulty enum.

    Returns a BookDifficulty or None.
    """
    if raw is None:
        return None

    normalized = normalize_enum(raw)  # whatever this does today

    if not normalized:
        return None

    # Normalize to lowercase tokens that match DB enum labels
    norm = str(normalized).strip().lower()

    difficulty_map = {
        "easy": "light",
        "light": "light",
        "beginner": "light",
        "medium": "medium",
        "moderate": "medium",
        "intermediate": "medium",
        "hard": "deep",
        "deep": "deep",
        "advanced": "deep",
    }

    mapped = difficulty_map.get(norm, norm)

    try:
        # IMPORTANT: return actual Enum member so SQLAlchemy writes correct label
        from app.models import BookDifficulty

        return BookDifficulty(mapped)
    except Exception:
        logger.warning(f"[seed_books] invalid difficulty={raw} title={title}, setting to None")
        return None


def _get_difficulty(book_dict: dict):
    """
    Extract difficulty from book dict, handling both 'difficulty' and 'difficulty_level' keys.
    """
    title = book_dict.get("title", "")
    return _coerce_difficulty(
        book_dict.get("difficulty") or book_dict.get("difficulty_level"),
        title=title
    )


def _richness_score(book_dict: dict) -> int:
    """
    Calculate a richness score for a book record.
    Higher score = more complete/richer data.
    Used to prefer richer records when deduplicating.
    """
    score = 0
    
    # Description is valuable
    if book_dict.get("description"):
        score += 10
    
    # Insight fields are valuable
    if book_dict.get("promise"):
        score += 5
    if book_dict.get("best_for"):
        score += 5
    if book_dict.get("core_frameworks"):
        score += 3
    if book_dict.get("anti_patterns"):
        score += 3
    if book_dict.get("outcomes"):
        score += 3
    
    # Other metadata
    if book_dict.get("subtitle"):
        score += 2
    if book_dict.get("page_count"):
        score += 1
    if book_dict.get("published_year"):
        score += 1
    if book_dict.get("thumbnail_url") or book_dict.get("cover_image_url"):
        score += 1
    
    return score


def _load_books_from_file(path: Path) -> list[dict]:
    """Load a single JSON file of books, or return empty if file missing."""
    if not path.exists():
        print(f"[seed_books] File not found, skipping: {path}")
        return []

    print(f"[seed_books] Loading books from: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected list of books in {path}, got {type(data)}")

    return data


def _collect_books(files: list[Path]) -> list[dict]:
    """
    Load books from all provided files and deduplicate.
    
    Deduplication key: (title.lower().strip(), author_name.lower().strip())
    When duplicates exist, prefer the record with richer fields (higher richness score).
    """
    all_books_raw: list[dict] = []

    for path in files:
        books = _load_books_from_file(path)
        all_books_raw.extend(books)

    if not all_books_raw:
        raise FileNotFoundError(
            "No books loaded. Checked files:\n"
            + "\n".join(str(p) for p in files)
        )

    print(f"[seed_books] Total raw book records loaded: {len(all_books_raw)}")
    
    # Deduplicate by (title, author_name) - prefer richer records
    books_by_key: dict[tuple[str, str], dict] = {}
    
    for book in all_books_raw:
        title = (book.get("title") or "").strip()
        author_name = (book.get("author_name") or "").strip()
        
        if not title or not author_name:
            continue
        
        key = (title.lower().strip(), author_name.lower().strip())
        
        if key not in books_by_key:
            books_by_key[key] = book
        else:
            # Compare richness scores - keep the richer one
            existing_score = _richness_score(books_by_key[key])
            new_score = _richness_score(book)
            
            if new_score > existing_score:
                books_by_key[key] = book
    
    deduplicated = list(books_by_key.values())
    print(f"[seed_books] After deduplication: {len(deduplicated)} unique books")
    
    return deduplicated


def seed_books(files: list[Path]):
    raw_books = _collect_books(files)

    db: Session = SessionLocal()
    try:
        created = 0
        updated = 0
        skipped = 0

        for b in raw_books:
            title = (b.get("title") or "").strip()
            author_name = (b.get("author_name") or "").strip()

            if not title or not author_name:
                # Hard skip any garbage rows
                skipped += 1
                continue

            # Use case-insensitive lookup for consistency with deduplication
            existing = (
                db.query(models.Book)
                .filter(
                    sa.func.lower(models.Book.title) == title.lower(),
                    sa.func.lower(models.Book.author_name) == author_name.lower(),
                )
                .one_or_none()
            )

            # Description: required in your model
            description = (
                b.get("description")
                or b.get("subtitle")
                or f"A book by {author_name}"
            )

            # Normalize array fields (avoid None)
            categories = b.get("categories") or []
            business_stage_tags = b.get("business_stage_tags") or []
            functional_tags = b.get("functional_tags") or []
            theme_tags = b.get("theme_tags") or []

            # Optional visual/meta fields if present
            thumbnail_url = b.get("thumbnail_url")
            cover_image_url = b.get("cover_image_url")
            page_count = b.get("page_count")
            published_year = b.get("published_year")

            # Handle both 'difficulty' and 'difficulty_level' keys
            # _get_difficulty returns a BookDifficulty enum or None
            difficulty = _get_difficulty(b)
            
            # New insight fields (use if present, else None)
            promise = b.get("promise")
            best_for = b.get("best_for")
            # List fields: use if present and is list, else None
            core_frameworks = b.get("core_frameworks") if isinstance(b.get("core_frameworks"), list) else None
            anti_patterns = b.get("anti_patterns") if isinstance(b.get("anti_patterns"), list) else None
            outcomes = b.get("outcomes") if isinstance(b.get("outcomes"), list) else None

            if existing:
                # Idempotent update: keep existing id, refresh fields from JSON
                existing.subtitle = b.get("subtitle")
                existing.description = description
                existing.thumbnail_url = thumbnail_url
                existing.cover_image_url = cover_image_url
                existing.page_count = page_count
                existing.published_year = published_year
                existing.categories = categories
                existing.business_stage_tags = business_stage_tags
                existing.functional_tags = functional_tags
                existing.theme_tags = theme_tags
                existing.difficulty = difficulty
                # Update insight fields if present
                if promise is not None:
                    existing.promise = promise
                if best_for is not None:
                    existing.best_for = best_for
                if core_frameworks is not None:
                    existing.core_frameworks = core_frameworks
                if anti_patterns is not None:
                    existing.anti_patterns = anti_patterns
                if outcomes is not None:
                    existing.outcomes = outcomes
                if hasattr(existing, "updated_at"):
                    existing.updated_at = datetime.utcnow()

                updated += 1
                continue

            # Create new book
            book = models.Book(
                title=title,
                subtitle=b.get("subtitle"),
                author_name=author_name,
                description=description,
                thumbnail_url=thumbnail_url,
                cover_image_url=cover_image_url,
                page_count=page_count,
                published_year=published_year,
                categories=categories,
                business_stage_tags=business_stage_tags,
                functional_tags=functional_tags,
                theme_tags=theme_tags,
                difficulty=difficulty,
                # Insight fields
                promise=promise,
                best_for=best_for,
                core_frameworks=core_frameworks,
                anti_patterns=anti_patterns,
                outcomes=outcomes,
            )

            if hasattr(models.Book, "created_at"):
                setattr(book, "created_at", datetime.utcnow())

            db.add(book)
            created += 1

        db.commit()
        print(
            f"[seed_books] Commit successful. Created={created} Updated={updated}"
        )
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Seed the Readar book catalog from JSON files."
    )
    parser.add_argument(
        "--file",
        "-f",
        action="append",
        dest="files",
        help=(
            "Path to a JSON file of books. "
            "Can be specified multiple times. "
            "If omitted, uses default canon files."
        ),
    )

    args = parser.parse_args()

    if args.files:
        # Use only the files the user specified
        files = [Path(f).resolve() for f in args.files]
    else:
        # Default behavior: use all canon files that exist
        files = []
        for p in DEFAULT_FILES:
            if p.exists():
                files.append(p)

    if not files:
        raise FileNotFoundError(
            "No seed files found. "
            "Tried defaults and legacy. Use --file to specify explicitly."
        )

    print("[seed_books] Using files:")
    for p in files:
        print(f"  - {p}")

    seed_books(files)


if __name__ == "__main__":
    main()
