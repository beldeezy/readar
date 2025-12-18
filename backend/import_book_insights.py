#!/usr/bin/env python3
"""
Import book insights from CSV file.

This script parses the Book Curation Sheet CSV and calls edit_book_insights.py
for each book to populate insight fields.
"""

import csv
import json
import re
import subprocess
import sys
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


def parse_list_field(value: str) -> Optional[list[str]]:
    """
    Parse a list field that is separated by semicolons (as used in this CSV).
    Returns None if empty, otherwise a list of trimmed strings.
    """
    if not value or not value.strip():
        return None
    
    # This CSV uses semicolons as separators
    # Split by semicolon and clean up each item
    items = [item.strip() for item in value.split(';') if item.strip()]
    
    return items if items else None


def escape_shell_arg(value: str) -> str:
    """
    Escape a string for safe use in shell command arguments.
    Uses single quotes and escapes any single quotes within.
    """
    # Replace single quotes with '\'' (end quote, escaped quote, start quote)
    escaped = value.replace("'", "'\\''")
    return f"'{escaped}'"


def build_command(
    title: str,
    author: Optional[str],
    promise: Optional[str],
    best_for: Optional[str],
    core_frameworks: Optional[list[str]],
    anti_patterns: Optional[list[str]],
    outcomes: Optional[list[str]],
) -> list[str]:
    """
    Build the command arguments for edit_book_insights.py.
    Returns a list of strings suitable for subprocess.run().
    """
    cmd = [
        sys.executable,
        "-m",
        "app.scripts.edit_book_insights",
        "--title",
        title,
    ]
    
    if author:
        cmd.extend(["--author", author])
    
    if promise:
        cmd.extend(["--promise", promise])
    
    if best_for:
        cmd.extend(["--best-for", best_for])
    
    if core_frameworks:
        cmd.extend(["--core-frameworks", json.dumps(core_frameworks)])
    
    if anti_patterns:
        cmd.extend(["--anti-patterns", json.dumps(anti_patterns)])
    
    if outcomes:
        cmd.extend(["--outcomes", json.dumps(outcomes)])
    
    return cmd


def process_csv(csv_path: Path) -> tuple[int, int, list[dict]]:
    """
    Process the CSV file and update books.
    Returns (success_count, error_count, errors_list).
    """
    success_count = 0
    error_count = 0
    errors = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Find the best_for column name dynamically (handles curly apostrophe)
        best_for_col = None
        for col in reader.fieldnames:
            if 'Best for' in col:
                best_for_col = col
                break
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
            title_raw = row.get('Title', '').strip()
            if not title_raw:
                error_count += 1
                errors.append({
                    'row': row_num,
                    'title': '(empty title)',
                    'reason': 'Missing title'
                })
                continue
            
            # Normalize title (remove year)
            title = normalize_title(title_raw)
            
            # Normalize author (remove parenthetical additions)
            author_raw = row.get('Author', '').strip()
            author = normalize_author(author_raw) if author_raw else None
            promise = row.get('Promise (Helps you ___ by ___)', '').strip() or None
            best_for = row.get(best_for_col, '').strip() or None if best_for_col else None
            
            # Parse list fields
            core_frameworks_raw = row.get('Core frameworks (2–5 key concepts)', '').strip()
            anti_patterns_raw = row.get('Anti-patterns (mistakes to stop doing)', '').strip()
            outcomes_raw = row.get('Outcomes (observable results)', '').strip()
            
            core_frameworks = parse_list_field(core_frameworks_raw)
            anti_patterns = parse_list_field(anti_patterns_raw)
            outcomes = parse_list_field(outcomes_raw)
            
            # Build and run command
            cmd = build_command(
                title=title,
                author=author,
                promise=promise,
                best_for=best_for,
                core_frameworks=core_frameworks,
                anti_patterns=anti_patterns,
                outcomes=outcomes,
            )
            
            print(f"\n[{row_num}] Processing: {title}")
            if title != title_raw:
                print(f"    (Normalized from: {title_raw})")
            if author:
                print(f"    Author: {author}")
                if author_raw and author != author_raw:
                    print(f"    (Normalized from: {author_raw})")
            
            try:
                result = subprocess.run(
                    cmd,
                    cwd=Path(__file__).parent,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                print(result.stdout)
                success_count += 1
                print(f"✅ Successfully updated: {title}")
                
            except subprocess.CalledProcessError as e:
                error_count += 1
                error_msg = e.stderr.strip() if e.stderr else str(e)
                errors.append({
                    'row': row_num,
                    'title': title,
                    'reason': error_msg
                })
                print(f"❌ Error updating {title}: {error_msg}")
                
            except Exception as e:
                error_count += 1
                errors.append({
                    'row': row_num,
                    'title': title,
                    'reason': f"Unexpected error: {str(e)}"
                })
                print(f"❌ Unexpected error for {title}: {e}")
    
    return success_count, error_count, errors


def main():
    csv_path = Path("/Users/michaelbelden/Downloads/Book Curation Sheet - Sheet1.csv")
    
    if not csv_path.exists():
        print(f"Error: CSV file not found at {csv_path}", file=sys.stderr)
        sys.exit(1)
    
    print("=" * 60)
    print("Importing Book Insights from CSV")
    print("=" * 60)
    print(f"CSV file: {csv_path}")
    print()
    
    success_count, error_count, errors = process_csv(csv_path)
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✅ {success_count} updated")
    if error_count > 0:
        print(f"❗ {error_count} skipped due to errors:")
        for err in errors:
            print(f"   Row {err['row']}: {err['title']} - {err['reason']}")
    else:
        print("❗ 0 skipped")
    print("=" * 60)
    
    sys.exit(0 if error_count == 0 else 1)


if __name__ == "__main__":
    main()


