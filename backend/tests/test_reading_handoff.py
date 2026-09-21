"""RD-53: selection, waiting and start survive reload without inventing progress."""
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.user_helpers import get_or_create_user_by_auth_id
from app.database import get_db
from app.main import app
from app.models import Book, ReadingHistoryEntry, UserBookInteraction, UserBookStatus, UserBookStatusModel


@pytest.fixture
def handoff(db, monkeypatch):
    user = get_or_create_user_by_auth_id(db, str(uuid4()), f"{uuid4()}@example.com")
    other = get_or_create_user_by_auth_id(db, str(uuid4()), f"{uuid4()}@example.com")
    book = Book(id=uuid4(), title="The next chapter", author_name="Test Author", description="Test book",
                cover_image_url="https://example.com/cover.jpg", purchase_url="https://example.com/book")
    db.add(book)
    db.flush()
    # Event logging is best effort on a separate production session. Keep it
    # outside this transaction-isolation test and never contact a live DB.
    monkeypatch.setattr("app.database.SessionLocal", Mock(return_value=Mock()))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    yield client, user, other, book
    app.dependency_overrides.clear()


def select(client, book):
    return client.post("/api/reading/selection", json={"book_id": str(book.id)})


def change(client, book, status):
    return client.post("/api/book-status", json={"book_id": str(book.id), "status": status, "source": "reading_page"})


def saved_list(client, db, status=None):
    db.expire_all()
    response = client.get("/api/profile/book-status", params={"status": status} if status else {})
    assert response.status_code == 200
    return response.json()


def test_choose_wait_start_and_correct_survive_reload(db, handoff):
    client, user, _, book = handoff
    response = select(client, book)
    assert response.status_code == 200
    assert response.json()["status"] == "reading_next"
    assert saved_list(client, db, "currently_reading") == []
    queued = saved_list(client, db, "reading_next")
    assert len(queued) == 1
    assert queued[0]["title"] == book.title
    assert queued[0]["cover_image_url"] == book.cover_image_url
    assert queued[0]["purchase_url"] == book.purchase_url

    assert change(client, book, "waiting_for_book").status_code == 200
    assert saved_list(client, db, "reading_next") == []
    assert len(saved_list(client, db, "waiting_for_book")) == 1
    assert saved_list(client, db, "currently_reading") == []

    assert change(client, book, "currently_reading").status_code == 200
    assert saved_list(client, db, "waiting_for_book") == []
    assert len(saved_list(client, db, "currently_reading")) == 1
    assert change(client, book, "reading_next").status_code == 200
    assert len(saved_list(client, db, "reading_next")) == 1
    assert saved_list(client, db, "currently_reading") == []
    assert db.query(ReadingHistoryEntry).filter_by(user_id=user.id).count() == 0


@pytest.mark.parametrize("state", ["reading_next", "waiting_for_book", "currently_reading"])
def test_reselecting_or_retrying_preserves_existing_reading_state(db, handoff, state):
    client, _, _, book = handoff
    assert change(client, book, state).status_code == 200
    for _ in range(2):
        assert select(client, book).json()["status"] == state
    items = saved_list(client, db)
    assert len(items) == 1
    assert items[0]["status"] == state


def test_selection_is_distinct_from_saving_for_later(db, handoff):
    client, user, _, book = handoff
    db.add(UserBookInteraction(user_id=user.id, book_id=book.id, status=UserBookStatus.INTERESTED))
    db.flush()
    assert change(client, book, "interested").status_code == 200
    assert len(saved_list(client, db, "interested")) == 1
    assert select(client, book).status_code == 200
    assert saved_list(client, db, "interested") == []
    assert len(saved_list(client, db, "reading_next")) == 1
    assert db.query(UserBookInteraction).filter_by(user_id=user.id, book_id=book.id).count() == 0


def test_accounts_cannot_read_or_change_each_others_choice(db, handoff):
    client, user, other, book = handoff
    assert change(client, book, "waiting_for_book").status_code == 200
    app.dependency_overrides[get_current_user] = lambda: other
    assert saved_list(client, db) == []
    assert select(client, book).status_code == 200
    assert saved_list(client, db)[0]["status"] == "reading_next"
    assert client.delete(f"/api/book-status/{book.id}").status_code == 200
    assert saved_list(client, db) == []
    app.dependency_overrides[get_current_user] = lambda: user
    assert saved_list(client, db)[0]["status"] == "waiting_for_book"


def test_unknown_book_does_not_create_a_lost_selection(db, handoff):
    client, _, _, _ = handoff
    response = client.post("/api/reading/selection", json={"book_id": str(uuid4())})
    assert response.status_code == 404
    assert saved_list(client, db) == []


def test_failed_write_returns_error_and_keeps_previous_state(db, handoff, monkeypatch):
    client, user, _, book = handoff
    assert change(client, book, "waiting_for_book").status_code == 200
    # Simulate the commit failing after the SQL write, not just before it.
    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", Mock(side_effect=RuntimeError("test commit failure")))
        response = change(client, book, "currently_reading")
        assert response.status_code == 500
    db.expire_all()
    assert db.query(UserBookStatusModel).filter_by(user_id=user.id, book_id=str(book.id)).one().status == "waiting_for_book"


def test_secondary_event_failure_does_not_turn_saved_selection_into_failure(db, handoff, monkeypatch):
    client, _, _, book = handoff
    monkeypatch.setattr("app.routers.book_status.log_event", Mock(side_effect=RuntimeError("test event failure")))
    assert select(client, book).status_code == 200
    assert len(saved_list(client, db, "reading_next")) == 1


def test_selection_requires_auth():
    client = TestClient(app)
    assert client.post("/api/reading/selection", json={"book_id": str(uuid4())}).status_code in (401, 403)


def test_existing_read_actions_still_update_history(db, handoff, monkeypatch):
    client, user, _, book = handoff
    monkeypatch.setattr("app.routers.book_status._regen_reading_profile", Mock())
    assert change(client, book, "read_liked").status_code == 200
    assert saved_list(client, db)[0]["status"] == "read_liked"
    assert change(client, book, "read_disliked").status_code == 200
    entries = db.query(ReadingHistoryEntry).filter_by(user_id=user.id).all()
    assert len(entries) == 1
    assert entries[0].shelf == "read"
    assert entries[0].my_rating == 2.0
