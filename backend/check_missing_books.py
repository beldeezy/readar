#!/usr/bin/env python3
"""
Check which books from the CSV are missing from the database.

This script:
1. Reads the CSV file
2. Normalizes titles and authors (same logic as import_book_insights.py)
3. Checks which books exist in the database
4. Reports missing books
"""

import csv
import re
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session
import sqlalchemy as sa

from app.database import SessionLocal
from app import models


def normalize_title(title: str) -> str:
    """
    Remove year from title if present (e.g., "Book Title (2011)" -> "Book Title").
    Handles patterns like:
    - "Title (2011)" -> "Title"
    - "Title (5th c. BC)" -> "Title"
    """
    # Remove 4-digit year in parentheses at the end
    title = re.sub(r'\s*\(\d{4}\)\s*$', '', title)
    # Remove period notation like "(5th c. BC)" at the end
    title = re.sub(r'\s*\([^)]*c\.\s*[A-Z]{2}\)\s*$', '', title, flags=re.IGNORECASE)
    return title.strip()


def normalize_author(author: str) -> Optional[str]:
    """
    Normalize author name by removing parenthetical additions like "(with Blake Masters)".
    """
    if not author or not author.strip():
        return None
    
    # Remove parenthetical additions like "(with ...)" or "(with Tahl Raz)"
    author = re.sub(r'\s*\(with[^)]*\)', '', author, flags=re.IGNORECASE)
    return author.strip() or None


def find_book(db: Session, title: str, author: Optional[str] = None) -> Optional[models.Book]:
    """
    Find a book by title (and optionally author).
    Returns None if not found.
    """
    title_lower = title.strip().lower()
    
    query = db.query(models.Book).filter(
        sa.func.lower(models.Book.title) == title_lower
    )
    
    if author:
        author_lower = author.strip().lower()
        query = query.filter(
            sa.func.lower(models.Book.author_name) == author_lower
        )
    
    return query.first()


def main():
    csv_path = Path("/Users/michaelbelden/Downloads/Book Curation Sheet - Sheet1.csv")
    
    if not csv_path.exists():
        print(f"Error: CSV file not found at {csv_path}", file=sys.stderr)
        sys.exit(1)
    
    print("=" * 60)
    print("Checking for Missing Books")
    print("=" * 60)
    print(f"CSV file: {csv_path}")
    print()
    
    db: Session = SessionLocal()
    missing_books = []
    found_books = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
                title_raw = row.get('Title', '').strip()
                if not title_raw:
                    continue
                
                # Normalize title (remove year)
                title = normalize_title(title_raw)
                
                # Normalize author (remove parenthetical additions)
                author_raw = row.get('Author', '').strip()
                author = normalize_author(author_raw) if author_raw else None
                
                # Check if book exists
                book = find_book(db, title, author)
                
                if book:
                    found_books.append({
                        'row': row_num,
                        'title': title,
                        'title_raw': title_raw,
                        'author': author,
                        'author_raw': author_raw,
                    })
                else:
                    missing_books.append({
                        'row': row_num,
                        'title': title,
                        'title_raw': title_raw,
                        'author': author,
                        'author_raw': author_raw,
                    })
        
        # Print results
        print(f"✅ Found in database: {len(found_books)}")
        print(f"❌ Missing from database: {len(missing_books)}")
        print()
        
        if missing_books:
            print("=" * 60)
            print("MISSING BOOKS")
            print("=" * 60)
            for book in missing_books:
                print(f"\nRow {book['row']}:")
                print(f"  Title: {book['title']}")
                if book['title'] != book['title_raw']:
                    print(f"    (Original: {book['title_raw']})")
                if book['author']:
                    print(f"  Author: {book['author']}")
                    if book['author'] != book['author_raw']:
                        print(f"    (Original: {book['author_raw']})")
        
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total books in CSV: {len(found_books) + len(missing_books)}")
        print(f"✅ In database: {len(found_books)}")
        print(f"❌ Missing: {len(missing_books)}")
        
        if missing_books:
            print("\nTo add missing books:")
            print("1. Add them to the canon seed JSON files")
            print("2. Run: python -m app.scripts.seed_books")
            print("3. Re-run: python import_book_insights.py")
        
    finally:
        db.close()
    
    sys.exit(0 if not missing_books else 1)


if __name__ == "__main__":
    main()

