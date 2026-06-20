"""Tests for server-side daily refresh metering (the recommendations paywall)."""
import pytest
from uuid import uuid4
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User, SubscriptionStatus
from app.core.user_helpers import get_or_create_user_by_auth_id
from app.services.refresh_paywall import (
    FREE_DAILY_REFRESHES,
    RefreshLimitReached,
    refresh_status,
    consume_refresh,
    is_premium,
)
from app.main import app
from app.core.auth import get_current_user
from app.database import get_db


@pytest.fixture
def free_user(db: Session) -> User:
    return get_or_create_user_by_auth_id(
        db=db, auth_user_id=str(uuid4()), email=f"{uuid4()}@example.com"
    )


@pytest.fixture
def premium_user(db: Session, free_user: User) -> User:
    free_user.subscription_status = SubscriptionStatus.ACTIVE
    db.commit()
    return free_user


# --- service: status + consume ---------------------------------------------------

def test_free_user_starts_with_full_allowance(db: Session, free_user: User):
    status = refresh_status(free_user)
    assert status == {"is_premium": False, "limit": FREE_DAILY_REFRESHES, "used": 0,
                      "remaining": FREE_DAILY_REFRESHES}


def test_consume_decrements_then_blocks(db: Session, free_user: User):
    for i in range(FREE_DAILY_REFRESHES):
        status = consume_refresh(db, free_user)
        assert status["remaining"] == FREE_DAILY_REFRESHES - (i + 1)
    # Allowance exhausted -> next consume raises.
    with pytest.raises(RefreshLimitReached) as exc:
        consume_refresh(db, free_user)
    assert exc.value.limit == FREE_DAILY_REFRESHES
    assert exc.value.used == FREE_DAILY_REFRESHES


def test_counter_resets_on_new_day(db: Session, free_user: User):
    # Simulate yesterday's usage at the cap.
    free_user.daily_refresh_count = FREE_DAILY_REFRESHES
    free_user.daily_refresh_date = date.today() - timedelta(days=1)
    db.commit()

    # Stale date is treated as a fresh day.
    assert refresh_status(free_user)["remaining"] == FREE_DAILY_REFRESHES
    status = consume_refresh(db, free_user)
    assert status["used"] == 1
    assert free_user.daily_refresh_date == date.today()


def test_premium_is_unlimited(db: Session, premium_user: User):
    assert is_premium(premium_user)
    status = refresh_status(premium_user)
    assert status["is_premium"] is True
    assert status["remaining"] is None
    # Consuming many times never raises for premium.
    for _ in range(FREE_DAILY_REFRESHES + 5):
        consume_refresh(db, premium_user)


# --- endpoint enforcement --------------------------------------------------------

def test_spin_is_metered_and_blocks_after_limit(db: Session, free_user: User):
    app.dependency_overrides[get_current_user] = lambda: free_user
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        # First FREE_DAILY_REFRESHES spins succeed.
        for _ in range(FREE_DAILY_REFRESHES):
            resp = client.get("/api/recommendations?limit=5&spin=true")
            assert resp.status_code == 200, resp.text
        # The next spin is blocked.
        blocked = client.get("/api/recommendations?limit=5&spin=true")
        assert blocked.status_code == 429
        assert blocked.json()["detail"]["code"] == "daily_refresh_limit_reached"
    finally:
        app.dependency_overrides.clear()


def test_non_spin_loads_are_not_metered(db: Session, free_user: User):
    app.dependency_overrides[get_current_user] = lambda: free_user
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        # Many non-spin loads never consume the allowance.
        for _ in range(FREE_DAILY_REFRESHES + 3):
            resp = client.get("/api/recommendations?limit=5")
            assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["refreshes_remaining"] == FREE_DAILY_REFRESHES
        assert body["refresh_limit"] == FREE_DAILY_REFRESHES
        assert body["is_premium"] is False
    finally:
        app.dependency_overrides.clear()
