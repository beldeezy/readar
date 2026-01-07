# app/routers/reading_history.py
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from io import TextIOWrapper
import csv
import logging
from app.database import get_db
from app.core.auth import get_current_user
from app.models import User, Book, PendingBook
from app.utils.email import send_weekly_pending_books_email
from sqlalchemy import or_
import sqlalchemy as sa

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reading-history", tags=["reading_history"])


@router.post("/upload-csv")
async def upload_reading_history_csv(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a Goodreads CSV file to import reading history.

    - Extracts book metadata from CSV
    - Checks if books exist in catalog (deduplication)
    - Adds new books to pending_books table
    - Returns counts of imported/skipped/new books
    """
    # Simple filename check - more forgiving than content-type
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a .csv file exported from Goodreads."
        )

    logger.info(f"Processing CSV upload for user_id={user.id}, filename={file.filename}")

    # Try to read and parse the CSV file
    try:
        text_stream = TextIOWrapper(file.file, encoding="utf-8")
        reader = csv.DictReader(text_stream)
        logger.info(f"CSV file opened successfully, reading rows...")
    except Exception as e:
        logger.exception("Failed to read uploaded CSV: %s", e)
        raise HTTPException(
            status_code=400,
            detail="Could not read CSV file. Make sure you exported it from Goodreads."
        )

    imported = 0
    skipped = 0
    new_books_added = 0

    # Parse rows and extract book metadata
    try:
        for row in reader:
            title = (row.get("Title") or "").strip()
            author = (row.get("Author") or "").strip()

            if not title or not author:
                skipped += 1
                continue

            # Extract additional metadata from Goodreads CSV
            isbn = (row.get("ISBN") or "").strip() or None
            isbn13 = (row.get("ISBN13") or "").strip() or None
            goodreads_id = (row.get("Book Id") or "").strip() or None
            year_str = (row.get("Year Published") or "").strip()
            rating_str = (row.get("Average Rating") or "").strip()
            pages_str = (row.get("Number of Pages") or "").strip()

            # Parse numeric fields
            year_published = None
            if year_str:
                try:
                    year_published = int(year_str)
                except ValueError:
                    pass

            average_rating = None
            if rating_str:
                try:
                    average_rating = float(rating_str)
                except ValueError:
                    pass

            num_pages = None
            if pages_str:
                try:
                    num_pages = int(pages_str)
                except ValueError:
                    pass

            # Check if book already exists in catalog
            # Match by ISBN, ISBN13, or title+author
            existing_book = db.query(Book).filter(
                or_(
                    Book.isbn_10 == isbn if isbn else False,
                    Book.isbn_13 == isbn13 if isbn13 else False,
                    sa.and_(
                        sa.func.lower(Book.title) == title.lower(),
                        sa.func.lower(Book.author_name) == author.lower()
                    )
                )
            ).first()

            if existing_book:
                # Book already in catalog
                imported += 1
                continue

            # Check if already in pending_books (dedupe within pending)
            existing_pending = db.query(PendingBook).filter(
                or_(
                    PendingBook.isbn == isbn if isbn else False,
                    PendingBook.isbn13 == isbn13 if isbn13 else False,
                    sa.and_(
                        sa.func.lower(PendingBook.title) == title.lower(),
                        sa.func.lower(PendingBook.author) == author.lower()
                    )
                )
            ).first()

            if existing_pending:
                # Already in pending queue
                imported += 1
                continue

            # Add to pending_books table
            pending_book = PendingBook(
                title=title,
                author=author,
                isbn=isbn,
                isbn13=isbn13,
                goodreads_id=goodreads_id,
                goodreads_url=f"https://www.goodreads.com/book/show/{goodreads_id}" if goodreads_id else None,
                year_published=year_published,
                average_rating=average_rating,
                num_pages=num_pages,
            )
            db.add(pending_book)
            new_books_added += 1
            imported += 1

    except Exception as e:
        logger.exception("Error while parsing Goodreads CSV row: %s", e)
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Error while processing Goodreads CSV: {e}"
        )

    # Commit all new pending books
    try:
        db.commit()
        logger.info(
            f"CSV import complete: {imported} total books, {new_books_added} new books added to queue, "
            f"{skipped} skipped rows for user_id={user.id}"
        )
    except Exception as e:
        logger.exception("Failed to commit pending books: %s", e)
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to save new books"
        )

    return {
        "imported_count": imported,
        "skipped_count": skipped,
        "new_books_added": new_books_added,
    }


@router.post("/weekly-report")
async def send_weekly_report(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Send weekly email report of new books added to pending queue.

    This endpoint can be called manually or by a cron job/scheduler.
    Sends report to michael@readar.ai with all new books from the past 7 days.

    Note: Email sending is currently logged only. Configure SMTP settings to enable actual emails.
    """
    # Optional: Add admin check if you want to restrict this endpoint
    # For now, any authenticated user can trigger the report

    logger.info(f"Weekly report triggered by user_id={user.id}")

    result = send_weekly_pending_books_email(db, recipient="michael@readar.ai")

    return result
