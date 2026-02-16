"""
Automated Amazon Best Sellers book discovery script.

Scrapes Amazon Best Sellers lists for business/entrepreneurship books and writes
them to a pending review CSV for manual approval before ingestion.

Usage:
    # Discover from Amazon Best Sellers - Entrepreneurship
    python -m backend.scripts.discover_amazon_books --category entrepreneurship --limit 50

    # Discover from multiple categories
    python -m backend.scripts.discover_amazon_books --category small-business --limit 30

    # Check deduplication (requires database)
    python -m backend.scripts.discover_amazon_books --category entrepreneurship --limit 50 --check-duplicates

Features:
    - Rate limiting (configurable delay between requests)
    - ISBN extraction from product pages
    - Deduplication against existing catalog
    - Pending review CSV output
    - Error handling and retry logic

Requirements:
    pip install requests beautifulsoup4
"""

import sys
from pathlib import Path

# Add backend/ to sys.path for app imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

import argparse
import csv
import time
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# Optional: Import DB models for deduplication check
try:
    from app.database import SessionLocal
    from app.models import Book
    from sqlalchemy import or_
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("Warning: Database not available. Deduplication check will be skipped.")


# Amazon Best Sellers URLs by category
AMAZON_CATEGORIES = {
    "entrepreneurship": "https://www.amazon.com/Best-Sellers-Books-Entrepreneurship/zgbs/books/2636",
    "small-business": "https://www.amazon.com/Best-Sellers-Books-Small-Business-Entrepreneurship/zgbs/books/2574",
    "business": "https://www.amazon.com/Best-Sellers-Books-Business-Money/zgbs/books/1",
    "startups": "https://www.amazon.com/Best-Sellers-Kindle-Store-Startups-Entrepreneurship/zgbs/digital-text/6511686011",
}

# User agent to avoid blocking
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def fetch_bestsellers_page(category_url: str, page: int = 1) -> Optional[BeautifulSoup]:
    """
    Fetch Amazon best sellers page and return parsed HTML.

    Args:
        category_url: Amazon category URL
        page: Page number (1-indexed)

    Returns:
        BeautifulSoup object or None if request fails
    """
    # Add page parameter if not first page
    url = category_url
    if page > 1:
        url = f"{category_url}?pg={page}"

    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.content, "html.parser")
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def extract_isbn_from_product_page(product_url: str, delay: float = 1.0) -> Optional[str]:
    """
    Fetch product page and extract ISBN-13.

    Args:
        product_url: Amazon product URL (ASIN)
        delay: Delay before request (rate limiting)

    Returns:
        ISBN-13 string or None
    """
    time.sleep(delay)  # Rate limiting

    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(product_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # Method 1: Look for ISBN in product details
        # Amazon shows ISBN-13 in the "Product details" section
        details_section = soup.find("div", {"id": "detailBullets_feature_div"})
        if details_section:
            text = details_section.get_text()
            isbn_match = re.search(r'ISBN-13[:\s]+(\d{3}-?\d{10}|\d{13})', text)
            if isbn_match:
                isbn = isbn_match.group(1).replace("-", "")
                if len(isbn) == 13:
                    return isbn

        # Method 2: Look in technical details table
        tech_details = soup.find("table", {"id": "productDetailsTable"})
        if tech_details:
            text = tech_details.get_text()
            isbn_match = re.search(r'ISBN-13[:\s]+(\d{3}-?\d{10}|\d{13})', text)
            if isbn_match:
                isbn = isbn_match.group(1).replace("-", "")
                if len(isbn) == 13:
                    return isbn

        # Method 3: Look in newer product details layout
        detail_bullets = soup.find_all("li", {"class": "a-spacing-mini"})
        for li in detail_bullets:
            text = li.get_text()
            if "ISBN-13" in text:
                isbn_match = re.search(r'(\d{3}-?\d{10}|\d{13})', text)
                if isbn_match:
                    isbn = isbn_match.group(1).replace("-", "")
                    if len(isbn) == 13:
                        return isbn

        return None

    except Exception as e:
        print(f"Error fetching ISBN from {product_url}: {e}")
        return None


def parse_bestsellers_list(soup: BeautifulSoup, limit: int, fetch_isbn: bool = True, delay: float = 1.0) -> List[Dict[str, Any]]:
    """
    Parse Amazon best sellers page and extract book data.

    Args:
        soup: BeautifulSoup object
        limit: Maximum number of books to extract
        fetch_isbn: Whether to fetch ISBN from product pages (slower but more accurate)
        delay: Delay between ISBN fetches

    Returns:
        List of book dicts with title, author, rank, url, isbn13
    """
    books = []

    # Find all book items in the list
    # Amazon uses different class names, try multiple selectors
    items = soup.find_all("div", {"class": "zg-grid-general-faceout"})
    if not items:
        items = soup.find_all("div", {"data-index": True})  # Alternative selector

    for idx, item in enumerate(items):
        if len(books) >= limit:
            break

        try:
            # Extract title
            title_elem = item.find("div", {"class": "_cDEzb_p13n-sc-css-line-clamp-1_1Fn1y"})
            if not title_elem:
                title_elem = item.find("a", {"class": "a-link-normal"})
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)

            # Extract author
            author_elem = item.find("div", {"class": "a-row a-size-small"})
            if not author_elem:
                author_elem = item.find("span", {"class": "a-size-small a-color-base"})

            author = "Unknown Author"
            if author_elem:
                author_text = author_elem.get_text(strip=True)
                # Clean up "by Author Name" format
                author = re.sub(r'^by\s+', '', author_text, flags=re.IGNORECASE).strip()

            # Extract product URL
            link_elem = item.find("a", href=True)
            if not link_elem:
                continue

            product_url = link_elem["href"]
            if not product_url.startswith("http"):
                product_url = f"https://www.amazon.com{product_url}"

            # Extract rank (position in list)
            rank = idx + 1

            # Extract ISBN if requested
            isbn13 = None
            if fetch_isbn:
                print(f"Fetching ISBN for: {title[:50]}...")
                isbn13 = extract_isbn_from_product_page(product_url, delay=delay)
                if isbn13:
                    print(f"  Found ISBN: {isbn13}")
                else:
                    print(f"  No ISBN found")

            books.append({
                "title": title,
                "author": author,
                "isbn13": isbn13 or "",
                "source_name": "amazon",
                "source_year": datetime.now().year,
                "source_rank": rank,
                "source_category": "entrepreneurship",  # Will be set by caller
                "source_url": product_url,
            })

        except Exception as e:
            print(f"Error parsing book item {idx}: {e}")
            continue

    return books


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


def check_if_duplicate(book: Dict[str, Any], db_session=None) -> bool:
    """
    Check if book already exists in catalog.

    Args:
        book: Book dict with title, author, isbn13
        db_session: Optional database session for checking

    Returns:
        True if duplicate, False if new
    """
    if not DB_AVAILABLE or not db_session:
        return False

    # Check by ISBN-13 first (most reliable)
    if book.get("isbn13"):
        existing = db_session.query(Book).filter(Book.isbn_13 == book["isbn13"]).first()
        if existing:
            print(f"  Duplicate (ISBN): {book['title'][:50]}")
            return True

    # Check by normalized title + author
    work_key = compute_work_key(book["title"], book["author"])

    # Query books with similar title/author
    title_parts = normalize_text(book["title"]).split()[:3]  # First 3 words
    author_parts = normalize_text(book["author"]).split()[:2]  # First 2 words

    if not title_parts or not author_parts:
        return False

    # Build ILIKE filters
    title_filters = [Book.title.ilike(f"%{part}%") for part in title_parts]
    author_filters = [Book.author_name.ilike(f"%{part}%") for part in author_parts]

    candidates = db_session.query(Book).filter(
        or_(*title_filters),
        or_(*author_filters)
    ).all()

    # Check work_key match
    for candidate in candidates:
        candidate_key = compute_work_key(candidate.title, candidate.author_name)
        if candidate_key == work_key:
            print(f"  Duplicate (title/author): {book['title'][:50]}")
            return True

    return False


def write_pending_review_csv(books: List[Dict[str, Any]], output_dir: Path, category: str) -> Path:
    """
    Write discovered books to pending review CSV.

    Args:
        books: List of book dicts
        output_dir: Output directory path
        category: Category name for filename

    Returns:
        Path to created CSV file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"pending_review_amazon_{category}_{timestamp}.csv"
    output_path = output_dir / filename

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write CSV
    fieldnames = ["title", "author", "source_name", "source_year", "source_rank", "source_category", "isbn13", "source_url"]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for book in books:
            writer.writerow(book)

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Discover books from Amazon Best Sellers")
    parser.add_argument(
        '--category',
        choices=list(AMAZON_CATEGORIES.keys()),
        default='entrepreneurship',
        help='Amazon category to scrape'
    )
    parser.add_argument('--limit', type=int, default=50, help='Maximum number of books to discover')
    parser.add_argument('--output-dir', default='backend/data/pending_review', help='Output directory for pending review CSV')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests in seconds')
    parser.add_argument('--check-duplicates', action='store_true', help='Check against existing catalog (requires database)')
    parser.add_argument('--fetch-isbn', action='store_true', help='Fetch ISBN from product pages (slower but more accurate)')
    args = parser.parse_args()

    print(f"Discovering Amazon Best Sellers: {args.category}")
    print(f"Limit: {args.limit}")
    print(f"Fetch ISBN: {args.fetch_isbn}")
    print(f"Check duplicates: {args.check_duplicates}")
    print()

    # Get category URL
    category_url = AMAZON_CATEGORIES[args.category]

    # Fetch and parse best sellers page
    print(f"Fetching: {category_url}")
    soup = fetch_bestsellers_page(category_url)

    if not soup:
        print("Failed to fetch best sellers page")
        return 1

    print("Parsing books...")
    books = parse_bestsellers_list(
        soup,
        limit=args.limit,
        fetch_isbn=args.fetch_isbn,
        delay=args.delay
    )

    print(f"\nFound {len(books)} books")

    # Set category for all books
    for book in books:
        book["source_category"] = args.category

    # Check for duplicates if requested
    if args.check_duplicates and DB_AVAILABLE:
        print("\nChecking for duplicates...")
        db = SessionLocal()

        filtered_books = []
        for book in books:
            if not check_if_duplicate(book, db):
                filtered_books.append(book)

        db.close()

        print(f"\nFiltered to {len(filtered_books)} new books ({len(books) - len(filtered_books)} duplicates removed)")
        books = filtered_books

    if not books:
        print("\nNo new books to add (all were duplicates)")
        return 0

    # Write to pending review CSV
    output_dir = Path(args.output_dir)
    output_path = write_pending_review_csv(books, output_dir, args.category)

    print(f"\nPending review CSV: {output_path}")
    print(f"Total books: {len(books)}")

    # Print summary
    print("\nSample books:")
    for book in books[:5]:
        print(f"  {book['source_rank']}. {book['title'][:60]} - {book['author'][:30]}")
        if book['isbn13']:
            print(f"     ISBN: {book['isbn13']}")

    print("\nNext steps:")
    print("1. Review the CSV file and remove any off-topic books")
    print("2. Run the ingestion script:")
    print(f"   python -m backend.scripts.ingest_catalog_from_seed --seed {output_path} --commit")

    return 0


if __name__ == '__main__':
    sys.exit(main())
