"""Tests for onboarding normalization function and endpoint."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4
from app.models import BusinessStage, User, OnboardingProfile
from app.routers.onboarding import normalize_business_stage
from app.core.user_helpers import get_or_create_user_by_auth_id
from app.main import app
from app.core.auth import get_current_user


def test_normalize_business_stage_uppercase_with_underscore():
    """Test normalization function with uppercase enum name like "PRE_REVENUE"."""
    result = normalize_business_stage("PRE_REVENUE")
    assert result == BusinessStage.PRE_REVENUE
    assert result.value == "pre-revenue"


def test_normalize_business_stage_lowercase_with_underscore():
    """Test normalization function with lowercase with underscore."""
    result = normalize_business_stage("pre_revenue")
    assert result == BusinessStage.PRE_REVENUE
    assert result.value == "pre-revenue"


def test_normalize_business_stage_lowercase_with_hyphen():
    """Test normalization function with lowercase with hyphen (already correct)."""
    result = normalize_business_stage("pre-revenue")
    assert result == BusinessStage.PRE_REVENUE
    assert result.value == "pre-revenue"


def test_normalize_business_stage_enum_object():
    """Test normalization function with enum object."""
    result = normalize_business_stage(BusinessStage.PRE_REVENUE)
    assert result == BusinessStage.PRE_REVENUE
    assert result.value == "pre-revenue"


def test_normalize_business_stage_early_revenue():
    """Test normalization with EARLY_REVENUE."""
    result = normalize_business_stage("EARLY_REVENUE")
    assert result == BusinessStage.EARLY_REVENUE
    assert result.value == "early-revenue"


def test_normalize_business_stage_idea():
    """Test normalization with IDEA."""
    result = normalize_business_stage("IDEA")
    assert result == BusinessStage.IDEA
    assert result.value == "idea"


def test_normalize_business_stage_scaling():
    """Test normalization with SCALING."""
    result = normalize_business_stage("SCALING")
    assert result == BusinessStage.SCALING
    assert result.value == "scaling"


def test_normalize_business_stage_with_spaces():
    """Test normalization with spaces."""
    result = normalize_business_stage("pre revenue")
    assert result == BusinessStage.PRE_REVENUE
    assert result.value == "pre-revenue"


def test_normalize_business_stage_invalid_raises_error():
    """Test that invalid business_stage raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        normalize_business_stage("NOT_A_STAGE")
    
    assert "Invalid business_stage value" in str(exc_info.value)
    assert "Allowed values are" in str(exc_info.value)


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


def override_get_current_user(db: Session = Depends(lambda: None)):
    """Override dependency - will be set per test."""
    pass


def test_post_onboarding_with_pre_revenue_enum_name(db: Session, test_user: User):
    """Test that POST with business_stage='PRE_REVENUE' persists as 'pre-revenue'."""
    # Override get_current_user dependency
    app.dependency_overrides[get_current_user] = lambda: test_user
    
    try:
        client = TestClient(app)
        
        payload = {
            "full_name": "Test User",
            "business_model": "service",
            "business_stage": "PRE_REVENUE",  # Enum name, should normalize to "pre-revenue"
            "biggest_challenge": "sales",
            "economic_sector": "technology",
            "industry": "software",
        }
        
        response = client.post("/api/onboarding", json=payload)
        
        # Should succeed
        assert response.status_code == 201, f"Response: {response.text}"
        
        # Verify response has normalized value
        data = response.json()
        assert data["business_stage"] == "pre-revenue"
        
        # Verify it's persisted correctly in DB
        profile = db.query(OnboardingProfile).filter(
            OnboardingProfile.user_id == test_user.id
        ).first()
        assert profile is not None
        assert profile.business_stage == BusinessStage.PRE_REVENUE
        assert profile.business_stage.value == "pre-revenue"
    finally:
        app.dependency_overrides.clear()


def test_post_onboarding_with_pre_revenue_lowercase_underscore(db: Session, test_user: User):
    """Test that POST with business_stage='pre_revenue' persists as 'pre-revenue'."""
    app.dependency_overrides[get_current_user] = lambda: test_user
    
    try:
        client = TestClient(app)
        
        payload = {
            "full_name": "Test User",
            "business_model": "service",
            "business_stage": "pre_revenue",  # Lowercase with underscore
            "biggest_challenge": "sales",
            "economic_sector": "technology",
            "industry": "software",
        }
        
        response = client.post("/api/onboarding", json=payload)
        
        # Should succeed
        assert response.status_code == 201, f"Response: {response.text}"
        
        # Verify response has normalized value
        data = response.json()
        assert data["business_stage"] == "pre-revenue"
        
        # Verify it's persisted correctly in DB
        profile = db.query(OnboardingProfile).filter(
            OnboardingProfile.user_id == test_user.id
        ).first()
        assert profile is not None
        assert profile.business_stage.value == "pre-revenue"
    finally:
        app.dependency_overrides.clear()


def test_post_onboarding_with_invalid_stage_returns_400(db: Session, test_user: User):
    """Test that POST with business_stage='NOT_A_STAGE' returns 400 with allowed values."""
    app.dependency_overrides[get_current_user] = lambda: test_user
    
    try:
        client = TestClient(app)
        
        payload = {
            "full_name": "Test User",
            "business_model": "service",
            "business_stage": "NOT_A_STAGE",  # Invalid value
            "biggest_challenge": "sales",
            "economic_sector": "technology",
            "industry": "software",
        }
        
        response = client.post("/api/onboarding", json=payload)
        
        # Should return 400, not 500
        assert response.status_code == 400, f"Response: {response.text}"
        
        # Verify error message includes allowed values
        data = response.json()
        assert "detail" in data
        assert "allowed_values" in data["detail"]
        assert "pre-revenue" in data["detail"]["allowed_values"]
    finally:
        app.dependency_overrides.clear()

