# backend/app/scripts/enrich_books_with_google.py

import os
import logging
from typing import Optional, Dict, Any

import requests
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app import models

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY")
if not GOOGLE_BOOKS_API_KEY:
    raise RuntimeError("Missing GOOGLE_BOOKS_API_KEY. Add it to backend/.env")
GOOGLE_BOOKS_BASE_URL = "https://www.googleapis.com/books/v1/volumes"


def _build_query(title: str, author: str) -> Dict[str, Any]:
    # Example: q=intitle:Built to Sell+inauthor:John Warrillow
    query = f'intitle:{title} inauthor:{author}'
    params: Dict[str, Any] = {
        "q": query,
        "maxResults": 5,
    }
    if GOOGLE_BOOKS_API_KEY:
        params["key"] = GOOGLE_BOOKS_API_KEY
    return params


def _pick_best_match(title: str, author: str, items: list[dict]) -> Optional[dict]:
    """
    Heuristic: try to find a volume where the title and author are reasonably close.
    """
    title_lower = title.lower()
    author_lower = author.lower()
    best_item = None
    best_score = 0

    for item in items:
        info = item.get("volumeInfo", {})
        v_title = (info.get("title") or "").lower()
        v_authors = [a.lower() for a in (info.get("authors") or [])]

        title_score = 0
        if v_title == title_lower:
            title_score = 3
        elif title_lower in v_title or v_title in title_lower:
            title_score = 2

        author_score = 0
        if any(author_lower == a for a in v_authors):
            author_score = 3
        elif any(author_lower in a or a in author_lower for a in v_authors):
            author_score = 2

        score = title_score + author_score
        if score > best_score:
            best_score = score
            best_item = item

    # Require at least some minimal match
    if best_score == 0:
        return None

    return best_item


def _fetch_google_metadata(title: str, author: str) -> Optional[dict]:
    """
    Call Google Books API for a given book and return the chosen volume dict,
    or None if nothing reasonable is found.
    """
    params = _build_query(title, author)
    try:
        resp = requests.get(GOOGLE_BOOKS_BASE_URL, params=params, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Google Books request failed for '%s' by '%s': %s", title, author, e)
        return None

    data = resp.json()
    items = data.get("items") or []

    if not items:
        logger.info("No Google Books results for '%s' by '%s'", title, author)
        return None

    best = _pick_best_match(title, author, items)
    if not best:
        logger.info("No suitable Google Books match for '%s' by '%s'", title, author)
        return None

    return best


def _extract_identifiers(volume_info: dict) -> tuple[Optional[str], Optional[str]]:
    isbn_10 = None
    isbn_13 = None
    for ident in volume_info.get("industryIdentifiers", []):
        t = ident.get("type")
        val = ident.get("identifier")
        if t == "ISBN_10":
            isbn_10 = val
        elif t == "ISBN_13":
            isbn_13 = val
    return isbn_10, isbn_13


def enrich_books(limit: Optional[int] = None, only_missing: bool = True) -> None:
    """
    Enrich books in the database with metadata from Google Books.

    :param limit: Optional max number of books to process (for testing).
    :param only_missing: If True, only update fields that are currently null / placeholder.
    """
    db: Session = SessionLocal()
    try:
        query = db.query(models.Book).order_by(models.Book.created_at.asc())
        if limit:
            query = query.limit(limit)

        books = query.all()
        logger.info("Starting Google Books enrichment for %d book(s)", len(books))

        updated_count = 0

        for book in books:
            logger.info("Enriching '%s' by %s", book.title, book.author_name)

            volume = _fetch_google_metadata(book.title, book.author_name)
            if not volume:
                continue

            info = volume.get("volumeInfo", {})
            volume_id = volume.get("id")
            page_count = info.get("pageCount")
            categories = info.get("categories")
            description = info.get("description")
            language = info.get("language")
            published_date = info.get("publishedDate")
            average_rating = info.get("averageRating")
            ratings_count = info.get("ratingsCount")
            isbn_10, isbn_13 = _extract_identifiers(info)

            changed = False

            # external_id → Google Books volumeId
            if not book.external_id and volume_id:
                book.external_id = volume_id
                changed = True

            # Page count
            if (not only_missing or book.page_count is None) and page_count:
                book.page_count = page_count
                changed = True

            # Categories
            if (not only_missing or not book.categories) and categories:
                book.categories = categories
                changed = True

            # Description – only override if empty or generic fallback
            generic_prefix = f"A book by {book.author_name}"
            if description:
                if not book.description or book.description.startswith(generic_prefix):
                    book.description = description
                    changed = True

            # Published year – only if missing
            if (not only_missing or book.published_year is None) and published_date:
                try:
                    year = int(str(published_date)[:4])
                    if year > 0:
                        book.published_year = year
                        changed = True
                except ValueError:
                    pass

            # Language
            if (not only_missing or not book.language) and language:
                book.language = language
                changed = True

            # ISBNs
            if (not only_missing or not book.isbn_10) and isbn_10:
                book.isbn_10 = isbn_10
                changed = True

            if (not only_missing or not book.isbn_13) and isbn_13:
                book.isbn_13 = isbn_13
                changed = True

            # Ratings
            if (not only_missing or book.average_rating is None) and average_rating is not None:
                book.average_rating = float(average_rating)
                changed = True

            if (not only_missing or book.ratings_count is None) and ratings_count is not None:
                book.ratings_count = int(ratings_count)
                changed = True

            if changed:
                updated_count += 1
                logger.info("  Updated: external_id=%s, page_count=%s, language=%s, isbn_10=%s, isbn_13=%s, average_rating=%s, ratings_count=%s",
                           book.external_id, book.page_count, book.language, book.isbn_10, book.isbn_13, book.average_rating, book.ratings_count)

        db.commit()
        logger.info("Enrichment complete. Updated %d book(s).", updated_count)

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Enrich books with metadata from Google Books."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of books to process (for testing).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Update fields even if they are already populated (not just missing).",
    )
    args = parser.parse_args()

    only_missing = not args.all
    enrich_books(limit=args.limit, only_missing=only_missing)

