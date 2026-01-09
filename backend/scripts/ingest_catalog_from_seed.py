"""
Catalog ingestion script: reads seed CSV, enriches via Google Books API, upserts books and sources.

Usage:
    python -m backend.scripts.ingest_catalog_from_seed --seed path/to/seed.csv [--commit] [--limit N]

Flags:
    --seed: Path to seed CSV file (required)
    --commit: Write to database (default is dry-run)
    --limit: Process only first N rows (optional)
    --delay: Delay between API requests in seconds (default 0.2)
"""

import argparse
import csv
import os
import sys
import time
import re
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import SessionLocal
from app.models import Book, BookSource
from app.core.config import settings


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, remove punctuation, extra whitespace."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
    return text


def compute_work_key(title: str, author: str) -> str:
    """
    Generate a normalized work key for deduplication.
    Format: normalized_title::normalized_author
    """
    norm_title = normalize_text(title)
    norm_author = normalize_text(author.split(',')[0].split(';')[0])  # Take first author
    return f"{norm_title}::{norm_author}"


def enrich_from_google_books(
    title: str,
    author: str,
    isbn13: Optional[str],
    api_key: str,
    delay: float = 0.2
) -> Optional[Dict[str, Any]]:
    """
    Query Google Books API and return the best match.

    Returns dict with:
        - volumeId
        - volumeInfo fields: title, subtitle, authors, description, etc.
    """
    base_url = "https://www.googleapis.com/books/v1/volumes"

    # Build query
    if isbn13:
        query = f"isbn:{isbn13}"
    else:
        # Escape quotes in title/author
        safe_title = title.replace('"', '')
        safe_author = author.replace('"', '')
        query = f'intitle:"{safe_title}" inauthor:"{safe_author}"'

    params = {
        "q": query,
        "maxResults": 5,
        "key": api_key,
    }

    try:
        time.sleep(delay)  # Rate limiting
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "items" not in data or not data["items"]:
            return None

        # Score each result
        candidates = []
        for item in data["items"]:
            volume_info = item.get("volumeInfo", {})
            score = score_google_books_match(title, author, volume_info)
            candidates.append((score, item))

        # Sort by score descending
        candidates.sort(key=lambda x: x[0], reverse=True)

        if candidates[0][0] > 0:
            best_item = candidates[0][1]
            return {
                "volumeId": best_item.get("id"),
                "volumeInfo": best_item.get("volumeInfo", {}),
                "saleInfo": best_item.get("saleInfo", {}),
            }

        return None

    except Exception as e:
        print(f"  [ERROR] Google Books API error: {e}")
        return None


def score_google_books_match(seed_title: str, seed_author: str, volume_info: Dict[str, Any]) -> float:
    """
    Score how well a Google Books volumeInfo matches the seed title/author.

    Returns float score (higher is better).
    Penalizes unwanted keywords like "summary", "workbook", etc.
    """
    score = 0.0

    gb_title = volume_info.get("title", "").lower()
    gb_authors = volume_info.get("authors", [])
    gb_author_str = " ".join(gb_authors).lower() if gb_authors else ""
    gb_description = volume_info.get("description", "").lower()

    seed_title_norm = normalize_text(seed_title)
    seed_author_norm = normalize_text(seed_author)

    # Title matching
    if seed_title_norm in normalize_text(gb_title):
        score += 10.0
    elif any(word in gb_title for word in seed_title_norm.split()[:3]):
        score += 5.0

    # Author matching
    if seed_author_norm in gb_author_str:
        score += 10.0
    elif any(word in gb_author_str for word in seed_author_norm.split()[:2]):
        score += 5.0

    # Penalize unwanted keywords
    unwanted_keywords = ["summary", "workbook", "analysis", "guide to", "companion", "journal", "study guide"]
    for keyword in unwanted_keywords:
        if keyword in gb_title or keyword in gb_description[:200]:
            score -= 20.0

    # Prefer books with publishedDate
    if volume_info.get("publishedDate"):
        score += 2.0

    return score


def extract_book_data_from_google(seed_row: Dict[str, str], google_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract book fields from Google Books API response, with fallback to seed data.

    Returns dict matching Book model fields.
    """
    if not google_data:
        # No Google data, use seed values
        return {
            "external_id": None,
            "title": seed_row["title"],
            "subtitle": None,
            "author_name": seed_row["author"],
            "description": "No description available.",
            "thumbnail_url": None,
            "cover_image_url": None,
            "purchase_url": None,
            "page_count": None,
            "published_year": None,
            "language": None,
            "isbn_10": None,
            "isbn_13": seed_row.get("isbn13"),
            "average_rating": None,
            "ratings_count": None,
            "categories": None,
        }

    volume_info = google_data.get("volumeInfo", {})
    sale_info = google_data.get("saleInfo", {})

    # Extract published_year
    published_year = None
    published_date_str = volume_info.get("publishedDate")
    if published_date_str:
        # Try to parse year (formats: "YYYY", "YYYY-MM", "YYYY-MM-DD")
        try:
            if len(published_date_str) >= 4:
                published_year = int(published_date_str[:4])
        except ValueError:
            pass

    # Image URLs
    image_links = volume_info.get("imageLinks", {})
    thumbnail_url = image_links.get("thumbnail")
    cover_image_url = image_links.get("large") or image_links.get("medium") or thumbnail_url

    # ISBNs
    isbn_10 = None
    isbn_13 = seed_row.get("isbn13")
    for identifier in volume_info.get("industryIdentifiers", []):
        if identifier.get("type") == "ISBN_10":
            isbn_10 = identifier.get("identifier")
        elif identifier.get("type") == "ISBN_13":
            isbn_13 = identifier.get("identifier")

    # Authors
    authors = volume_info.get("authors", [])
    author_name = authors[0] if authors else seed_row["author"]

    # Description
    description = volume_info.get("description") or "No description available."

    # Purchase URL
    purchase_url = sale_info.get("buyLink")

    return {
        "external_id": google_data.get("volumeId"),
        "title": volume_info.get("title") or seed_row["title"],
        "subtitle": volume_info.get("subtitle"),
        "author_name": author_name,
        "description": description,
        "thumbnail_url": thumbnail_url,
        "cover_image_url": cover_image_url,
        "purchase_url": purchase_url,
        "page_count": volume_info.get("pageCount"),
        "published_year": published_year,
        "language": volume_info.get("language"),
        "isbn_10": isbn_10,
        "isbn_13": isbn_13,
        "average_rating": volume_info.get("averageRating"),
        "ratings_count": volume_info.get("ratingsCount"),
        "categories": volume_info.get("categories"),
    }


def find_existing_book_by_work_key(db: Session, title: str, author: str) -> Optional[Book]:
    """
    Search for existing book matching the same work (title + author family).

    Returns Book if found, else None.
    """
    work_key = compute_work_key(title, author)

    # Query books with similar title/author
    # Use ILIKE for case-insensitive search
    title_parts = normalize_text(title).split()[:3]  # First 3 words
    author_parts = normalize_text(author).split()[:2]  # First 2 words

    if not title_parts or not author_parts:
        return None

    # Build ILIKE filters
    title_filters = [Book.title.ilike(f"%{part}%") for part in title_parts]
    author_filters = [Book.author_name.ilike(f"%{part}%") for part in author_parts]

    candidates = db.query(Book).filter(
        or_(*title_filters),
        or_(*author_filters)
    ).all()

    # Check work_key match
    for candidate in candidates:
        candidate_key = compute_work_key(candidate.title, candidate.author_name)
        if candidate_key == work_key:
            return candidate

    return None


def upsert_book_and_source(
    db: Session,
    book_data: Dict[str, Any],
    source_data: Dict[str, Any],
    dry_run: bool = True
) -> Tuple[str, Optional[str]]:
    """
    Upsert book and source into database.

    Returns (action, book_id):
        action: "created", "updated", "skipped"
        book_id: UUID string if created/updated, None if skipped
    """
    title = book_data["title"]
    author = book_data["author_name"]

    # Find existing book by work_key
    existing_book = find_existing_book_by_work_key(db, title, author)

    if existing_book:
        # Decide whether to update
        should_update = False

        # Update if new book has newer published_year
        if book_data.get("published_year") and existing_book.published_year:
            if book_data["published_year"] > existing_book.published_year:
                should_update = True

        # Update if existing is missing critical fields
        if not existing_book.description or existing_book.description == "No description available.":
            if book_data.get("description") and book_data["description"] != "No description available.":
                should_update = True

        if not existing_book.cover_image_url and book_data.get("cover_image_url"):
            should_update = True

        if should_update:
            if not dry_run:
                for key, value in book_data.items():
                    if value is not None:
                        setattr(existing_book, key, value)
                existing_book.updated_at = datetime.utcnow()
                db.flush()
            action = "updated"
            book_id = str(existing_book.id)
        else:
            action = "skipped"
            book_id = str(existing_book.id)

        # Upsert source
        if not dry_run and action in ("updated", "skipped"):
            existing_source = db.query(BookSource).filter(
                BookSource.book_id == existing_book.id,
                BookSource.source_name == source_data["source_name"],
                BookSource.source_year == source_data["source_year"],
                BookSource.source_category == source_data["source_category"]
            ).first()

            if not existing_source:
                new_source = BookSource(
                    book_id=existing_book.id,
                    **source_data
                )
                db.add(new_source)

        return (action, book_id)

    else:
        # Create new book
        if not dry_run:
            new_book = Book(**book_data)
            db.add(new_book)
            db.flush()

            # Create source
            new_source = BookSource(
                book_id=new_book.id,
                **source_data
            )
            db.add(new_source)

            book_id = str(new_book.id)
        else:
            book_id = None

        return ("created", book_id)


def main():
    parser = argparse.ArgumentParser(description="Ingest catalog from seed CSV")
    parser.add_argument("--seed", required=True, help="Path to seed CSV file")
    parser.add_argument("--commit", action="store_true", help="Write to database (default is dry-run)")
    parser.add_argument("--limit", type=int, help="Process only first N rows")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between API requests (seconds)")

    args = parser.parse_args()

    # Check GOOGLE_BOOKS_API_KEY
    google_api_key = os.environ.get("GOOGLE_BOOKS_API_KEY")
    if not google_api_key:
        print("[ERROR] GOOGLE_BOOKS_API_KEY environment variable not set")
        sys.exit(1)

    # Check seed file exists
    seed_path = Path(args.seed)
    if not seed_path.exists():
        print(f"[ERROR] Seed file not found: {seed_path}")
        sys.exit(1)

    dry_run = not args.commit
    mode_str = "DRY-RUN" if dry_run else "COMMIT"

    print(f"[{mode_str}] Starting catalog ingestion")
    print(f"[{mode_str}] Seed file: {seed_path}")
    print(f"[{mode_str}] Limit: {args.limit or 'none'}")
    print(f"[{mode_str}] API delay: {args.delay}s")
    print()

    # Read CSV
    rows = []
    with open(seed_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if args.limit and i >= args.limit:
                break
            rows.append(row)

    print(f"[{mode_str}] Read {len(rows)} rows from CSV")
    print()

    # Validate required columns
    required_cols = {"title", "author", "source_name", "source_year", "source_rank", "source_category"}
    if rows:
        missing = required_cols - set(rows[0].keys())
        if missing:
            print(f"[ERROR] Missing required columns: {missing}")
            sys.exit(1)

    # Statistics
    stats = {
        "processed": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "sources_inserted": 0,
    }

    db = SessionLocal()
    try:
        for i, row in enumerate(rows, 1):
            title = row["title"].strip()
            author = row["author"].strip()
            isbn13 = row.get("isbn13", "").strip() or None

            print(f"[{i}/{len(rows)}] Processing: {title} by {author}")

            stats["processed"] += 1

            try:
                # Enrich from Google Books
                google_data = enrich_from_google_books(
                    title=title,
                    author=author,
                    isbn13=isbn13,
                    api_key=google_api_key,
                    delay=args.delay
                )

                if google_data:
                    print(f"  [OK] Enriched from Google Books (volumeId: {google_data.get('volumeId')})")
                else:
                    print(f"  [WARN] No Google Books match found, using seed data")

                # Extract book data
                book_data = extract_book_data_from_google(row, google_data)

                # Source data
                source_data = {
                    "source_name": row["source_name"],
                    "source_year": int(row["source_year"]),
                    "source_rank": int(row["source_rank"]),
                    "source_category": row["source_category"],
                    "source_url": row.get("source_url", "").strip() or None,
                }

                # Upsert
                action, book_id = upsert_book_and_source(db, book_data, source_data, dry_run=dry_run)

                stats[action] += 1
                if action in ("created", "updated"):
                    stats["sources_inserted"] += 1

                print(f"  [OK] Action: {action.upper()}, book_id: {book_id or 'N/A (dry-run)'}")

            except Exception as e:
                stats["failed"] += 1
                print(f"  [ERROR] Failed: {e}")

            print()

        if not dry_run:
            db.commit()
            print(f"[{mode_str}] Database changes committed")
        else:
            db.rollback()
            print(f"[{mode_str}] Database changes rolled back (dry-run)")

    finally:
        db.close()

    # Print summary
    print()
    print("=" * 60)
    print(f"SUMMARY ({mode_str})")
    print("=" * 60)
    print(f"Processed:        {stats['processed']}")
    print(f"Created:          {stats['created']}")
    print(f"Updated:          {stats['updated']}")
    print(f"Skipped:          {stats['skipped']}")
    print(f"Failed:           {stats['failed']}")
    print(f"Sources inserted: {stats['sources_inserted']}")
    print("=" * 60)

    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
