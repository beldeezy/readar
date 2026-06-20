"""Tests for the book-status critical path.

Covers the two-store sync gotcha and the reading-history side-effect:
- marking a book read writes a ReadingHistoryEntry (powers books-read count/goal)
- marking currently_reading clears the engine interaction (so it can't feed recs)
- _lookup_book resolves UUID and external_id ids

The endpoint commits across its own get_db session (a different connection than
the test transaction), so the DB side-effects are tested by calling the router's
logic functions directly against the test session. Pure-validation and auth
behaviour are tested through the API (no DB writes needed for those paths).
"""
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User, Book, UserBookInteraction, UserBookStatus, ReadingHistoryEntry
from app.core.user_helpers import get_or_create_user_by_auth_id
from app.routers.book_status import (
    _record_read_in_history,
    _delete_interaction,
    _lookup_book,
)
from app.main import app
from app.core.auth import get_current_user


@pytest.fixture
def user(db: Session) -> User:
    return get_or_create_user_by_auth_id(
        db=db, auth_user_id=str(uuid4()), email=f"{uuid4()}@example.com"
    )


@pytest.fixture
def book(db: Session) -> Book:
    b = Book(
        id=uuid4(),
        title="Built to Sell",
        author_name="John Warrillow",
        description="Creating a business that can thrive without you.",
        external_id="ext-built-to-sell",
    )
    db.add(b)
    db.flush()
    return b


# --- reading-history side-effect -------------------------------------------------

def test_read_liked_creates_reading_history_entry(db: Session, user: User, book: Book):
    _record_read_in_history(db, user.id, book, "read_liked")
    db.flush()

    entry = (
        db.query(ReadingHistoryEntry)
        .filter(ReadingHistoryEntry.user_id == user.id)
        .one()
    )
    assert entry.title == book.title
    assert entry.shelf == "read"
    assert entry.my_rating == 5.0
    assert entry.catalog_book_id == book.id
    assert entry.source == "readar"


def test_read_disliked_uses_low_rating(db: Session, user: User, book: Book):
    _record_read_in_history(db, user.id, book, "read_disliked")
    db.flush()
    entry = db.query(ReadingHistoryEntry).filter(ReadingHistoryEntry.user_id == user.id).one()
    assert entry.my_rating == 2.0


def test_record_read_is_idempotent_on_title_author(db: Session, user: User, book: Book):
    """Re-marking the same book read updates the row in place (merges with import)."""
    _record_read_in_history(db, user.id, book, "read_disliked")
    db.flush()
    _record_read_in_history(db, user.id, book, "read_liked")
    db.flush()

    entries = db.query(ReadingHistoryEntry).filter(ReadingHistoryEntry.user_id == user.id).all()
    assert len(entries) == 1  # no duplicate
    assert entries[0].my_rating == 5.0  # updated to the latest


# --- two-store sync: currently_reading clears the engine interaction -------------

def test_delete_interaction_removes_engine_row(db: Session, user: User, book: Book):
    db.add(UserBookInteraction(
        id=uuid4(), user_id=user.id, book_id=book.id, status=UserBookStatus.INTERESTED
    ))
    db.flush()

    _delete_interaction(db, user.id, str(book.id))
    db.flush()

    remaining = (
        db.query(UserBookInteraction)
        .filter(UserBookInteraction.user_id == user.id, UserBookInteraction.book_id == book.id)
        .count()
    )
    assert remaining == 0


def test_delete_interaction_noop_for_non_uuid_id(db: Session, user: User):
    """A free-form (non-UUID) book id must not raise — interactions are UUID-keyed."""
    _delete_interaction(db, user.id, "ext-not-a-uuid")  # should simply no-op


# --- _lookup_book resolution -----------------------------------------------------

def test_lookup_book_by_uuid(db: Session, book: Book):
    assert _lookup_book(db, str(book.id)) is not None
    assert _lookup_book(db, str(book.id)).id == book.id


def test_lookup_book_by_external_id(db: Session, book: Book):
    found = _lookup_book(db, "ext-built-to-sell")
    assert found is not None
    assert found.id == book.id


def test_lookup_book_missing_returns_none(db: Session):
    assert _lookup_book(db, str(uuid4())) is None


# --- endpoint-level: validation + auth (no DB writes on these paths) -------------

def test_invalid_status_returns_400(db: Session, user: User):
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client = TestClient(app)
        resp = client.post("/api/book-status", json={"book_id": str(uuid4()), "status": "bogus"})
        assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_book_status_requires_auth():
    """No credentials -> rejected (401/403), never an anonymous write."""
    client = TestClient(app)
    resp = client.post("/api/book-status", json={"book_id": str(uuid4()), "status": "interested"})
    assert resp.status_code in (401, 403)
