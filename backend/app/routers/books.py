from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional
from app.database import get_db
from app.models import Book
from app.schemas.book import BookResponse, BookCreate
from app.core.config import settings

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=list[BookResponse])
def get_books(
    search: Optional[str] = Query(None, description="Search in title, author, or description"),
    category: Optional[str] = Query(None, description="Filter by category"),
    stage: Optional[str] = Query(None, description="Filter by business stage tag"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get paginated list of books with optional filters."""
    query = db.query(Book)
    
    if search:
        search_term = f"%{search.lower()}%"
        query = query.filter(
            or_(
                Book.title.ilike(search_term),
                Book.author_name.ilike(search_term),
                Book.description.ilike(search_term)
            )
        )
    
    if category:
        query = query.filter(Book.categories.contains([category]))
    
    if stage:
        query = query.filter(Book.business_stage_tags.contains([stage]))
    
    books = query.offset(offset).limit(limit).all()
    return books


@router.get("/{book_id}", response_model=BookResponse)
def get_book(book_id: str, db: Session = Depends(get_db)):
    """Get full details of a specific book."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )
    return book


@router.post("/seed/debug", status_code=status.HTTP_201_CREATED)
def seed_books_debug(db: Session = Depends(get_db)):
    """DEV ONLY: Seed books from JSON file."""
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is disabled in production",
        )
    
    import json
    import os
    from pathlib import Path
    
    # Load seed data
    seed_file = Path(__file__).parent.parent / "data" / "books_seed.json"
    if not seed_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seed file not found",
        )
    
    with open(seed_file, "r") as f:
        books_data = json.load(f)
    
    created_count = 0
    for book_data in books_data:
        # Check if book already exists by title + author
        existing = db.query(Book).filter(
            Book.title == book_data["title"],
            Book.author_name == book_data["author_name"]
        ).first()
        
        if not existing:
            new_book = Book(**book_data)
            db.add(new_book)
            created_count += 1
    
    db.commit()
    return {"message": f"Seeded {created_count} new books"}

