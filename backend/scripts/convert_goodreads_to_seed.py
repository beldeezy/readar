"""
Convert Goodreads library export CSV to the seed CSV format expected by ingest_catalog_from_seed.py.

Usage:
    python -m backend.scripts.convert_goodreads_to_seed \
        --input backend/data/goodreads_library_export_1000_titles.csv \
        --output backend/data/goodreads_seed.csv
"""

import argparse
import csv
import re
import sys
from pathlib import Path


def normalize_isbn(value: str | None) -> str | None:
    """
    Normalize ISBN values from Goodreads CSV, removing Excel export artifacts.

    Examples:
        ="142990531X" -> 142990531X
        ="9781429905312" -> 9781429905312
        ="" -> None
    """
    if not value:
        return None

    value = value.strip()

    # Remove Excel-export artifacts: ="..." wrapper
    if value.startswith('="') and value.endswith('"'):
        value = value[2:-1]
    elif value.startswith('"') and value.endswith('"'):
        value = value[1:-1]

    # Keep only digits and X (ISBN-10 check digit)
    value = re.sub(r'[^0-9X]', '', value.upper())

    return value if value else None


def normalize_title(title: str) -> str:
    """Clean up title for deduplication comparison."""
    return re.sub(r'\s+', ' ', title.strip().lower())


def normalize_author(author: str) -> str:
    """Clean up author for deduplication comparison."""
    return re.sub(r'\s+', ' ', author.strip().lower())


def main():
    parser = argparse.ArgumentParser(description="Convert Goodreads CSV to seed CSV format")
    parser.add_argument("--input", required=True, help="Path to Goodreads export CSV")
    parser.add_argument("--output", required=True, help="Path for output seed CSV")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}")
        sys.exit(1)

    # Read Goodreads CSV
    rows = []
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    print(f"Read {len(rows)} rows from Goodreads CSV")

    # Convert and deduplicate
    seen_isbn13 = set()
    seen_title_author = set()
    output_rows = []
    skipped_dup = 0
    skipped_empty = 0

    for i, row in enumerate(rows, 1):
        title = (row.get("Title") or "").strip()
        author = (row.get("Author") or "").strip()

        if not title or not author:
            skipped_empty += 1
            continue

        isbn13 = normalize_isbn(row.get("ISBN13"))

        # Dedup by ISBN13
        if isbn13 and isbn13 in seen_isbn13:
            skipped_dup += 1
            continue

        # Dedup by (title, author) normalized
        dedup_key = (normalize_title(title), normalize_author(author))
        if dedup_key in seen_title_author:
            skipped_dup += 1
            continue

        if isbn13:
            seen_isbn13.add(isbn13)
        seen_title_author.add(dedup_key)

        output_rows.append({
            "title": title,
            "author": author,
            "source_name": "Goodreads Library",
            "source_year": "2025",
            "source_rank": str(i),
            "source_category": "personal-library",
            "isbn13": isbn13 or "",
            "source_url": "",
        })

    # Write seed CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["title", "author", "source_name", "source_year", "source_rank", "source_category", "isbn13", "source_url"]

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Output: {len(output_rows)} unique books written to {output_path}")
    print(f"Skipped: {skipped_dup} duplicates, {skipped_empty} empty title/author")


if __name__ == "__main__":
    main()
