# Catalog Ingestion Scripts

## ingest_catalog_from_seed.py

Ingests books from a seed CSV file, enriches them via Google Books API, and upserts into the database with source tracking and match confidence auditing.

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

#### Basic Commands

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

#### Resume Mode (Safe Re-run)

Resume mode allows safe re-running after interruptions by skipping rows that already exist in `book_sources`:

```bash
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.csv \
  --commit \
  --resume
```

**Behavior:**
- Checks if source already exists by (source_name, source_year, source_rank, source_category)
- Skips processing if source found
- Logs: `[SKIP][RESUME] source=amazon rank=12`
- Prevents duplicate sources after partial failures

#### Skip Existing Books Mode

Only add new sources without modifying existing book data:

```bash
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/new_sources_2025.csv \
  --commit \
  --skip-existing-books
```

**Behavior:**
- If book already exists: don't update books table
- Still allows insertion into book_sources if source is new
- Logs: `[SKIP][BOOK_EXISTS] title="Zero to One"`
- Useful for adding new curated lists to existing catalog

#### Confidence Threshold

Set minimum match score to accept (0-100, default: 65):

```bash
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.csv \
  --commit \
  --confidence-threshold 75
```

**Behavior:**
- Rows with match score below threshold are treated as failures
- No book or source written for low-confidence matches
- Helps ensure data quality

#### Custom Report Directory

Specify where to write ingestion reports:

```bash
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.csv \
  --commit \
  --report-dir custom/reports
```

**Default:** `backend/data/ingestion_reports/`

#### Custom API Delay

Adjust delay between API requests (default 0.2s):

```bash
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.csv \
  --commit \
  --delay 0.5
```

### All Available Flags

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--seed` | string | *required* | Path to seed CSV file |
| `--commit` | flag | false | Write to database (default is dry-run) |
| `--limit` | int | none | Process only first N rows |
| `--delay` | float | 0.2 | Delay between API requests (seconds) |
| `--resume` | flag | false | Skip rows that already exist in book_sources |
| `--skip-existing-books` | flag | false | Don't update existing books, only add sources |
| `--report-dir` | string | `backend/data/ingestion_reports` | Directory for ingestion reports |
| `--confidence-threshold` | int | 65 | Minimum match score to accept (0-100) |

### How It Works

1. **Read CSV**: Parses seed file and validates required columns
2. **Resume Check** (if `--resume`): Skip rows already in book_sources
3. **Google Books Enrichment**:
   - Strategy: ISBN lookup (if provided) or title + author search
   - Queries up to 5 candidates
   - Scores matches to avoid summaries/workbooks/companions
   - Records audit metadata: match_strategy, match_score, rejected_candidates_count
4. **Confidence Check**: Reject matches below threshold
5. **Deduplication**:
   - Computes "work key" from normalized title + author
   - Searches existing books for same work
   - Prefers newer editions and fills missing fields
6. **Upsert Book**: Creates new book or updates existing one (unless `--skip-existing-books`)
7. **Track Source**: Inserts book_sources record with provenance and audit fields
8. **Generate Report**: Writes CSV report with match details and outcomes

### Match Confidence & Audit Fields

Every successful book_sources row includes audit metadata:

- **match_strategy**: `"isbn"` or `"title_author"`
- **match_score**: 0-100 (higher is better)
- **matched_volume_id**: Google Books volume ID
- **matched_isbn13**: ISBN-13 of matched book
- **rejected_candidates_count**: Number of candidates scored ≤ 0

These fields enable operators to:
- Audit enrichment quality
- Identify low-confidence matches
- Debug matching logic
- Track ISBN vs title/author match rates

### Ingestion Reports

After every run, a timestamped CSV report is written to `{report-dir}/{timestamp}.csv`.

**Report Columns:**
- `title`: Original seed title
- `author`: Original seed author
- `source_name`: Source list name
- `source_year`: Source list year
- `source_rank`: Rank within source
- `status`: `created`, `updated`, `skipped`, `skipped_resume`, `skipped_existing_book`, `failed`
- `match_strategy`: `isbn` or `title_author`
- `match_score`: 0-100 confidence score
- `matched_title`: Title from Google Books
- `matched_author`: Author from Google Books
- `matched_published_year`: Publication year from Google Books
- `notes`: Reason for skip/failure or update details

**Example Report Path:**
```
backend/data/ingestion_reports/20260109_153045.csv
```

**Use Reports To:**
- Audit why rows were created, skipped, or failed
- Identify books below confidence threshold
- Review matched titles vs seed titles
- Track enrichment success rates

### Console Output

The script prints:
- Configuration summary (flags, paths, thresholds)
- Progress for each book:
  - `[OK]` - Successfully enriched and processed
  - `[SKIP][RESUME]` - Skipped in resume mode
  - `[SKIP][BOOK_EXISTS]` - Skipped existing book (with flag)
  - `[FAIL]` - Below confidence threshold or error
  - `[WARN]` - No Google Books match, using seed data
- Summary statistics:
  - **Processed**: Total rows processed
  - **Created**: New books created
  - **Updated**: Existing books updated
  - **Skipped**: Books skipped (no updates needed)
    - **Resume**: Skipped via `--resume` (source exists)
    - **Existing book**: Skipped via `--skip-existing-books`
  - **Failed**: Rows that failed enrichment or confidence check
  - **Sources inserted**: Total book_sources rows created

**Example Summary:**
```
============================================================
SUMMARY (COMMIT)
============================================================
Processed:        100
Created:          45
Updated:          12
Skipped:          38
  - Resume:       15
  - Existing book: 5
Failed:           5
Sources inserted: 57
============================================================
```

### Example Seed Files

- **Empty template**: `backend/data/seeds/entrepreneurship_2025_top100.csv` (headers only)
- **Example data**: `backend/data/seeds/entrepreneurship_2025_top100.example.csv` (4 sample rows)

### Workflow Examples

#### Initial Ingestion

```bash
# Dry-run first to preview
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/amazon_2025_entrepreneurship.csv \
  --limit 5

# Commit after review
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/amazon_2025_entrepreneurship.csv \
  --commit
```

#### Resume After Failure

```bash
# If ingestion interrupted at row 47/100
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/amazon_2025_entrepreneurship.csv \
  --commit \
  --resume  # Skips rows 1-46 automatically
```

#### Add New Source Without Updating Books

```bash
# Add Goodreads sources to existing Amazon books
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/goodreads_2025_business.csv \
  --commit \
  --skip-existing-books
```

#### High-Confidence Only

```bash
# Only accept matches with 80+ confidence
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/curated_list.csv \
  --commit \
  --confidence-threshold 80
```

### Rate Limiting

Default delay between Google Books API requests: **0.2 seconds**

Configurable via `--delay` flag to avoid rate limiting or increase throughput.

### Exit Codes

- **0**: Success (all rows processed, no failures)
- **1**: Errors occurred (missing API key, seed file not found, or one or more book processing failures)

### Troubleshooting

**Issue:** `GOOGLE_BOOKS_API_KEY environment variable not set`
- **Solution:** Set the API key: `export GOOGLE_BOOKS_API_KEY="your-key"`

**Issue:** Many failures with "Match score X below threshold Y"
- **Solution:** Lower confidence threshold: `--confidence-threshold 50`
- **Note:** Review report CSV to see match scores and adjust threshold accordingly

**Issue:** Script interrupted, how to resume?
- **Solution:** Re-run with `--resume` flag to skip already-ingested sources

**Issue:** Want to add new source list without changing existing book data
- **Solution:** Use `--skip-existing-books` flag

**Issue:** Need to audit enrichment quality
- **Solution:** Review CSV reports in `backend/data/ingestion_reports/`
