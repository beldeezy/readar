#!/usr/bin/env python3
"""
Merge books_seed.json and seed_books.json into a single canonical books_seed.json.

Removes duplicates based on normalized title + author, preferring records with:
- More complete tags
- Difficulty included
- Business model included
"""

import json
import re
from pathlib import Path
from typing import Optional


def normalize_title(title: str) -> str:
    """
    Remove year/period from title if present (e.g., "Book Title (2011)" -> "Book Title").
    Handles patterns like:
    - "Title (2011)" -> "Title"
    - "Title (5th c. BC)" -> "Title"
    Also normalizes curly apostrophes to straight ones for matching.
    """
    if not title:
        return ""
    # Normalize curly apostrophes/quotes to straight ones (U+2019, U+2018, U+201C, U+201D)
    title = title.replace('\u2019', "'")  # Right single quotation mark
    title = title.replace('\u2018', "'")  # Left single quotation mark
    title = title.replace('\u201C', '"')  # Left double quotation mark
    title = title.replace('\u201D', '"')  # Right double quotation mark
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


def count_tags(book_dict: dict) -> int:
    """Count total number of tags across all tag arrays."""
    count = 0
    for tag_field in ['categories', 'business_stage_tags', 'functional_tags', 'theme_tags']:
        tags = book_dict.get(tag_field)
        if isinstance(tags, list):
            count += len(tags)
    return count


def preference_score(book_dict: dict) -> int:
    """
    Calculate a preference score for a book record.
    Higher score = preferred when merging duplicates.
    
    Scoring:
    - More complete tags: +1 per tag
    - Difficulty included: +10
    - Business model included: +10
    - Description included: +5
    - Page count included: +2
    - Subtitle included: +2
    """
    score = 0
    
    # Count tags (more tags = better)
    score += count_tags(book_dict)
    
    # Difficulty included
    if book_dict.get("difficulty") or book_dict.get("difficulty_level"):
        score += 10
    
    # Business model included
    if book_dict.get("business_model"):
        score += 10
    
    # Other valuable fields
    if book_dict.get("description"):
        score += 5
    if book_dict.get("page_count"):
        score += 2
    if book_dict.get("subtitle"):
        score += 2
    
    return score


def merge_books(books1: list[dict], books2: list[dict]) -> list[dict]:
    """
    Merge two lists of books, removing duplicates based on normalized title + author.
    Prefers records with higher preference scores.
    """
    books_by_key: dict[tuple[str, str], dict] = {}
    
    # Process first list
    for book in books1:
        title = book.get("title", "").strip()
        author_name = book.get("author_name", "").strip()
        
        if not title or not author_name:
            continue
        
        normalized_title = normalize_title(title).lower()
        normalized_author = normalize_author(author_name)
        
        if not normalized_author:
            continue
        
        key = (normalized_title, normalized_author.lower())
        
        if key not in books_by_key:
            books_by_key[key] = book
        else:
            # Compare preference scores - keep the one with higher score
            existing_score = preference_score(books_by_key[key])
            new_score = preference_score(book)
            
            if new_score > existing_score:
                books_by_key[key] = book
    
    # Process second list
    for book in books2:
        title = book.get("title", "").strip()
        author_name = book.get("author_name", "").strip()
        
        if not title or not author_name:
            continue
        
        normalized_title = normalize_title(title).lower()
        normalized_author = normalize_author(author_name)
        
        if not normalized_author:
            continue
        
        key = (normalized_title, normalized_author.lower())
        
        if key not in books_by_key:
            books_by_key[key] = book
        else:
            # Compare preference scores - keep the one with higher score
            existing_score = preference_score(books_by_key[key])
            new_score = preference_score(book)
            
            if new_score > existing_score:
                books_by_key[key] = book
    
    return list(books_by_key.values())


def main():
    base_dir = Path(__file__).parent
    books_seed_path = base_dir / "app" / "data" / "books_seed.json"
    seed_books_path = base_dir / "app" / "data" / "seed_books.json"
    
    # Load both files
    print(f"Loading {books_seed_path}...")
    with open(books_seed_path, "r", encoding="utf-8") as f:
        books1 = json.load(f)
    print(f"  Loaded {len(books1)} books")
    
    print(f"Loading {seed_books_path}...")
    with open(seed_books_path, "r", encoding="utf-8") as f:
        books2 = json.load(f)
    print(f"  Loaded {len(books2)} books")
    
    # Merge and deduplicate
    print("\nMerging and deduplicating...")
    merged_books = merge_books(books1, books2)
    print(f"  Merged to {len(merged_books)} unique books")
    
    # Sort by title for consistency
    merged_books.sort(key=lambda b: (b.get("title", "").lower(), b.get("author_name", "").lower()))
    
    # Write merged result back to books_seed.json
    print(f"\nWriting merged result to {books_seed_path}...")
    with open(books_seed_path, "w", encoding="utf-8") as f:
        json.dump(merged_books, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Successfully merged {len(merged_books)} books into books_seed.json")
    print(f"   Removed {len(books1) + len(books2) - len(merged_books)} duplicates")


if __name__ == "__main__":
    main()

