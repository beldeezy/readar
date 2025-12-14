# app/routers/reading_history.py
from uuid import UUID
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query
from sqlalchemy.orm import Session
from io import TextIOWrapper
import csv
import logging
from app.database import get_db
# from app import models  # TEMP: commented out since we're not writing to DB
# from app.core.security import get_password_hash  # TEMP: commented out since we're not creating users

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reading-history", tags=["reading_history"])


@router.post("/upload-csv")
async def upload_reading_history_csv(
    user_id: UUID = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a Goodreads CSV file to import reading history.
    
    Accepts user_id as query parameter and a CSV file.
    Returns count of imported and skipped entries.
    
    TODO: Once auth & users are stable, re-enable writing reading history to the DB.
    For now, this endpoint only validates and counts rows without persisting to the database.
    """
    # TEMP: disable auto-creating placeholder User during CSV upload.
    # user = db.query(models.User).filter(models.User.id == user_id).one_or_none()
    # if user is None:
    #     # Create a minimal placeholder user that satisfies all NOT NULL constraints
    #     placeholder_email = f"dev+{user_id}@readar.local"
    #     # Generate a placeholder password hash (required field)
    #     placeholder_password_hash = get_password_hash(f"placeholder_{user_id}")
    #     
    #     user = models.User(
    #         id=user_id,
    #         email=placeholder_email,
    #         password_hash=placeholder_password_hash,
    #         # created_at, updated_at, and subscription_status have defaults, so we can omit them
    #     )
    #     db.add(user)
    #     db.flush()  # Ensure user gets written before using the FK
    #     logger.info(f"Auto-created placeholder user for user_id={user_id}, email={placeholder_email}")
    
    # Simple filename check - more forgiving than content-type
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a .csv file exported from Goodreads."
        )
    
    logger.info(f"Processing CSV upload for user_id={user_id}, filename={file.filename}")

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

    # Parse rows with error handling - counting only, no DB writes
    try:
        for row in reader:
            title = (row.get("Title") or "").strip()
            
            if not title:
                skipped += 1
                continue

            # We're not persisting yet — just counting.
            imported += 1

    except Exception as e:
        logger.exception("Error while parsing Goodreads CSV row: %s", e)
        raise HTTPException(
            status_code=400,
            detail=f"Error while processing Goodreads CSV: {e}"
        )

    # IMPORTANT: no db.commit() here for now.
    logger.info(f"CSV validation complete: {imported} valid rows, {skipped} skipped rows for user_id={user_id}")
    return {"imported_count": imported, "skipped_count": skipped}

