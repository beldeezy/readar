"""Tests for recommendation engine stability and insight matching."""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.models import Book, OnboardingProfile, User, BusinessStage
from app.services.recommendation_engine import (
    score_promise_match,
    score_framework_match,
    score_outcome_match,
    ScoreFactors,
    W_STAGE,
    W_CHALLENGE,
    W_AREAS,
    W_MODEL,
    W_PROMISE,
    W_FRAMEWORK,
    W_OUTCOME,
)


@pytest.fixture
def sample_book(db: Session) -> Book:
    """Create a sample book with insight fields."""
    book = Book(
        id=uuid4(),
        title="Test Book",
        author_name="Test Author",
        description="A test book",
        promise="Helps you overcome sales challenges by providing proven strategies",
        core_frameworks=["Service Business Model", "Client Acquisition Framework"],
        outcomes=["Increased client acquisition", "Better sales conversion"],
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


@pytest.fixture
def sample_profile(db: Session, sample_user: User) -> OnboardingProfile:
    """Create a sample onboarding profile."""
    profile = OnboardingProfile(
        id=uuid4(),
        user_id=sample_user.id,
        full_name="Test User",
        business_model="service",
        business_stage=BusinessStage.EARLY_REVENUE,
        biggest_challenge="sales",
        vision_6_12_months="Increase client acquisition and improve sales conversion",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@pytest.fixture
def sample_user(db: Session) -> User:
    """Create a sample user."""
    from app.core.security import get_password_hash
    user = User(
        id=uuid4(),
        email="test@example.com",
        password_hash=get_password_hash("testpassword"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_promise_match_returns_positive_when_challenge_matches(sample_book, sample_profile):
    """Test that promise_match returns >0 when challenge matches book promise."""
    # Profile has "sales" challenge, book promise contains "sales challenges"
    result = score_promise_match(sample_book, sample_profile)
    assert result > 0.0
    assert result == 1.0


def test_promise_match_returns_zero_when_no_match(sample_book, sample_profile):
    """Test that promise_match returns 0 when challenge doesn't match."""
    sample_profile.biggest_challenge = "hiring"
    result = score_promise_match(sample_book, sample_profile)
    assert result == 0.0


def test_promise_match_returns_zero_when_missing_fields(sample_book, sample_profile):
    """Test that promise_match returns 0 when fields are missing."""
    sample_book.promise = None
    result = score_promise_match(sample_book, sample_profile)
    assert result == 0.0
    
    sample_book.promise = "Some promise"
    sample_profile.biggest_challenge = None
    result = score_promise_match(sample_book, sample_profile)
    assert result == 0.0


def test_framework_match_returns_positive_when_model_matches(sample_book, sample_profile):
    """Test that framework_match returns >0 when business model matches frameworks."""
    # Profile has "service" model, book has "Service Business Model" framework
    result = score_framework_match(sample_book, sample_profile)
    assert result > 0.0
    assert result == 1.0


def test_framework_match_returns_zero_when_no_match(sample_book, sample_profile):
    """Test that framework_match returns 0 when model doesn't match."""
    sample_profile.business_model = "saas"
    result = score_framework_match(sample_book, sample_profile)
    assert result == 0.0


def test_framework_match_returns_zero_when_missing_fields(sample_book, sample_profile):
    """Test that framework_match returns 0 when fields are missing."""
    sample_book.core_frameworks = None
    result = score_framework_match(sample_book, sample_profile)
    assert result == 0.0
    
    sample_book.core_frameworks = ["Some Framework"]
    sample_profile.business_model = None
    result = score_framework_match(sample_book, sample_profile)
    assert result == 0.0


def test_outcome_match_returns_positive_when_vision_matches(sample_book, sample_profile):
    """Test that outcome_match returns >0 when vision matches book outcomes."""
    # Profile vision contains "client acquisition", book outcome is "Increased client acquisition"
    result = score_outcome_match(sample_book, sample_profile)
    assert result > 0.0
    assert result == 1.0


def test_outcome_match_returns_zero_when_no_match(sample_book, sample_profile):
    """Test that outcome_match returns 0 when vision doesn't match."""
    sample_profile.vision_6_12_months = "Build a team and hire employees"
    result = score_outcome_match(sample_book, sample_profile)
    assert result == 0.0


def test_outcome_match_returns_zero_when_missing_fields(sample_book, sample_profile):
    """Test that outcome_match returns 0 when fields are missing."""
    sample_book.outcomes = None
    result = score_outcome_match(sample_book, sample_profile)
    assert result == 0.0
    
    sample_book.outcomes = ["Some outcome"]
    sample_profile.vision_6_12_months = None
    result = score_outcome_match(sample_book, sample_profile)
    assert result == 0.0


def test_score_factors_includes_insight_matches(sample_book, sample_profile):
    """Test that ScoreFactors includes the new insight match fields."""
    factors = ScoreFactors()
    assert hasattr(factors, "promise_match")
    assert hasattr(factors, "framework_match")
    assert hasattr(factors, "outcome_match")
    assert factors.promise_match == 0.0
    assert factors.framework_match == 0.0
    assert factors.outcome_match == 0.0


def test_total_score_increases_with_insight_matches(sample_book, sample_profile):
    """Test that total score increases when insight fields match."""
    from app.services.recommendation_engine import _score_from_stage_fit
    
    # Calculate score with matching insights
    user_ctx = {
        "business_stage": "early-revenue",
        "business_model": "service",
        "biggest_challenge": "sales",
        "areas_of_business": [],
    }
    score_with_match, factors_with_match = _score_from_stage_fit(
        user_ctx, sample_book, sample_profile
    )
    
    # Verify insight matches are set
    assert factors_with_match.promise_match > 0.0
    assert factors_with_match.framework_match > 0.0
    assert factors_with_match.outcome_match > 0.0
    
    # Verify score includes weighted insight contributions
    expected_insight_contribution = (
        W_PROMISE * factors_with_match.promise_match +
        W_FRAMEWORK * factors_with_match.framework_match +
        W_OUTCOME * factors_with_match.outcome_match
    )
    assert expected_insight_contribution > 0.0
    
    # Create a book without matching insights
    sample_book_no_match = Book(
        id=uuid4(),
        title="No Match Book",
        author_name="Test Author",
        description="A test book",
        promise="Helps with something else",
        core_frameworks=["Different Framework"],
        outcomes=["Different outcome"],
    )
    
    score_no_match, factors_no_match = _score_from_stage_fit(
        user_ctx, sample_book_no_match, sample_profile
    )
    
    # Score with matches should be higher
    assert score_with_match > score_no_match


def test_weights_are_defined():
    """Test that all required weights are defined."""
    assert W_STAGE == 1.2
    assert W_CHALLENGE == 1.4
    assert W_AREAS == 1.0
    assert W_MODEL == 0.8
    assert W_PROMISE == 1.2
    assert W_FRAMEWORK == 0.6
    assert W_OUTCOME == 0.6

