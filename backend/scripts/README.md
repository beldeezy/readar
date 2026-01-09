# Catalog Ingestion Scripts

## ingest_catalog_from_seed.py

Ingests books from a seed CSV file, enriches them via Google Books API, and upserts into the database with source tracking.

### Prerequisites

1. **Set GOOGLE_BOOKS_API_KEY environment variable:**
   ```bash
   export GOOGLE_BOOKS_API_KEY="your-api-key-here"
   ```

2. **Prepare seed CSV file** with the following columns:
   - `title` (required)
   - `author` (required)
   - `source_name` (required): e.g., "amazon", "goodreads"
   - `source_year` (required): e.g., 2025
   - `source_rank` (required): ranking position within the source list
   - `source_category` (required): e.g., "entrepreneurship"
   - `isbn13` (optional): ISBN-13 for precise Google Books lookup
   - `source_url` (optional): URL to the source list

### Usage

**Dry-run (default):**
```bash
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.csv
```

**Commit to database:**
```bash
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.csv \
  --commit
```

**Process only first 10 rows:**
```bash
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.csv \
  --limit 10
```

**Custom API delay (default 0.2s):**
```bash
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.csv \
  --commit \
  --delay 0.5
```

### How It Works

1. **Read CSV**: Parses seed file and validates required columns
2. **Google Books Enrichment**:
   - Queries by ISBN-13 (if provided) or by title + author
   - Scores matches to avoid summaries/workbooks
   - Extracts metadata: description, images, ISBNs, categories, etc.
3. **Deduplication**:
   - Computes "work key" from normalized title + author
   - Searches existing books for same work
   - Prefers newer editions and fills missing fields
4. **Upsert Book**: Creates new book or updates existing one
5. **Track Source**: Inserts book_sources record with provenance

### Output

The script prints:
- Progress for each book (enrichment status, action taken)
- Summary statistics:
  - Processed
  - Created
  - Updated
  - Skipped
  - Failed
  - Sources inserted

### Example Seed Files

- **Empty template**: `backend/data/seeds/entrepreneurship_2025_top100.csv` (headers only)
- **Example data**: `backend/data/seeds/entrepreneurship_2025_top100.example.csv` (4 sample rows)

### Rate Limiting

Default delay between Google Books API requests: **0.2 seconds**

Configurable via `--delay` flag to avoid rate limiting.

### Exit Codes

- **0**: Success
- **1**: Errors occurred (missing API key, seed file not found, or book processing failures)
