# backend/app/scripts/edit_book_insights.py

"""
Admin CLI to edit book insight fields.

Usage examples:

  cd backend
  source venv/bin/activate
  python -m app.scripts.edit_book_insights \
    --title "Traction" \
    --promise "Find your highest-leverage acquisition channel" \
    --core-frameworks '["Bullseye Framework"]' \
    --outcomes '["Clear channel shortlist", "Weekly traction experiments"]'

  # With author disambiguation
  python -m app.scripts.edit_book_insights \
    --title "The Lean Startup" \
    --author "Eric Ries" \
    --best-for "Early-stage founders validating product-market fit"
"""

import argparse
import json
import sys
from typing import Optional

from sqlalchemy.orm import Session
import sqlalchemy as sa

from app.database import SessionLocal
from app import models


def parse_json_array(value: str) -> Optional[list[str]]:
    """
    Safely parse a JSON array string and validate it's a list of strings.
    
    Returns None if value is None/empty, or raises ValueError if invalid.
    """
    if not value or not value.strip():
        return None
    
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
    
    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON array, got {type(parsed).__name__}")
    
    # Validate all items are strings
    for i, item in enumerate(parsed):
        if not isinstance(item, str):
            raise ValueError(f"Array item at index {i} is not a string: {type(item).__name__}")
    
    return parsed


def find_book(db: Session, title: str, author: Optional[str] = None) -> models.Book:
    """
    Find a book by title (and optionally author).
    
    Handles cases where CSV title includes subtitle (e.g., "Influence: The Psychology of Persuasion")
    but database has them separated (title="Influence", subtitle="The Psychology of Persuasion").
    
    Raises ValueError if not found or multiple matches.
    """
    title_lower = title.strip().lower()
    
    # First try exact title match
    query = db.query(models.Book).filter(
        sa.func.lower(models.Book.title) == title_lower
    )
    
    if author:
        author_lower = author.strip().lower()
        query = query.filter(
            sa.func.lower(models.Book.author_name) == author_lower
        )
    
    books = query.all()
    
    # If not found and title contains a colon, try matching just the part before the colon
    # (in case CSV has "Title: Subtitle" but DB has title="Title" and subtitle="Subtitle")
    if not books and ':' in title:
        title_part = title.split(':')[0].strip().lower()
        query = db.query(models.Book).filter(
            sa.func.lower(models.Book.title) == title_part
        )
        
        if author:
            author_lower = author.strip().lower()
            query = query.filter(
                sa.func.lower(models.Book.author_name) == author_lower
            )
        
        books = query.all()
    
    if not books:
        author_hint = f" by {author}" if author else ""
        raise ValueError(f"Book not found: '{title}'{author_hint}")
    
    if len(books) > 1:
        authors = [b.author_name for b in books]
        raise ValueError(
            f"Multiple books found with title '{title}'. "
            f"Use --author to disambiguate. Found authors: {', '.join(set(authors))}"
        )
    
    return books[0]


def update_book_insights(
    db: Session,
    book: models.Book,
    promise: Optional[str] = None,
    best_for: Optional[str] = None,
    core_frameworks: Optional[list[str]] = None,
    anti_patterns: Optional[list[str]] = None,
    outcomes: Optional[list[str]] = None,
) -> models.Book:
    """
    Update insight fields on a book.
    Only updates fields that are provided (not None).
    """
    if promise is not None:
        book.promise = promise.strip() if promise else None
    
    if best_for is not None:
        book.best_for = best_for.strip() if best_for else None
    
    if core_frameworks is not None:
        book.core_frameworks = core_frameworks if core_frameworks else None
    
    if anti_patterns is not None:
        book.anti_patterns = anti_patterns if anti_patterns else None
    
    if outcomes is not None:
        book.outcomes = outcomes if outcomes else None
    
    db.commit()
    db.refresh(book)
    
    return book


def print_book_summary(book: models.Book):
    """Print a summary of the book's insight fields."""
    print("\n" + "=" * 60)
    print(f"Updated: {book.title}")
    if book.subtitle:
        print(f"Subtitle: {book.subtitle}")
    print(f"Author: {book.author_name}")
    print("=" * 60)
    print("\nInsight Fields:")
    print(f"  Promise: {book.promise or '(not set)'}")
    print(f"  Best For: {book.best_for or '(not set)'}")
    print(f"  Core Frameworks: {book.core_frameworks or '(not set)'}")
    print(f"  Anti-patterns: {book.anti_patterns or '(not set)'}")
    print(f"  Outcomes: {book.outcomes or '(not set)'}")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Edit book insight fields (promise, best_for, core_frameworks, anti_patterns, outcomes)."
    )
    parser.add_argument(
        "--title",
        "-t",
        required=True,
        help="Book title (required, case-insensitive)",
    )
    parser.add_argument(
        "--author",
        "-a",
        help="Author name (optional, for disambiguation)",
    )
    parser.add_argument(
        "--promise",
        help="What the book helps the reader achieve",
    )
    parser.add_argument(
        "--best-for",
        help="Who/when it's best (stage/scenario)",
    )
    parser.add_argument(
        "--core-frameworks",
        help="JSON array of 2-5 named frameworks/concepts, e.g. '[\"Framework A\", \"Framework B\"]'",
    )
    parser.add_argument(
        "--anti-patterns",
        help="JSON array of what it helps the reader stop doing, e.g. '[\"Pattern A\", \"Pattern B\"]'",
    )
    parser.add_argument(
        "--outcomes",
        help="JSON array of observable changes after reading, e.g. '[\"Outcome A\", \"Outcome B\"]'",
    )
    
    args = parser.parse_args()
    
    # Parse JSON array fields
    core_frameworks = None
    anti_patterns = None
    outcomes = None
    
    if args.core_frameworks:
        try:
            core_frameworks = parse_json_array(args.core_frameworks)
        except ValueError as e:
            print(f"Error parsing --core-frameworks: {e}", file=sys.stderr)
            sys.exit(1)
    
    if args.anti_patterns:
        try:
            anti_patterns = parse_json_array(args.anti_patterns)
        except ValueError as e:
            print(f"Error parsing --anti-patterns: {e}", file=sys.stderr)
            sys.exit(1)
    
    if args.outcomes:
        try:
            outcomes = parse_json_array(args.outcomes)
        except ValueError as e:
            print(f"Error parsing --outcomes: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Check that at least one field is being updated
    if not any([
        args.promise,
        args.best_for,
        args.core_frameworks,
        args.anti_patterns,
        args.outcomes,
    ]):
        print("Error: At least one insight field must be provided for update.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
    
    # Connect to database and update
    db: Session = SessionLocal()
    try:
        # Find the book
        try:
            book = find_book(db, args.title, args.author)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Update insight fields
        update_book_insights(
            db=db,
            book=book,
            promise=args.promise,
            best_for=args.best_for,
            core_frameworks=core_frameworks,
            anti_patterns=anti_patterns,
            outcomes=outcomes,
        )
        
        # Print summary
        print_book_summary(book)
        print("✓ Update successful!")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

