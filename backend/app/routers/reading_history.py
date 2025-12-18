# app/routers/reading_history.py
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from io import TextIOWrapper
import csv
import logging
from app.database import get_db
from app.core.auth import get_current_user
from app.core.user_helpers import get_or_create_user_by_auth_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reading-history", tags=["reading_history"])


@router.post("/upload-csv")
async def upload_reading_history_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a Goodreads CSV file to import reading history.
    
    Returns count of imported and skipped entries.
    
    TODO: Re-enable writing reading history to the DB once schema is finalized.
    For now, this endpoint only validates and counts rows without persisting to the database.
    """
    # Get or create local user from Supabase auth_user_id
    user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=current_user["auth_user_id"],
        email=current_user.get("email", ""),
    )
    
    # Simple filename check - more forgiving than content-type
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a .csv file exported from Goodreads."
        )
    
    logger.info(f"Processing CSV upload for user_id={user.id} (auth_user_id={current_user['auth_user_id']}), filename={file.filename}")

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
    logger.info(f"CSV validation complete: {imported} valid rows, {skipped} skipped rows for user_id={user.id}")
    return {"imported_count": imported, "skipped_count": skipped}

