from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserBookInteraction, Book
from app.schemas.user_book import UserBookInteractionCreate, UserBookInteractionResponse
from app.core.auth import get_current_user
from app.core.user_helpers import get_or_create_user_by_auth_id
from datetime import datetime
import uuid

router = APIRouter(prefix="/user-books", tags=["user-books"])


@router.post("", response_model=UserBookInteractionResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_user_book(
    interaction_data: UserBookInteractionCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create or update user-book interaction."""
    # Get or create local user from Supabase auth_user_id
    user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=current_user["auth_user_id"],
        email=current_user.get("email", ""),
    )
    
    # Verify book exists
    book = db.query(Book).filter(Book.id == interaction_data.book_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )
    
    # Check if interaction already exists
    existing = db.query(UserBookInteraction).filter(
        UserBookInteraction.user_id == user.id,
        UserBookInteraction.book_id == interaction_data.book_id
    ).first()
    
    if existing:
        # Update existing
        existing.status = interaction_data.status
        existing.rating = interaction_data.rating
        existing.notes = interaction_data.notes
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Create new
        new_interaction = UserBookInteraction(
            user_id=user.id,
            book_id=interaction_data.book_id,
            status=interaction_data.status,
            rating=interaction_data.rating,
            notes=interaction_data.notes
        )
        db.add(new_interaction)
        db.commit()
        db.refresh(new_interaction)
        return new_interaction


@router.get("", response_model=list[UserBookInteractionResponse])
async def get_user_books(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all user-book interactions for the current user."""
    # Get or create local user from Supabase auth_user_id
    user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=current_user["auth_user_id"],
        email=current_user.get("email", ""),
    )
    
    interactions = db.query(UserBookInteraction).filter(
        UserBookInteraction.user_id == user.id
    ).all()
    return interactions


@router.get("/{book_id}", response_model=UserBookInteractionResponse)
async def get_user_book(
    book_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user-book interaction for a specific book."""
    # Get or create local user from Supabase auth_user_id
    user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=current_user["auth_user_id"],
        email=current_user.get("email", ""),
    )
    
    interaction = db.query(UserBookInteraction).filter(
        UserBookInteraction.user_id == user.id,
        UserBookInteraction.book_id == book_id
    ).first()
    
    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interaction not found",
        )
    
    return interaction

