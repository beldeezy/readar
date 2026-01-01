"""Integration test for recommendations endpoint with user, onboarding, and ratings."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4
from app.models import (
    User,
    OnboardingProfile,
    Book,
    UserBookInteraction,
    UserBookStatus,
    BusinessStage,
)
from app.core.user_helpers import get_or_create_user_by_auth_id
from app.main import app
from app.core.auth import get_current_user


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user with auth_user_id for Supabase-style auth."""
    auth_user_id = str(uuid4())
    user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=auth_user_id,
        email="test@example.com",
    )
    return user


@pytest.fixture
def test_books(db: Session) -> list[Book]:
    """Create 5 test books for recommendations."""
    books = []
    for i in range(5):
        book = Book(
            id=uuid4(),
            title=f"Test Book {i+1}",
            author_name=f"Author {i+1}",
            description=f"Description for book {i+1}",
            business_stage_tags=["early-revenue", "scaling"],
            theme_tags=["sales", "marketing"],
            functional_tags=["strategy", "tactics"],
        )
        db.add(book)
        books.append(book)
    db.commit()
    for book in books:
        db.refresh(book)
    return books


@pytest.fixture
def test_onboarding_profile(db: Session, test_user: User) -> OnboardingProfile:
    """Create an onboarding profile for the test user."""
    profile = OnboardingProfile(
        id=uuid4(),
        user_id=test_user.id,
        full_name="Test User",
        business_model="service",
        business_stage=BusinessStage.EARLY_REVENUE,
        biggest_challenge="sales",
        industry="software",
        economic_sector="technology",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@pytest.fixture
def test_ratings(
    db: Session, test_user: User, test_books: list[Book]
) -> list[UserBookInteraction]:
    """Create 4 book ratings/interactions for the test user."""
    ratings = []
    statuses = [
        UserBookStatus.READ_LIKED,
        UserBookStatus.READ_LIKED,
        UserBookStatus.INTERESTED,
        UserBookStatus.INTERESTED,
    ]
    
    # Use first 4 books
    for i, book in enumerate(test_books[:4]):
        interaction = UserBookInteraction(
            id=uuid4(),
            user_id=test_user.id,
            book_id=book.id,
            status=statuses[i],
        )
        db.add(interaction)
        ratings.append(interaction)
    
    db.commit()
    for rating in ratings:
        db.refresh(rating)
    return ratings


def test_recommendations_with_user_onboarding_and_ratings(
    db: Session,
    test_user: User,
    test_books: list[Book],
    test_onboarding_profile: OnboardingProfile,
    test_ratings: list[UserBookInteraction],
):
    """Test that recommendations endpoint returns >=1 item when user has onboarding + 4 ratings."""
    # Override get_current_user dependency
    app.dependency_overrides[get_current_user] = lambda: test_user
    
    try:
        client = TestClient(app)
        
        # Call recommendations endpoint
        response = client.get("/api/recommendations?limit=5")
        
        # Should succeed
        assert response.status_code == 200, f"Response: {response.text}"
        
        # Parse response
        data = response.json()
        assert "items" in data
        assert "request_id" in data
        
        # Assert we get at least 1 recommendation
        items = data["items"]
        assert len(items) >= 1, (
            f"Expected at least 1 recommendation, got {len(items)}. "
            f"User has {len(test_ratings)} ratings and onboarding profile. "
            f"Response: {response.text}"
        )
        
        # Verify each item has required fields
        for item in items:
            assert "book_id" in item
            assert "title" in item
            assert "score" in item
            assert "relevancy_score" in item
            assert "why_this_book" in item
        
    finally:
        app.dependency_overrides.clear()


def test_recommendations_empty_with_debug_info(
    db: Session,
    test_user: User,
):
    """Test that recommendations endpoint returns debug info when empty (with READAR_RECS_DEBUG)."""
    import os
    
    # Override get_current_user dependency
    app.dependency_overrides[get_current_user] = lambda: test_user
    
    # Set READAR_RECS_DEBUG env var
    original_value = os.environ.get("READAR_RECS_DEBUG")
    os.environ["READAR_RECS_DEBUG"] = "true"
    
    try:
        client = TestClient(app)
        
        # Call recommendations endpoint (may be empty if no books in catalog, or may have generic recommendations)
        response = client.get("/api/recommendations?limit=5")
        
        # Should succeed
        assert response.status_code == 200, f"Response: {response.text}"
        
        # Parse response
        data = response.json()
        assert "items" in data
        items = data["items"]
        
        # If empty, should have debug info (gated by READAR_RECS_DEBUG)
        if len(items) == 0:
            assert "debug" in data, (
                "Expected debug info when recommendations are empty and READAR_RECS_DEBUG=true. "
                f"Response: {response.text}"
            )
            debug = data["debug"]
            assert "user_id" in debug
            assert "signal_counts" in debug
            assert "gates" in debug
            assert "reason" in debug
            
            # Verify signal_counts structure
            signal_counts = debug["signal_counts"]
            assert "onboarding_profile" in signal_counts
            assert "book_ratings" in signal_counts
            assert "reading_history_entries" in signal_counts
            
            # Verify gates structure
            gates = debug["gates"]
            assert "min_ratings_required" in gates
            assert "min_history_required" in gates
            assert "signal_threshold" in gates
            
            # Verify reason is a valid string
            assert isinstance(debug["reason"], str)
            assert debug["reason"] in ["no_catalog", "no_signal", "cold_start_no_interactions", "no_matches", "unknown"]
            
    finally:
        app.dependency_overrides.clear()
        # Restore original env var value
        if original_value is not None:
            os.environ["READAR_RECS_DEBUG"] = original_value
        elif "READAR_RECS_DEBUG" in os.environ:
            del os.environ["READAR_RECS_DEBUG"]

