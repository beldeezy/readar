#!/usr/bin/env python3
"""
Bulk update book insights from enriched_book_insights.json.

This script loads enriched book insights from JSON and applies them
to the database using the edit_book_insights.py CLI script.
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


def normalize_author(author: str) -> Optional[str]:
    """
    Normalize author name by removing parenthetical additions like "(with Blake Masters)".
    """
    if not author or not author.strip():
        return None
    
    # Remove parenthetical additions like "(with ...)" or "(with Tahl Raz)"
    author = re.sub(r'\s*\(with[^)]*\)', '', author, flags=re.IGNORECASE)
    return author.strip() or None


def get_python_executable():
    """Get the Python executable, preferring venv if available."""
    base_dir = Path(__file__).parent
    venv_python = base_dir / "venv" / "bin" / "python"
    
    if venv_python.exists():
        return str(venv_python)
    
    # Fall back to sys.executable
    return sys.executable


def main():
    # Load enriched book insights
    json_path = Path(__file__).parent / "app" / "data" / "enriched_book_insights.json"
    
    if not json_path.exists():
        print(f"Error: File not found: {json_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Loading enriched book insights from: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        books = json.load(f)
    
    if not isinstance(books, list):
        print(f"Error: Expected list of books, got {type(books)}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Found {len(books)} books to update\n")
    
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    for i, book in enumerate(books, 1):
        title = book.get("title")
        author_raw = book.get("author_name", "")
        # Normalize author (remove parenthetical additions like "(with Blake Masters)")
        author = normalize_author(author_raw) if author_raw else None
        
        if not title:
            print(f"[{i}/{len(books)}] ⚠️  Skipping book with no title")
            skipped_count += 1
            continue
        
        # Build command arguments
        python_exe = get_python_executable()
        args = [
            python_exe,
            "-m",
            "app.scripts.edit_book_insights",
            "--title",
            title,
        ]
        
        if author:
            args.extend(["--author", author])
        
        if book.get("promise"):
            args.extend(["--promise", book["promise"]])
        
        if book.get("best_for"):
            args.extend(["--best-for", book["best_for"]])
        
        if book.get("core_frameworks"):
            args.extend(["--core-frameworks", json.dumps(book["core_frameworks"])])
        
        if book.get("anti_patterns"):
            args.extend(["--anti-patterns", json.dumps(book["anti_patterns"])])
        
        if book.get("outcomes"):
            args.extend(["--outcomes", json.dumps(book["outcomes"])])
        
        # Check if at least one insight field is provided
        if not any([
            book.get("promise"),
            book.get("best_for"),
            book.get("core_frameworks"),
            book.get("anti_patterns"),
            book.get("outcomes"),
        ]):
            print(f"[{i}/{len(books)}] ⚠️  Skipping '{title}': No insight fields provided")
            skipped_count += 1
            continue
        
        print(f"[{i}/{len(books)}] ⏳ Updating: {title}")
        if author:
            print(f"    Author: {author}")
            if author_raw and author != author_raw:
                print(f"    (Normalized from: {author_raw})")
        
        try:
            result = subprocess.run(
                args,
                cwd=Path(__file__).parent,
                capture_output=True,
                text=True,
                check=True,
            )
            print(f"    ✅ Updated: {title}")
            success_count += 1
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            print(f"    ❌ Failed to update {title}: {error_msg}")
            error_count += 1
        
        except Exception as e:
            print(f"    ❌ Unexpected error for {title}: {e}")
            error_count += 1
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✅ Successfully updated: {success_count}")
    print(f"❌ Failed: {error_count}")
    print(f"⚠️  Skipped: {skipped_count}")
    print(f"📊 Total processed: {len(books)}")
    print("=" * 60)
    
    sys.exit(0 if error_count == 0 else 1)


if __name__ == "__main__":
    main()

