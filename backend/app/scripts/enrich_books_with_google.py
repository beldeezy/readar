# backend/app/scripts/enrich_books_with_google.py

import os
import time
import logging
from typing import Optional, Dict, Any

import requests
from sqlalchemy import or_
from sqlalchemy.orm import Session

try:
    from dotenv import load_dotenv
    load_dotenv()  # no-op in prod (env vars are real); loads .env locally
except Exception:
    pass

from app.database import SessionLocal
from app import models

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Read lazily so this module can be imported without the key set (the key is
# only required when actually enriching).
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY")

GOOGLE_BOOKS_BASE_URL = "https://www.googleapis.com/books/v1/volumes"

# Open Library — free, key-less fallback for titles Google Books can't match.
OPENLIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
OPENLIBRARY_COVER_URL = "https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg"
# Open Library asks API consumers to identify themselves with a descriptive UA.
OPENLIBRARY_USER_AGENT = "ReadarBookEnricher/1.0 (+https://readar.ai)"

# Descriptions we consider "not real" and safe to overwrite.
PLACEHOLDER_DESCRIPTIONS = (
    "No description available.",
    "Imported from Goodreads reading history. Tags pending enrichment.",
)


def _is_placeholder_description(book: "models.Book") -> bool:
    """True when a book's description is empty or a known placeholder."""
    desc = (book.description or "").strip()
    if not desc:
        return True
    if desc in PLACEHOLDER_DESCRIPTIONS:
        return True
    if desc.startswith("Imported from Goodreads"):
        return True
    if desc.startswith(f"A book by {book.author_name}"):
        return True
    return False


def _to_https(url: Optional[str]) -> Optional[str]:
    return url.replace("http://", "https://") if url else url


def _extract_cover_urls(volume_info: dict) -> tuple[Optional[str], Optional[str]]:
    """Return (cover_image_url, thumbnail_url) from Google Books imageLinks."""
    links = volume_info.get("imageLinks") or {}
    cover = links.get("thumbnail") or links.get("smallThumbnail")
    thumb = links.get("smallThumbnail") or links.get("thumbnail")
    return _to_https(cover), _to_https(thumb)


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


def apply_google_metadata(book: "models.Book", only_missing: bool = True) -> bool:
    """
    Fetch Google Books metadata for a single book and apply it in place.
    Returns True if any field changed. The caller is responsible for committing.
    Safe to call without an API key (returns False) so it can be used inside
    the import flow without breaking it.
    """
    if not GOOGLE_BOOKS_API_KEY:
        return False

    volume = _fetch_google_metadata(book.title, book.author_name)
    if not volume:
        return False

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
    cover_url, thumb_url = _extract_cover_urls(info)

    changed = False

    if not book.external_id and volume_id:
        book.external_id = volume_id
        changed = True
    if (not only_missing or book.page_count is None) and page_count:
        book.page_count = page_count
        changed = True
    if (not only_missing or not book.categories) and categories:
        book.categories = categories
        changed = True
    if description and (not only_missing or _is_placeholder_description(book)):
        book.description = description
        changed = True
    if (not only_missing or not book.cover_image_url) and cover_url:
        book.cover_image_url = cover_url
        changed = True
    if (not only_missing or not book.thumbnail_url) and thumb_url:
        book.thumbnail_url = thumb_url
        changed = True
    if (not only_missing or book.published_year is None) and published_date:
        try:
            year = int(str(published_date)[:4])
            if year > 0:
                book.published_year = year
                changed = True
        except ValueError:
            pass
    if (not only_missing or not book.language) and language:
        book.language = language
        changed = True
    if (not only_missing or not book.isbn_10) and isbn_10:
        book.isbn_10 = isbn_10
        changed = True
    if (not only_missing or not book.isbn_13) and isbn_13:
        book.isbn_13 = isbn_13
        changed = True
    if (not only_missing or book.average_rating is None) and average_rating is not None:
        book.average_rating = float(average_rating)
        changed = True
    if (not only_missing or book.ratings_count is None) and ratings_count is not None:
        book.ratings_count = int(ratings_count)
        changed = True

    return changed


# ---------------------------------------------------------------------------
# Open Library fallback
# ---------------------------------------------------------------------------

def _book_needs_enrichment(book: "models.Book") -> bool:
    """True when a book still lacks a cover or a real (non-placeholder) description."""
    return not book.cover_image_url or _is_placeholder_description(book)


def _ol_pick_best_match(title: str, author: str, docs: list[dict]) -> Optional[dict]:
    """Mirror of _pick_best_match for Open Library search docs."""
    title_lower = title.lower()
    author_lower = author.lower()
    best_doc = None
    best_score = 0

    for doc in docs:
        d_title = (doc.get("title") or "").lower()
        d_authors = [a.lower() for a in (doc.get("author_name") or [])]

        title_score = 0
        if d_title == title_lower:
            title_score = 3
        elif title_lower in d_title or d_title in title_lower:
            title_score = 2

        author_score = 0
        if any(author_lower == a for a in d_authors):
            author_score = 3
        elif any(author_lower in a or a in author_lower for a in d_authors):
            author_score = 2

        score = title_score + author_score
        if score > best_score:
            best_score = score
            best_doc = doc

    if best_score == 0:
        return None
    return best_doc


def _ol_normalize_description(raw: Any) -> Optional[str]:
    """Open Library descriptions come as a plain string or {"type", "value"}."""
    if isinstance(raw, dict):
        raw = raw.get("value")
    if isinstance(raw, str):
        text = raw.strip()
        return text or None
    return None


def _fetch_openlibrary_work_description(work_key: Optional[str]) -> Optional[str]:
    """Fetch a work's description from Open Library (work_key like '/works/OL...W')."""
    if not work_key:
        return None
    try:
        resp = requests.get(
            f"https://openlibrary.org{work_key}.json",
            headers={"User-Agent": OPENLIBRARY_USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Open Library work request failed for '%s': %s", work_key, e)
        return None
    return _ol_normalize_description(resp.json().get("description"))


def _fetch_openlibrary_metadata(title: str, author: str) -> Optional[dict]:
    """
    Search Open Library for a book and return a normalized dict of the fields we
    care about (cover_url, thumbnail_url, description, published_year, isbns,
    language), or None if nothing reasonable is found.
    """
    params = {
        "title": title,
        "author": author,
        "limit": 5,
        "fields": "key,title,author_name,cover_i,first_publish_year,isbn,language",
    }
    try:
        resp = requests.get(
            OPENLIBRARY_SEARCH_URL,
            params=params,
            headers={"User-Agent": OPENLIBRARY_USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Open Library search failed for '%s' by '%s': %s", title, author, e)
        return None

    docs = resp.json().get("docs") or []
    if not docs:
        logger.info("No Open Library results for '%s' by '%s'", title, author)
        return None

    best = _ol_pick_best_match(title, author, docs)
    if not best:
        logger.info("No suitable Open Library match for '%s' by '%s'", title, author)
        return None

    cover_url = thumb_url = None
    cover_id = best.get("cover_i")
    if cover_id:
        cover_url = OPENLIBRARY_COVER_URL.format(cover_id=cover_id, size="L")
        thumb_url = OPENLIBRARY_COVER_URL.format(cover_id=cover_id, size="M")

    isbn_10 = isbn_13 = None
    for raw_isbn in best.get("isbn") or []:
        digits = str(raw_isbn).replace("-", "").strip()
        if len(digits) == 13 and not isbn_13:
            isbn_13 = digits
        elif len(digits) == 10 and not isbn_10:
            isbn_10 = digits

    languages = best.get("language") or []

    return {
        "description": _fetch_openlibrary_work_description(best.get("key")),
        "cover_url": cover_url,
        "thumb_url": thumb_url,
        "published_year": best.get("first_publish_year"),
        "isbn_10": isbn_10,
        "isbn_13": isbn_13,
        "language": languages[0] if languages else None,
    }


def apply_openlibrary_metadata(book: "models.Book", only_missing: bool = True) -> bool:
    """
    Fetch Open Library metadata for a single book and apply it in place. Returns
    True if any field changed. The caller commits. Needs no API key, so it works
    as a fallback for titles Google Books can't match (and even with no Google key).
    """
    data = _fetch_openlibrary_metadata(book.title, book.author_name)
    if not data:
        return False

    changed = False

    description = data.get("description")
    if description and (not only_missing or _is_placeholder_description(book)):
        book.description = description
        changed = True
    if (not only_missing or not book.cover_image_url) and data.get("cover_url"):
        book.cover_image_url = data["cover_url"]
        changed = True
    if (not only_missing or not book.thumbnail_url) and data.get("thumb_url"):
        book.thumbnail_url = data["thumb_url"]
        changed = True
    published_year = data.get("published_year")
    if (not only_missing or book.published_year is None) and published_year:
        try:
            year = int(published_year)
            if year > 0:
                book.published_year = year
                changed = True
        except (ValueError, TypeError):
            pass
    if (not only_missing or not book.isbn_10) and data.get("isbn_10"):
        book.isbn_10 = data["isbn_10"]
        changed = True
    if (not only_missing or not book.isbn_13) and data.get("isbn_13"):
        book.isbn_13 = data["isbn_13"]
        changed = True
    if (not only_missing or not book.language) and data.get("language"):
        book.language = data["language"]
        changed = True

    return changed


def apply_book_metadata(
    book: "models.Book",
    only_missing: bool = True,
    use_openlibrary_fallback: bool = True,
) -> bool:
    """
    Enrich a book from Google Books, then fall back to Open Library for anything
    still missing (cover / real description). Returns True if any field changed.
    """
    changed = apply_google_metadata(book, only_missing=only_missing)

    if use_openlibrary_fallback and _book_needs_enrichment(book):
        if apply_openlibrary_metadata(book, only_missing=only_missing):
            changed = True

    return changed


def enrich_books(
    limit: Optional[int] = None,
    only_missing: bool = True,
    descriptions_only: bool = False,
    sleep: float = 0.0,
    use_openlibrary_fallback: bool = True,
) -> None:
    """
    Enrich books in the database with metadata from Google Books.

    :param limit: Optional max number of books to process (for testing).
    :param only_missing: If True, only update fields that are currently null / placeholder.
    :param descriptions_only: If True, only process books with placeholder descriptions.
    :param sleep: Seconds to pause between Google Books requests (rate-limit friendly).
    :param use_openlibrary_fallback: If True, fall back to Open Library (no key needed)
        for books Google can't fully resolve.
    """
    if not GOOGLE_BOOKS_API_KEY:
        if not use_openlibrary_fallback:
            raise RuntimeError("Missing GOOGLE_BOOKS_API_KEY. Add it to backend/.env")
        logger.warning(
            "GOOGLE_BOOKS_API_KEY not set — running with Open Library fallback only."
        )

    db: Session = SessionLocal()
    try:
        query = db.query(models.Book).order_by(models.Book.created_at.asc())
        if descriptions_only:
            query = query.filter(or_(
                models.Book.description.is_(None),
                models.Book.description == "No description available.",
                models.Book.description.like("Imported from Goodreads%"),
            ))
        elif only_missing:
            # Default backfill: only touch books that still need a cover or a
            # real description. Makes reruns idempotent + quota-efficient.
            query = query.filter(or_(
                models.Book.cover_image_url.is_(None),
                models.Book.description.is_(None),
                models.Book.description == "No description available.",
                models.Book.description.like("Imported from Goodreads%"),
            ))
        if limit:
            query = query.limit(limit)

        books = query.all()
        logger.info("Starting Google Books enrichment for %d book(s)", len(books))

        updated_count = 0

        for book in books:
            logger.info("Enriching '%s' by %s", book.title, book.author_name)

            if apply_book_metadata(
                book,
                only_missing=only_missing,
                use_openlibrary_fallback=use_openlibrary_fallback,
            ):
                updated_count += 1
                logger.info(
                    "  Updated: cover=%s desc=%s external_id=%s",
                    bool(book.cover_image_url), bool(book.description), book.external_id,
                )

            if sleep:
                time.sleep(sleep)

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
    parser.add_argument(
        "--descriptions-only",
        action="store_true",
        help="Only process books with placeholder/missing descriptions.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Seconds to pause between Google Books requests (default 0.2).",
    )
    parser.add_argument(
        "--no-openlibrary",
        action="store_true",
        help="Disable the Open Library fallback (Google Books only).",
    )
    args = parser.parse_args()

    only_missing = not args.all
    enrich_books(
        limit=args.limit,
        only_missing=only_missing,
        descriptions_only=args.descriptions_only,
        sleep=args.sleep,
        use_openlibrary_fallback=not args.no_openlibrary,
    )
