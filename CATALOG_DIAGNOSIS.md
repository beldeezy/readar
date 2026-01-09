# Diagnosis: "0 Recommendations" After Ingestion

## Root Cause Statement

**Most likely cause:** The database is empty because ingestion has not been run with `--commit`, or the ingestion script and backend are using different DATABASE_URL configurations.

**Secondary cause:** If books exist but all have missing `business_stage_tags` and the user has `business_stage` set in their onboarding profile, generic recommendations may filter too aggressively.

---

## Verification Steps

### Step 1: Check Which Database the Backend Uses

**Start the backend and check startup logs:**

```bash
cd backend
uvicorn app.main:app --reload
```

**Look for:**
```
[CONFIG] DATABASE_URL host=..., port=5432, database=readar
```

This shows which database the backend is connected to.

### Step 2: Check Catalog Counts via Diagnostic Endpoint

**Prerequisites:**
- Backend must be running
- You must be logged in as admin (`michael@readar.ai`)

**Query the diagnostic endpoint:**

```bash
# Get auth token first (login as michael@readar.ai)
# Then call:
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/admin/catalog-stats
```

**Expected response:**
```json
{
  "books_count": 0,
  "sources_count": 0,
  "recent_books": [],
  "recent_sources": [],
  "database_url": "postgresql://postgres:***@localhost:5432/readar"
}
```

**If `books_count = 0`:** Database is empty → run ingestion with `--commit`

**If `books_count > 0` but recommendations still return 0:** See Step 5

### Step 3: Run Database Migration

**Ensure book_sources table exists:**

```bash
cd backend
alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Running upgrade ... -> a1b2c3d4e5f6, add_book_sources_table
```

### Step 4: Run Ingestion Script

**Set Google Books API key:**
```bash
export GOOGLE_BOOKS_API_KEY="your-api-key-here"
```

**Dry-run first (verify without writing):**
```bash
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.csv \
  --limit 5
```

**Expected output:**
```
[DRY-RUN] Starting catalog ingestion
[DRY-RUN] Seed file: backend/data/seeds/entrepreneurship_2025_top100.csv
[DRY-RUN] Limit: 5

[1/5] Processing: The Lean Startup by Eric Ries
  [OK] Enriched from Google Books (volumeId: ...)
  [OK] Action: CREATED, book_id: N/A (dry-run)

...

============================================================
SUMMARY (DRY-RUN)
============================================================
Processed:        5
Created:          5
Updated:          0
Skipped:          0
Failed:           0
Sources inserted: 5
============================================================
```

**If successful, commit to database:**
```bash
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.csv \
  --limit 5 \
  --commit
```

**Expected output:**
```
[COMMIT] Starting catalog ingestion
...
[COMMIT] Database changes committed

============================================================
SUMMARY (COMMIT)
============================================================
Processed:        5
Created:          5
Updated:          0
Skipped:          0
Failed:           0
Sources inserted: 5
============================================================
```

### Step 5: Verify Books in Database

**Option A: Via API**

```bash
curl http://localhost:8000/api/books?limit=5
```

**Expected response:**
```json
[
  {
    "id": "...",
    "title": "The Lean Startup",
    "author_name": "Eric Ries",
    "description": "...",
    "published_year": 2011,
    ...
  },
  ...
]
```

**Option B: Via Admin Catalog Stats**

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/admin/catalog-stats
```

**Expected response:**
```json
{
  "books_count": 5,
  "sources_count": 5,
  "recent_books": [
    {"title": "The Lean Startup", "author_name": "Eric Ries", ...},
    ...
  ]
}
```

### Step 6: Verify Recommendations

**Option A: Via curl**

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/recommendations?limit=5
```

**Expected response (if books exist):**
```json
{
  "request_id": "...",
  "items": [
    {
      "book_id": "...",
      "title": "The Lean Startup",
      "author_name": "Eric Ries",
      "score": 0.85,
      ...
    },
    ...
  ]
}
```

**Option B: Via frontend**

1. Complete onboarding
2. Navigate to `/recommendations/loading`
3. Should see recommendations page (not "No recommendations yet")

### Step 7: Check Backend Logs

**If recommendations still return 0 despite books existing:**

**Look for logs containing:**
```
[RECS_EMPTY] user_id=... ratings=0 history=0 has_profile=True reason=no_catalog
```

**If `reason=no_catalog` but `books_count > 0`:**
- Backend and ingestion script are using **different databases**
- Check `DATABASE_URL` in both contexts

**If `reason=no_matches`:**
- Books exist but filters are too restrictive
- Check if books have `business_stage_tags` or `functional_tags` populated
- See Step 8 for fix

### Step 8: Fix "No Matches" Issue

**If books exist but have no tags, recommendations may be empty.**

**Workaround: Add tags during ingestion**

Edit `backend/scripts/ingest_catalog_from_seed.py` (around line 210):

```python
# Add default tags for books without them
if not book_data.get("categories"):
    book_data["categories"] = [seed_row["source_category"]]  # e.g., ["entrepreneurship"]

# Add business_stage_tags if missing
if not book_data.get("business_stage_tags"):
    book_data["business_stage_tags"] = ["idea", "pre-revenue", "early-revenue", "scaling"]
```

**Or: Ensure Google Books enrichment provides categories (already implemented)**

---

## Common Issues & Fixes

### Issue 1: ImportError when running ingestion script

**Error:**
```
ModuleNotFoundError: No module named 'app'
```

**Fix:** Already fixed in commit `bee7b26c`. Ensure you have latest code.

### Issue 2: `GOOGLE_BOOKS_API_KEY` not set

**Error:**
```
[ERROR] GOOGLE_BOOKS_API_KEY environment variable not set
```

**Fix:**
```bash
export GOOGLE_BOOKS_API_KEY="your-api-key-here"
```

### Issue 3: Seed CSV not found

**Error:**
```
[ERROR] Seed file not found: backend/data/seeds/entrepreneurship_2025_top100.csv
```

**Fix:**
```bash
# Copy example file
cp backend/data/seeds/entrepreneurship_2025_top100.example.csv \
   backend/data/seeds/entrepreneurship_2025_top100.csv

# Add more rows (96 more to reach 100)
```

### Issue 4: Database connection fails

**Error:**
```
RuntimeError: DATABASE_URL is not set
```

**Fix:**
```bash
# Create backend/.env
echo 'DATABASE_URL=postgresql://postgres:postgres@localhost:5432/readar' > backend/.env
```

### Issue 5: Books ingested but recommendations still 0

**Diagnosis:**

1. Check if backend and ingestion script use same DATABASE_URL:
   ```bash
   # Check backend
   uvicorn app.main:app --reload | grep DATABASE_URL

   # Check ingestion script uses same settings
   python -c "import sys; sys.path.append('backend'); from app.core.config import settings; print(settings.get_masked_database_url())"
   ```

2. Verify books exist in backend's DB:
   ```bash
   curl http://localhost:8000/api/books?limit=5
   ```

3. Check recommendation logs:
   ```bash
   # In backend logs, look for:
   [RECS_EMPTY] ... reason=no_catalog
   # or
   [RECS_EMPTY] ... reason=no_matches
   ```

**Fix:**
- If different DATABASE_URL: Ensure both read from `backend/.env`
- If `reason=no_matches`: Books exist but filters are too strict → add tags (see Step 8)

---

## Expected Behavior After Fix

### When books exist in catalog:

1. **GET /api/books?limit=5** → Returns books array with 5 items
2. **GET /api/recommendations?limit=5** → Returns recommendations array with 5 items
3. **GET /admin/catalog-stats** → Shows `books_count > 0`
4. **Frontend /recommendations** → Displays book cards (not empty state)

### When catalog is empty:

1. **GET /api/books?limit=5** → Returns empty array `[]`
2. **GET /api/recommendations?limit=5** → Returns `{"items": []}` + logs `[RECS_EMPTY] reason=no_catalog`
3. **Frontend /recommendations** → Shows "No recommendations yet" empty state

---

## Quick Verification Commands

**Run these in order to verify everything works:**

```bash
# 1. Check migration
cd backend && alembic upgrade head

# 2. Set API key
export GOOGLE_BOOKS_API_KEY="your-key"

# 3. Run ingestion (5 books for testing)
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2025_top100.example.csv \
  --limit 4 \
  --commit

# 4. Check books endpoint
curl http://localhost:8000/api/books?limit=5 | jq '.[] | {title, author_name}'

# 5. Check recommendations (requires auth token)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/recommendations?limit=5 | jq '.items | length'

# Expected output: 4 (or more if fallback to generic works)
```

---

## Files Modified

- `backend/app/routers/admin_debug.py` - Added `/admin/catalog-stats` endpoint
- `backend/scripts/ingest_catalog_from_seed.py` - Fixed import path (commit `bee7b26c`)

**Commit:** `66019391` - "Add /admin/catalog-stats diagnostic endpoint"
