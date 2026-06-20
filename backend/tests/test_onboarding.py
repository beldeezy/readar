"""Tests for onboarding business_stage normalization and the onboarding endpoint.

`normalize_business_stage` moved from app.routers.onboarding into a Pydantic
field validator on OnboardingPayload, so we exercise it by constructing the model
(the real path a request body takes) rather than calling a standalone function.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4
from pydantic import ValidationError

from app.models import BusinessStage, User, OnboardingProfile, EventLog
from app.schemas.onboarding import OnboardingPayload
from app.core.user_helpers import get_or_create_user_by_auth_id
from app.main import app
from app.core.auth import get_current_user, require_admin_user
from app.database import get_db


def _normalize(value) -> BusinessStage:
    """Run a value through the OnboardingPayload business_stage validator."""
    payload = OnboardingPayload(
        business_model="service",
        biggest_challenge="sales",
        business_stage=value,
    )
    return payload.business_stage


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("PRE_REVENUE", BusinessStage.PRE_REVENUE),
        ("pre_revenue", BusinessStage.PRE_REVENUE),
        ("pre-revenue", BusinessStage.PRE_REVENUE),
        ("pre revenue", BusinessStage.PRE_REVENUE),
        (BusinessStage.PRE_REVENUE, BusinessStage.PRE_REVENUE),
        ("EARLY_REVENUE", BusinessStage.EARLY_REVENUE),
        ("IDEA", BusinessStage.IDEA),
        ("SCALING", BusinessStage.SCALING),
    ],
)
def test_normalize_business_stage_accepts_variants(raw, expected):
    """Case/spacing/underscore/hyphen variants all normalize to the right enum."""
    assert _normalize(raw) == expected


def test_normalize_business_stage_invalid_raises():
    """An unknown stage raises a validation error listing allowed values."""
    with pytest.raises(ValidationError) as exc_info:
        _normalize("NOT_A_STAGE")
    msg = str(exc_info.value)
    assert "Invalid business_stage value" in msg
    assert "Allowed values are" in msg


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user with auth_user_id for Supabase-style auth."""
    return get_or_create_user_by_auth_id(
        db=db, auth_user_id=str(uuid4()), email=f"{uuid4()}@example.com"
    )


def test_post_onboarding_normalizes_enum_name(db: Session, test_user: User):
    """POST with business_stage='PRE_REVENUE' persists and returns 'pre-revenue'."""
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        response = client.post("/api/onboarding", json={
            "full_name": "Test User",
            "business_model": "service",
            "business_stage": "PRE_REVENUE",
            "biggest_challenge": "sales",
            "economic_sector": "technology",
            "industry": "software",
        })

        assert response.status_code == 201, f"Response: {response.text}"
        assert response.json()["business_stage"] == "pre-revenue"

        profile = db.query(OnboardingProfile).filter(
            OnboardingProfile.user_id == test_user.id
        ).first()
        assert profile is not None
        assert profile.business_stage == BusinessStage.PRE_REVENUE
    finally:
        app.dependency_overrides.clear()


def test_onboarding_funnel_counts_completed_by_session(db: Session, test_user: User):
    """The auth-wall funnel must measure signin_prompted -> completed by the same
    unit (anon session), so 'Completed (saved)' is counted by session_id while the
    authoritative user count is retained alongside.
    """
    # Start from a clean slate within this rolled-back transaction. log_event_best_effort
    # commits on a separate connection, so other tests can leak event_logs rows into the
    # DB when DATABASE_URL == TEST_DATABASE_URL (as in CI); deleting here keeps the
    # analytics aggregation (which shares this session) deterministic.
    db.query(EventLog).delete()
    sid = f"sess-{uuid4()}"
    db.add_all([
        EventLog(event_name="onboarding_started", session_id=sid),
        EventLog(event_name="onboarding_signin_prompted", session_id=sid),
        EventLog(event_name="onboarding_completed", session_id=sid, user_id=test_user.id),
    ])
    db.flush()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_admin_user] = lambda: test_user
    try:
        client = TestClient(app)
        resp = client.get("/api/admin/analytics?days=30")
        assert resp.status_code == 200, resp.text
        funnel = {s["stage"]: s for s in resp.json()["onboarding_funnel"]}

        assert funnel["Prompted to sign in"]["count"] == 1
        completed = funnel["Completed (saved)"]
        assert completed["count"] == 1   # counted by session (apples-to-apples)
        assert completed["users"] == 1   # authoritative user count retained
    finally:
        app.dependency_overrides.clear()


def test_post_onboarding_invalid_stage_returns_422(db: Session, test_user: User):
    """An invalid business_stage fails request-body validation (422)."""
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        response = client.post("/api/onboarding", json={
            "full_name": "Test User",
            "business_model": "service",
            "business_stage": "NOT_A_STAGE",
            "biggest_challenge": "sales",
        })
        assert response.status_code == 422, f"Response: {response.text}"
    finally:
        app.dependency_overrides.clear()
