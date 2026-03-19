"""
One-time production catalog seeder.

Loads books_seed.json into the target database, skipping duplicates by title+author.

Usage:
    # Dry run (default) — shows what would be inserted, writes nothing:
    DATABASE_URL="postgresql://..." python -m scripts.seed_production

    # Commit to database:
    DATABASE_URL="postgresql://..." python -m scripts.seed_production --commit

    # Dry run with verbose output:
    DATABASE_URL="postgresql://..." python -m scripts.seed_production --verbose
"""

import sys
import json
import argparse
import logging
from pathlib import Path

# Allow running as `python -m scripts.seed_production` from backend/
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models import Book

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).resolve().parents[1] / "app" / "data" / "books_seed.json"


def normalize(s: str) -> str:
    """Lowercase + strip for dedup comparison."""
    return (s or "").strip().lower()


def seed(database_url: str, commit: bool, verbose: bool) -> None:
    if not SEED_FILE.exists():
        logger.error(f"Seed file not found: {SEED_FILE}")
        sys.exit(1)

    with open(SEED_FILE, "r") as f:
        books_data = json.load(f)

    logger.info(f"Loaded {len(books_data)} books from seed file")

    engine = create_engine(database_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Fetch all existing title+author pairs for fast in-memory dedup
        existing_rows = db.execute(
            text("SELECT LOWER(TRIM(title)), LOWER(TRIM(author_name)) FROM books")
        ).fetchall()
        existing_keys = {(r[0], r[1]) for r in existing_rows}
        logger.info(f"Found {len(existing_keys)} existing books in database")

        to_insert = []
        skipped = 0
        invalid = 0

        for raw in books_data:
            title = raw.get("title", "").strip()
            author = raw.get("author_name", "").strip()

            if not title or not author:
                if verbose:
                    logger.warning(f"Skipping entry missing title or author: {raw}")
                invalid += 1
                continue

            key = (normalize(title), normalize(author))
            if key in existing_keys:
                if verbose:
                    logger.debug(f"SKIP (exists): {title} — {author}")
                skipped += 1
                continue

            # Build only the columns that exist on the Book model
            book_kwargs = {
                "title": title,
                "author_name": author,
            }

            optional_fields = [
                "subtitle", "description", "thumbnail_url", "cover_image_url",
                "purchase_url", "page_count", "published_year", "language",
                "isbn_10", "isbn_13", "average_rating", "ratings_count",
                "categories", "business_stage_tags", "functional_tags",
                "theme_tags", "difficulty", "promise", "best_for",
                "core_frameworks", "anti_patterns", "outcomes", "external_id",
            ]
            for field in optional_fields:
                if field in raw and raw[field] is not None:
                    book_kwargs[field] = raw[field]

            to_insert.append(book_kwargs)
            existing_keys.add(key)  # Prevent within-batch duplicates

            if verbose:
                logger.info(f"  + {title} — {author}")

        logger.info(
            f"Summary: {len(to_insert)} to insert | {skipped} already exist | {invalid} invalid/skipped"
        )

        if not to_insert:
            logger.info("Nothing to insert. Database is already up to date.")
            return

        if not commit:
            logger.info("DRY RUN — no changes written. Pass --commit to persist.")
            return

        # Bulk insert
        logger.info(f"Inserting {len(to_insert)} books...")
        for kwargs in to_insert:
            db.add(Book(**kwargs))

        db.commit()
        logger.info(f"✓ Done. {len(to_insert)} books inserted successfully.")

    except Exception as e:
        db.rollback()
        logger.error(f"Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed production book catalog")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Write to database (default is dry-run)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print each book being inserted/skipped",
    )
    args = parser.parse_args()

    import os
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error(
            "DATABASE_URL environment variable is required.\n"
            "Usage: DATABASE_URL='postgresql://...' python -m scripts.seed_production --commit"
        )
        sys.exit(1)

    seed(database_url=db_url, commit=args.commit, verbose=args.verbose)
