# Readar Catalog Expansion Guide

This guide explains how to automatically discover and add new books to your Readar catalog using the Amazon Best Sellers scraper.

## Quick Start

### Option 1: Automated Workflow (Recommended)

Use the all-in-one workflow script:

```bash
# Interactive mode (with manual review)
./backend/scripts/catalog_expansion_workflow.sh

# Specify category and limit
./backend/scripts/catalog_expansion_workflow.sh --category small-business --limit 30

# Auto-approve (skip manual review)
./backend/scripts/catalog_expansion_workflow.sh --auto-approve --limit 25

# Fetch ISBNs (slower but more accurate)
./backend/scripts/catalog_expansion_workflow.sh --fetch-isbn --limit 20
```

### Option 2: Manual Step-by-Step

If you prefer more control, run each step manually:

```bash
# Step 1: Discover books
python -m backend.scripts.discover_amazon_books \
  --category entrepreneurship \
  --limit 50 \
  --check-duplicates

# Step 2: Review the CSV
# Edit: backend/data/pending_review/pending_review_amazon_entrepreneurship_YYYYMMDD_HHMMSS.csv

# Step 3: Ingest approved books
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/pending_review/pending_review_amazon_entrepreneurship_YYYYMMDD_HHMMSS.csv \
  --commit
```

---

## Discovery Script Options

### Basic Usage

```bash
python -m backend.scripts.discover_amazon_books [OPTIONS]
```

### Available Options

| Option | Description | Default |
|--------|-------------|---------|
| `--category` | Amazon category to scrape | `entrepreneurship` |
| `--limit` | Max books to discover | `50` |
| `--fetch-isbn` | Fetch ISBN from product pages (slower) | `false` |
| `--check-duplicates` | Check against existing catalog | `false` |
| `--delay` | Delay between requests (seconds) | `1.0` |
| `--output-dir` | Output directory for CSV | `backend/data/pending_review` |

### Available Categories

- `entrepreneurship` - Entrepreneurship books
- `small-business` - Small business books
- `business` - General business books
- `startups` - Startup/entrepreneurship (Kindle)

### Examples

```bash
# Discover 25 entrepreneurship books (fast, no ISBN)
python -m backend.scripts.discover_amazon_books \
  --category entrepreneurship \
  --limit 25

# Discover with ISBN and deduplication (recommended)
python -m backend.scripts.discover_amazon_books \
  --category entrepreneurship \
  --limit 50 \
  --fetch-isbn \
  --check-duplicates

# Discover from small business category
python -m backend.scripts.discover_amazon_books \
  --category small-business \
  --limit 30 \
  --check-duplicates

# Fast discovery without ISBN (for large batches)
python -m backend.scripts.discover_amazon_books \
  --category business \
  --limit 100 \
  --check-duplicates
```

---

## Review Workflow

### 1. Discovery Phase

The scraper creates a CSV file in `backend/data/pending_review/`:

```
pending_review_amazon_entrepreneurship_20260215_140530.csv
```

### 2. Review Phase

Open the CSV and review each book:

**What to look for:**
- ✅ Keep: Business/entrepreneurship books relevant to your audience
- ❌ Remove: Off-topic books (fiction, self-help not related to business, etc.)
- ❌ Remove: Low-quality or spam books
- ❌ Remove: Books already in catalog (if not using `--check-duplicates`)

**CSV Format:**
```csv
title,author,source_name,source_year,source_rank,source_category,isbn13,source_url
Traction,Gino Wickman,amazon,2026,1,entrepreneurship,9781936661824,https://amazon.com/...
```

### 3. Ingestion Phase

Once reviewed, ingest the approved books:

```bash
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/pending_review/pending_review_amazon_entrepreneurship_20260215_140530.csv \
  --commit \
  --resume
```

**Ingestion flags:**
- `--commit`: Actually write to database (omit for dry-run)
- `--resume`: Skip rows already in book_sources (safe for re-runs)
- `--skip-existing-books`: Only add sources, don't update existing books
- `--confidence-threshold 75`: Require higher match confidence (default: 65)

---

## Scheduled Automation

### Daily Discovery (with Review)

Add to crontab for daily discovery at 2 AM:

```bash
# Edit crontab
crontab -e

# Add this line:
0 2 * * * cd /home/user/readar && ./backend/scripts/catalog_expansion_workflow.sh --category entrepreneurship --limit 25 >> /var/log/readar_discovery.log 2>&1
```

### Weekly Batch Discovery

Discover from multiple categories on Sundays at 3 AM:

```bash
# Entrepreneurship
0 3 * * 0 cd /home/user/readar && ./backend/scripts/catalog_expansion_workflow.sh --category entrepreneurship --limit 50

# Small Business
30 3 * * 0 cd /home/user/readar && ./backend/scripts/catalog_expansion_workflow.sh --category small-business --limit 30
```

### Email Notifications (Optional)

Get notified when new books are discovered:

```bash
#!/bin/bash
# catalog_discovery_with_email.sh

RESULT=$(./backend/scripts/catalog_expansion_workflow.sh --category entrepreneurship --limit 25)

if echo "$RESULT" | grep -q "Books discovered: [1-9]"; then
  echo "$RESULT" | mail -s "Readar: New Books Discovered" you@example.com
fi
```

---

## Deduplication

The script uses multiple methods to detect duplicates:

### 1. ISBN-13 Matching (Most Reliable)
- Exact match on ISBN-13
- Only works if `--fetch-isbn` is enabled

### 2. Title + Author Matching
- Normalizes title and author (lowercase, removes punctuation)
- Fuzzy matching using first 3 title words + first 2 author words
- Creates a "work key": `normalized_title::normalized_author`

### Example Work Keys:
```
"traction get a grip on your business::gino wickman"
"lean startup how todays entrepreneurs::eric ries"
```

### Enable Deduplication

```bash
# Check against existing catalog
python -m backend.scripts.discover_amazon_books \
  --category entrepreneurship \
  --limit 50 \
  --check-duplicates
```

**Note:** Requires database access. If database is unavailable, deduplication is skipped.

---

## Rate Limiting & Best Practices

### Scraping Etiquette

The scraper includes rate limiting to be respectful to Amazon's servers:

- **Default delay:** 1 second between requests
- **User-Agent:** Identifies as a standard browser
- **Timeout:** 15 seconds per request
- **Error handling:** Gracefully handles failures

### Adjust Rate Limiting

```bash
# Slower (more respectful)
python -m backend.scripts.discover_amazon_books \
  --category entrepreneurship \
  --limit 50 \
  --delay 2.0

# Faster (use sparingly)
python -m backend.scripts.discover_amazon_books \
  --category entrepreneurship \
  --limit 50 \
  --delay 0.5
```

### Recommendations

- ✅ Run during off-peak hours (late night/early morning)
- ✅ Use `--check-duplicates` to avoid re-discovering books
- ✅ Start with small limits (25-50) and increase gradually
- ✅ Use `--fetch-isbn` for better quality (but slower)
- ❌ Don't run multiple scrapers simultaneously
- ❌ Don't set delay below 0.5 seconds

---

## Troubleshooting

### "No module named 'requests'"

Install dependencies:

```bash
cd backend
pip install requests beautifulsoup4
```

### "Database not available"

Deduplication check requires database access. Either:

1. Ensure database is running
2. Run without `--check-duplicates`
3. Manually deduplicate during review phase

### "Failed to fetch best sellers page"

Amazon may be blocking requests. Try:

1. Increase delay: `--delay 2.0`
2. Wait a few hours and retry
3. Check if Amazon changed their HTML structure

### "No ISBN found"

Some books don't have ISBN-13 on Amazon. This is normal. The scraper will:

1. Leave `isbn13` field empty
2. Continue with title/author matching
3. Google Books API will attempt to find ISBN during ingestion

### Books Not Showing in Catalog

Check the ingestion report:

```bash
ls -lt backend/data/ingestion_reports/
cat backend/data/ingestion_reports/ingestion_report_YYYYMMDD_HHMMSS.csv
```

Look for:
- Low match scores (increase `--confidence-threshold`)
- Failed Google Books API matches
- Duplicate detections

---

## Directory Structure

```
backend/
├── data/
│   ├── pending_review/           # Discovered books awaiting review
│   │   ├── pending_review_amazon_entrepreneurship_20260215_140530.csv
│   │   └── archived/             # Ingested books (moved after ingestion)
│   ├── ingestion_reports/        # Match confidence reports
│   │   └── ingestion_report_20260215_140600.csv
│   └── seeds/                    # Approved seed files
│       └── entrepreneurship_2026_top100.csv
└── scripts/
    ├── discover_amazon_books.py  # Discovery scraper
    ├── ingest_catalog_from_seed.py  # Ingestion script
    └── catalog_expansion_workflow.sh  # Automated workflow
```

---

## Advanced Usage

### Multiple Categories in Parallel

```bash
# Discover from multiple categories
python -m backend.scripts.discover_amazon_books --category entrepreneurship --limit 50 --check-duplicates &
python -m backend.scripts.discover_amazon_books --category small-business --limit 30 --check-duplicates &
python -m backend.scripts.discover_amazon_books --category startups --limit 25 --check-duplicates &

wait  # Wait for all to complete
```

**Note:** Use with caution and respect rate limits.

### Custom Filters

Edit the pending review CSV to add custom filters:

```bash
# Keep only books with ISBN
awk -F',' 'NR==1 || $7!=""' pending_review.csv > filtered.csv

# Keep only books ranked 1-25
awk -F',' 'NR==1 || $6<=25' pending_review.csv > top25.csv

# Remove specific authors
grep -v "Author Name" pending_review.csv > filtered.csv
```

### Combine with Existing Seeds

Merge discovered books with existing seed:

```bash
# Remove header from discovered books
tail -n +2 pending_review_amazon_entrepreneurship_20260215.csv >> backend/data/seeds/entrepreneurship_2026_top100.csv

# Ingest the combined file
python -m backend.scripts.ingest_catalog_from_seed \
  --seed backend/data/seeds/entrepreneurship_2026_top100.csv \
  --commit \
  --resume
```

---

## Next Steps

1. **Test the scraper:**
   ```bash
   python -m backend.scripts.discover_amazon_books --limit 5
   ```

2. **Review the output:**
   ```bash
   cat backend/data/pending_review/pending_review_amazon_entrepreneurship_*.csv
   ```

3. **Run the full workflow:**
   ```bash
   ./backend/scripts/catalog_expansion_workflow.sh --limit 25
   ```

4. **Schedule automation:**
   ```bash
   crontab -e
   # Add daily discovery job
   ```

5. **Monitor catalog health:**
   - Check `/admin/catalog-stats` endpoint
   - Review ingestion reports regularly
   - Track catalog growth over time

---

## FAQ

**Q: How often should I run the scraper?**
A: Daily or weekly is recommended. Amazon's best sellers update frequently.

**Q: Should I use `--fetch-isbn`?**
A: Yes for quality, no for speed. ISBN improves deduplication and Google Books matching.

**Q: What if Amazon changes their HTML?**
A: The scraper may need updates. File an issue with the error message.

**Q: Can I add books from other sources?**
A: Yes! Create a CSV with the same format and run the ingestion script.

**Q: How do I remove books from the catalog?**
A: Use the admin interface or manually delete from the database (use with caution).

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review ingestion reports for detailed errors
3. Check server logs for scraper errors
4. File an issue with the error message and steps to reproduce

---

**Happy catalog expanding! 📚**
