# Catalog Ingestion System - Implementation Summary

## ✅ Implemented Components

### 1. book_sources Table + Model + Migration

**Model:** `backend/app/models.py`
```python
class BookSource(Base):
    id = UUID (PK)
    book_id = UUID (FK → books.id, CASCADE)
    source_name = Text  # "amazon", "goodreads"
    source_year = Integer
    source_rank = Integer
    source_category = Text  # "entrepreneurship"
    source_url = Text (nullable)
    created_at, updated_at

    # Constraints
    UNIQUE (book_id, source_name, source_year, source_category)
    INDEX (source_name, source_year, source_category)
    INDEX (book_id)
```

**Migration:** `backend/alembic/versions/add_book_sources_table.py`
- Revision ID: `a1b2c3d4e5f6`
- Creates table, indexes, foreign key with cascade delete

**Relationship:** `Book.sources` (one-to-many)

---

### 2. Admin Authorization (require_admin_user)

**Dependency:** `backend/app/core/auth.py`
```python
def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Admin-only access control.
    Email allowlist: michael@readar.ai
    Raises: 403 Forbidden if not admin
    """
```

**Applied to:**
- `admin_debug` router (router-level dependency)
- All endpoints under `/admin/*`

**Logs:** Admin access denials with user_id + email

---

### 3. Catalog Ingestion Script

**Location:** `backend/scripts/ingest_catalog_from_seed.py`

**Features:**
- ✅ CSV parsing with required columns validation
- ✅ Google Books API enrichment (by ISBN or title+author)
- ✅ Match scoring (avoids summaries/workbooks/guides)
- ✅ Deduplication by work_key (normalized title + author)
- ✅ Prefer newest edition, fill missing fields
- ✅ Upsert books + insert book_sources
- ✅ Rate limiting (0.2s default delay)
- ✅ Dry-run mode (default)
- ✅ Clear summary output

**CLI Usage:**
```bash
# Dry-run (no DB writes)
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.csv

# Commit to database
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.csv \
  --commit

# Process first 10 rows only
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.csv \
  --limit 10

# Custom API delay
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.csv \
  --commit \
  --delay 0.5
```

**Environment Variable Required:**
```bash
export GOOGLE_BOOKS_API_KEY="your-api-key-here"
```

**CSV Columns (Required):**
- `title`
- `author`
- `source_name` (amazon, goodreads)
- `source_year` (2025)
- `source_rank` (1, 2, 3, ...)
- `source_category` (entrepreneurship)

**CSV Columns (Optional):**
- `isbn13`
- `source_url`

**Summary Output:**
```
SUMMARY (DRY-RUN / COMMIT)
============================================================
Processed:        100
Created:          78
Updated:          15
Skipped:          5
Failed:           2
Sources inserted: 93
============================================================
```

---

### 4. Seed File Templates + Documentation

**Files Created:**

1. **Empty template:**
   - `backend/data/seeds/entrepreneurship_2025_top100.csv`
   - Headers only, ready for data entry

2. **Example data:**
   - `backend/data/seeds/entrepreneurship_2025_top100.example.csv`
   - 4 sample rows (The Lean Startup, Zero to One, etc.)

3. **Documentation:**
   - `backend/scripts/README.md`
   - Full usage examples, prerequisites, how it works

---

## 🔒 Security & Safety

1. **Admin Access Control:**
   - Email allowlist: `michael@readar.ai`
   - 403 Forbidden for non-admin
   - Logged access denials

2. **API Key Handling:**
   - Read from environment variable only
   - Never logged or exposed

3. **Dry-Run Default:**
   - Must explicitly use `--commit` to write DB
   - Prevents accidental data changes

4. **Rate Limiting:**
   - 0.2s delay between API requests (configurable)
   - Prevents Google Books API rate limits

5. **Transaction Safety:**
   - Database session commits only on success
   - Rollback on errors or dry-run

---

## 📊 Data Flow

```
CSV Seed File
    ↓
Read & Validate
    ↓
For Each Row:
    ↓
Google Books API Enrichment
(by ISBN or title+author)
    ↓
Score Matches
(avoid summaries/workbooks)
    ↓
Extract Book Data
(title, author, description, images, ISBNs, etc.)
    ↓
Find Existing Book
(by work_key = normalized title+author)
    ↓
  Found?
    Yes → Update if newer or has missing fields
    No  → Create new book
    ↓
Upsert book_sources
(track provenance)
    ↓
Commit (if --commit)
```

---

## 🚀 Next Steps

### To Run the Migration:

```bash
cd backend
alembic upgrade head
```

### To Populate Catalog:

1. Create seed CSV with 100 books:
   ```bash
   cp backend/data/seeds/entrepreneurship_2025_top100.example.csv \
      backend/data/seeds/entrepreneurship_2025_top100.csv
   # Edit CSV to add 96 more books
   ```

2. Set API key:
   ```bash
   export GOOGLE_BOOKS_API_KEY="your-key"
   ```

3. Run ingestion (dry-run first):
   ```bash
   python -m backend.scripts.ingest_catalog_from_seed \
     --seed backend/data/seeds/entrepreneurship_2025_top100.csv
   ```

4. Review output, then commit:
   ```bash
   python -m backend.scripts.ingest_catalog_from_seed \
     --seed backend/data/seeds/entrepreneurship_2025_top100.csv \
     --commit
   ```

---

## 📝 Files Modified/Created

**Modified:**
- `backend/app/models.py` - BookSource model + Book.sources relationship
- `backend/app/core/auth.py` - require_admin_user dependency
- `backend/app/routers/admin_debug.py` - apply admin auth

**Created:**
- `backend/alembic/versions/add_book_sources_table.py` - migration
- `backend/scripts/ingest_catalog_from_seed.py` - ingestion script (725 lines)
- `backend/scripts/README.md` - documentation
- `backend/scripts/__init__.py` - module marker
- `backend/data/seeds/entrepreneurship_2025_top100.csv` - empty template
- `backend/data/seeds/entrepreneurship_2025_top100.example.csv` - example data

---

## 🎯 Deliverables Checklist

- ✅ Migration + model for book_sources
- ✅ Admin dependency applied to /admin/* routes
- ✅ Ingestion script with all required features
- ✅ Seed file templates (empty + example)
- ✅ Documentation (README.md)
- ✅ Dry-run flag (default)
- ✅ Clear summary output
- ✅ Rate limiting
- ✅ Google Books API enrichment
- ✅ Deduplication by work_key
- ✅ Prefer newest edition
- ✅ Sources tracking
- ✅ Exit codes (0 = success, 1 = failure)

---

**Commit:** `0bc2a707` - "Add catalog ingestion system"
**Branch:** `claude/fix-empty-recommendations-7Lfdx`
