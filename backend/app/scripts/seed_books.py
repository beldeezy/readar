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
from pathlib import Path
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app import models

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_FILES = [
    BASE_DIR / "data" / "readar_canon_v1.json",
    BASE_DIR / "data" / "readar_canon_services_v1.json",
    BASE_DIR / "data" / "readar_canon_saas_v1.json",
]

LEGACY_FILE = BASE_DIR / "data" / "seed_books.json"


def _coerce_difficulty(raw):
    """
    Map JSON difficulty string -> BookDifficulty enum.

    Accepts case-insensitive 'light' | 'medium' | 'deep'.
    Returns None if not recognized / not provided.
    """
    if not raw:
        return None

    value = str(raw).strip().lower()
    try:
        return models.BookDifficulty(value)
    except ValueError:
        # Unknown difficulty label – ignore instead of crashing
        return None


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
    Load and concatenate books from all provided files.
    Later files can overwrite earlier ones via the update logic.
    """
    all_books: list[dict] = []

    for path in files:
        books = _load_books_from_file(path)
        all_books.extend(books)

    if not all_books:
        raise FileNotFoundError(
            "No books loaded. Checked files:\n"
            + "\n".join(str(p) for p in files)
        )

    print(f"[seed_books] Total raw book records loaded: {len(all_books)}")
    return all_books


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

            existing = (
                db.query(models.Book)
                .filter(
                    models.Book.title == title,
                    models.Book.author_name == author_name,
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

            difficulty = _coerce_difficulty(b.get("difficulty"))

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
            )

            if hasattr(models.Book, "created_at"):
                setattr(book, "created_at", datetime.utcnow())

            db.add(book)
            created += 1

        db.commit()
        print(
            f"[seed_books] Seed complete. Created={created}, "
            f"Updated={updated}, Skipped={skipped}"
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
        # Default behavior: use main canon + services if they exist,
        # otherwise fall back to legacy seed_books.json if needed.
        files = []
        for p in DEFAULT_FILES:
            if p.exists():
                files.append(p)
        if not files and LEGACY_FILE.exists():
            files.append(LEGACY_FILE)

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
