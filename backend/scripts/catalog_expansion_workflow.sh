#!/bin/bash
# Automated catalog expansion workflow
#
# This script automates the book discovery and ingestion process:
# 1. Discover new books from Amazon Best Sellers
# 2. Present them for manual review
# 3. Ingest approved books into the catalog
#
# Usage:
#   ./catalog_expansion_workflow.sh [--auto-approve] [--category entrepreneurship] [--limit 50]

set -e

# Default values
CATEGORY="entrepreneurship"
LIMIT=50
AUTO_APPROVE=false
FETCH_ISBN=false
CHECK_DUPLICATES=true

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --auto-approve)
      AUTO_APPROVE=true
      shift
      ;;
    --category)
      CATEGORY="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --fetch-isbn)
      FETCH_ISBN=true
      shift
      ;;
    --no-duplicate-check)
      CHECK_DUPLICATES=false
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

echo "========================================="
echo "Readar Catalog Expansion Workflow"
echo "========================================="
echo "Category: $CATEGORY"
echo "Limit: $LIMIT"
echo "Fetch ISBN: $FETCH_ISBN"
echo "Check duplicates: $CHECK_DUPLICATES"
echo "Auto-approve: $AUTO_APPROVE"
echo ""

# Step 1: Discover new books
echo "Step 1: Discovering books from Amazon..."
echo "-----------------------------------------"

DISCOVER_CMD="python -m backend.scripts.discover_amazon_books --category $CATEGORY --limit $LIMIT"

if [ "$FETCH_ISBN" = true ]; then
  DISCOVER_CMD="$DISCOVER_CMD --fetch-isbn"
fi

if [ "$CHECK_DUPLICATES" = true ]; then
  DISCOVER_CMD="$DISCOVER_CMD --check-duplicates"
fi

$DISCOVER_CMD

# Find the most recent pending review file
PENDING_FILE=$(ls -t backend/data/pending_review/pending_review_amazon_${CATEGORY}_*.csv 2>/dev/null | head -1)

if [ -z "$PENDING_FILE" ]; then
  echo "Error: No pending review file found"
  exit 1
fi

echo ""
echo "Pending review file: $PENDING_FILE"
echo ""

# Count books in pending file
BOOK_COUNT=$(tail -n +2 "$PENDING_FILE" | wc -l)
echo "Books discovered: $BOOK_COUNT"

if [ "$BOOK_COUNT" -eq 0 ]; then
  echo "No new books to add. Exiting."
  exit 0
fi

# Step 2: Manual review (unless auto-approve)
if [ "$AUTO_APPROVE" = false ]; then
  echo ""
  echo "Step 2: Manual Review"
  echo "---------------------"
  echo "Please review the file: $PENDING_FILE"
  echo ""
  echo "Remove any books that are:"
  echo "  - Off-topic (not business/entrepreneurship)"
  echo "  - Low-quality"
  echo "  - Duplicates"
  echo ""
  read -p "Press ENTER when you've finished reviewing, or Ctrl+C to cancel..."

  # Recount after review
  BOOK_COUNT=$(tail -n +2 "$PENDING_FILE" | wc -l)
  echo "Books after review: $BOOK_COUNT"
fi

# Step 3: Ingest into catalog
echo ""
echo "Step 3: Ingesting into catalog..."
echo "----------------------------------"

python -m backend.scripts.ingest_catalog_from_seed \
  --seed "$PENDING_FILE" \
  --commit \
  --resume \
  --report-dir backend/data/ingestion_reports

# Step 4: Archive the pending file
ARCHIVE_DIR="backend/data/pending_review/archived"
mkdir -p "$ARCHIVE_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_FILE="${ARCHIVE_DIR}/ingested_${TIMESTAMP}_$(basename $PENDING_FILE)"

mv "$PENDING_FILE" "$ARCHIVE_FILE"
echo ""
echo "Archived to: $ARCHIVE_FILE"

# Step 5: Summary
echo ""
echo "========================================="
echo "Catalog Expansion Complete"
echo "========================================="
echo "Books ingested: $BOOK_COUNT"
echo "Category: $CATEGORY"
echo ""
echo "Check ingestion report in: backend/data/ingestion_reports/"
echo ""
