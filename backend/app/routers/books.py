from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, asc, desc
from typing import Optional, List, Any
from uuid import UUID
import logging
from sqlalchemy import or_, and_
from typing import Optional
from app.database import get_db
from app.models import Book
from app.schemas.book import BookResponse, BookCreate
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=List[BookResponse])
def get_books(
    q: Optional[str] = Query(None, description="Search in title or author"),
    sort: str = Query("title", description="Sort field: title, author_name, published_year, page_count"),
    order: str = Query("asc", description="Sort order: asc or desc"),
    year_min: Optional[int] = Query(None, description="Minimum published year"),
    year_max: Optional[int] = Query(None, description="Maximum published year"),
    has_cover: Optional[bool] = Query(None, description="Filter by cover presence"),
    category: Optional[str] = Query(None, description="Filter by category"),
    stage: Optional[str] = Query(None, description="Filter by business stage tag"),
    limit: int = Query(100, ge=1, le=5000),
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
    try:
        query = db.query(Book)
        
        # Search query (q) - case-insensitive search against title and author_name
        if q:
            qq = f"%{q.strip()}%"
            query = query.filter(
                or_(
                    Book.title.ilike(qq),
                    Book.author_name.ilike(qq),
                )
            )
        
        # Year range filters
        if year_min is not None:
            query = query.filter(Book.published_year >= year_min)
        if year_max is not None:
            query = query.filter(Book.published_year <= year_max)
        
        # Cover presence filter
        if has_cover is True:
            query = query.filter(
                or_(
                    Book.cover_image_url.isnot(None),
                    Book.thumbnail_url.isnot(None),
                )
            )
        elif has_cover is False:
            query = query.filter(
                and_(
                    Book.cover_image_url.is_(None),
                    Book.thumbnail_url.is_(None),
                )
            )
        
        # Legacy filters (keep for backward compatibility)
        if category:
            query = query.filter(Book.categories.contains([category]))
        
        if stage:
            query = query.filter(Book.business_stage_tags.contains([stage]))
        
        # Sort with allowlist to prevent SQL injection
        sort_map = {
            "title": Book.title,
            "author_name": Book.author_name,
            "published_year": Book.published_year,
            "page_count": Book.page_count,
        }
        sort_col = sort_map.get(sort, Book.title)
        sort_fn = desc if order.lower() == "desc" else asc
        query = query.order_by(sort_fn(sort_col))
        
        books = query.offset(offset).limit(limit).all()
        
        # Convert to Pydantic models explicitly to ensure UUID serialization
        result: List[BookResponse] = []
        for book in books:
            try:
                # Ensure UUID is converted to string
                book_dict = {
                    "id": str(book.id),
                    "external_id": book.external_id,
                    "title": book.title,
                    "subtitle": book.subtitle,
                    "author_name": book.author_name,
                    "description": book.description,
                    "thumbnail_url": book.thumbnail_url,
                    "cover_image_url": book.cover_image_url,
                    "page_count": book.page_count,
                    "published_year": book.published_year,
                    "categories": book.categories,
                    "business_stage_tags": book.business_stage_tags,
                    "functional_tags": book.functional_tags,
                    "theme_tags": book.theme_tags,
                    "difficulty": book.difficulty,
                    "promise": book.promise,
                    "best_for": book.best_for,
                    "core_frameworks": book.core_frameworks,
                    "anti_patterns": book.anti_patterns,
                    "outcomes": book.outcomes,
                    "created_at": book.created_at,
                    "updated_at": book.updated_at,
                }
                result.append(BookResponse(**book_dict))
            except Exception as e:
                # Log individual book errors but continue processing
                logger.warning(f"Error serializing book {book.id} ({book.title}): {repr(e)}")
                continue
        
        logger.info(f"Fetched {len(result)} books", extra={
            "q": q,
            "sort": sort,
            "order": order,
            "year_min": year_min,
            "year_max": year_max,
            "has_cover": has_cover,
            "limit": limit,
            "offset": offset,
        })
        
        return result
    
    except Exception as e:
        logger.exception("Failed to fetch books", extra={
            "q": q,
            "sort": sort,
            "order": order,
            "year_min": year_min,
            "year_max": year_max,
            "has_cover": has_cover,
        })
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch books"
        )
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
    try:
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )
        
        # Ensure UUID is converted to string
        book_dict = {
            "id": str(book.id),
            "external_id": book.external_id,
            "title": book.title,
            "subtitle": book.subtitle,
            "author_name": book.author_name,
            "description": book.description,
            "thumbnail_url": book.thumbnail_url,
            "cover_image_url": book.cover_image_url,
            "page_count": book.page_count,
            "published_year": book.published_year,
            "categories": book.categories,
            "business_stage_tags": book.business_stage_tags,
            "functional_tags": book.functional_tags,
            "theme_tags": book.theme_tags,
            "difficulty": book.difficulty,
            "promise": book.promise,
            "best_for": book.best_for,
            "core_frameworks": book.core_frameworks,
            "anti_patterns": book.anti_patterns,
            "outcomes": book.outcomes,
            "created_at": book.created_at,
            "updated_at": book.updated_at,
        }
        return BookResponse(**book_dict)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch book: {repr(e)}"
        )
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

