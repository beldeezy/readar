"""Completion is private, atomic and replay-safe; return actions use saved work."""
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import text, inspect

from app.core.auth import get_current_user
from app.core.user_helpers import get_or_create_user_by_auth_id
from app.database import get_db
from app.main import app
from app.models import (Book, BusinessStage, OnboardingProfile, ReadingCompletion, ReadingHistoryEntry,
                        ReadingLog, ReadingTakeaway, UserBookStatusModel)
from app.routers import reading_journey


@pytest.fixture
def journey(db, monkeypatch):
    user = get_or_create_user_by_auth_id(db, str(uuid4()), f"{uuid4()}@example.test")
    other = get_or_create_user_by_auth_id(db, str(uuid4()), f"{uuid4()}@example.test")
    book = Book(id=uuid4(), title="Next chapter", author_name="Writer", description="A test book", page_count=100)
    db.add(book); db.flush()
    db.add(UserBookStatusModel(user_id=user.id, book_id=str(book.id), status="currently_reading"))
    db.add(OnboardingProfile(user_id=user.id, business_model="service", business_stage=BusinessStage.EARLY_REVENUE, biggest_challenge="Find customers"))
    db.commit()
    monkeypatch.setattr("app.database.SessionLocal", Mock(return_value=Mock()))
    monkeypatch.setattr(reading_journey, "utc_now", lambda: datetime(2026, 9, 21, 1, tzinfo=timezone.utc))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app), user, other, book
    app.dependency_overrides.clear()


def body(**changes):
    return dict(request_id=str(uuid4()), rating=None, reflection="", next_challenge=None, expected_challenge=None) | changes


def finish(client, book, payload=None, tz="UTC"):
    return client.post(f"/api/reading/books/{book.id}/finish", json=payload or body(), params={"tz": tz})


def test_finish_saves_all_and_survives_reload_without_awarding_progress(db, journey):
    client, user, _, book = journey
    payload = body(rating=4, reflection="Test one offer", next_challenge="Price my service", expected_challenge="Find customers")
    response = finish(client, book, payload)
    assert response.status_code == 200, response.text
    assert response.json()["challenge_after"] == "Price my service"
    db.expire_all()
    saved = client.get("/api/reading/journey").json()
    assert saved["challenge"] == "Price my service"
    assert saved["completions"][0]["reflection"] == "Test one offer"
    assert saved["next_action"]["kind"] == "finished"
    assert db.query(UserBookStatusModel).filter_by(user_id=user.id).one().status == "finished"
    history = db.query(ReadingHistoryEntry).filter_by(user_id=user.id).one()
    assert (history.shelf, history.my_rating, history.catalog_book_id) == ("read", 4, book.id)
    assert db.query(ReadingLog).filter_by(user_id=user.id).count() == 0
    assert client.get("/api/reading/rewards").json()["total_points"] == 0


def test_response_loss_retry_keeps_one_finish_and_does_not_overwrite_new_challenge(db, journey):
    client, user, _, book = journey
    payload = body(next_challenge="Price my service", expected_challenge="Find customers")
    first = finish(client, book, payload)
    profile = db.query(OnboardingProfile).filter_by(user_id=user.id).one()
    profile.biggest_challenge = "Hire a team"; db.commit()
    assert finish(client, book, payload).json() == first.json()
    assert db.query(ReadingCompletion).count() == 1
    assert db.query(ReadingHistoryEntry).count() == 1
    assert client.get("/api/reading/journey").json()["challenge"] == "Hire a team"
    assert finish(client, book).status_code == 409


def test_optional_feedback_does_not_invent_a_rating_or_change_challenge(db, journey):
    client, user, _, book = journey
    assert finish(client, book).status_code == 200
    history = db.query(ReadingHistoryEntry).one()
    assert history.my_rating is None
    assert client.get("/api/reading/journey").json()["challenge"] == "Find customers"


def test_imported_history_is_reused_and_optional_rating_is_preserved(db, journey):
    client, user, _, book = journey
    db.add(ReadingHistoryEntry(user_id=user.id, title=book.title, author=book.author_name, my_rating=3, shelf="to-read", source="goodreads"))
    db.commit()
    assert finish(client, book).status_code == 200
    rows = db.query(ReadingHistoryEntry).filter_by(user_id=user.id).all()
    assert len(rows) == 1
    assert rows[0].my_rating == 3
    assert rows[0].shelf == "read"


def test_finish_failure_rolls_back_history_shelf_profile_and_completion(db, journey, monkeypatch):
    client, user, _, book = journey
    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", Mock(side_effect=RuntimeError("write failure")))
        assert finish(client, book, body(rating=5, next_challenge="Hire", expected_challenge="Find customers")).status_code == 500
    db.expire_all()
    assert db.query(ReadingCompletion).count() == 0
    assert db.query(ReadingHistoryEntry).count() == 0
    assert db.query(UserBookStatusModel).filter_by(user_id=user.id).one().status == "currently_reading"
    assert db.query(OnboardingProfile).filter_by(user_id=user.id).one().biggest_challenge == "Find customers"


def test_stale_challenge_rejected_without_partial_finish(db, journey):
    client, _, _, book = journey
    assert finish(client, book, body(next_challenge="Hire", expected_challenge="Old challenge")).status_code == 409
    assert db.query(ReadingCompletion).count() == 0
    assert db.query(ReadingHistoryEntry).count() == 0


def test_finish_requires_started_book_and_is_scoped_to_reader(db, journey):
    client, user, other, book = journey
    app.dependency_overrides[get_current_user] = lambda: other
    assert finish(client, book).status_code == 409
    assert client.get("/api/reading/journey").json()["completions"] == []
    app.dependency_overrides[get_current_user] = lambda: user
    assert finish(client, book, body(reflection="Private note")).status_code == 200
    app.dependency_overrides[get_current_user] = lambda: other
    assert "Private note" not in client.get("/api/reading/journey").text
    assert client.get("/api/reading/journey").json()["next_action"]["kind"] == "new"


@pytest.mark.parametrize("changes", [{"rating": True}, {"rating": 6}, {"rating": "5"}, {"reflection": "a"*2001}, {"next_challenge": " "}, {"user_id": str(uuid4())}])
def test_finish_validates_input(db, journey, changes):
    client, _, _, book = journey
    assert finish(client, book, body(**changes)).status_code == 422
    assert db.query(ReadingCompletion).count() == 0


def test_local_date_snooze_and_opt_out_persist_without_changing_email(db, journey):
    client, user, _, book = journey
    original = user.notify_email_recommendations
    params = {"tz": "America/Los_Angeles"}
    assert client.get("/api/reading/journey", params=params).json()["today"] == "2026-09-20"
    saved = client.put("/api/reading/journey/preferences", params=params, json={"show_next_action": True, "snooze_days": 1})
    assert saved.json()["snoozed_until"] == "2026-09-21"
    assert client.get("/api/reading/journey", params=params).json()["next_action"] is None
    assert client.get("/api/reading/journey").json()["next_action"] is not None
    assert client.put("/api/reading/journey/preferences", json={"show_next_action": False}).status_code == 200
    assert client.get("/api/reading/journey").json()["next_action"] is None
    assert client.put("/api/reading/journey/preferences", json={"show_next_action": True}).status_code == 200
    assert client.get("/api/reading/journey").json()["next_action"]["kind"] == "reading"
    assert user.notify_email_recommendations == original
    assert finish(client, book, tz="America/Los_Angeles").json()["completed_on"] == "2026-09-20"


def test_stalled_and_pending_action_return_reasons_use_real_saved_work(db, journey):
    client, user, _, book = journey
    shelf = db.query(UserBookStatusModel).filter_by(user_id=user.id).one()
    shelf.updated_at = datetime(2026, 9, 15); db.commit()
    assert client.get("/api/reading/journey").json()["next_action"]["kind"] == "restart"
    db.add(ReadingTakeaway(user_id=user.id, book_id=book.id, client_id=uuid4(), book_title=book.title,
                          book_author=book.author_name, takeaway="Ask users first", action_text="Interview one customer",
                          goal_context="Find customers")); db.commit()
    action = client.get("/api/reading/journey").json()["next_action"]
    assert action["kind"] == "action"
    assert action["detail"] == "Interview one customer"


def test_journey_routes_require_auth():
    client = TestClient(app)
    assert client.get("/api/reading/journey").status_code in (401, 403)
    assert client.post(f"/api/reading/books/{uuid4()}/finish", json=body()).status_code in (401, 403)


def test_migration_roundtrip_preserves_existing_tables(db, monkeypatch):
    connection = db.connection()
    schema = 'journey_' + uuid4().hex
    previous = connection.execute(text("SELECT current_setting('search_path')")).scalar_one()
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connection.execute(text("SELECT set_config('search_path', :path, true)"), {"path": schema})
    try:
        connection.execute(text('CREATE TABLE users (id UUID PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE books (id UUID PRIMARY KEY)'))
        path = Path(__file__).parents[1] / 'alembic/versions/b4c5d6e7f8a9_add_reading_journey.py'
        spec = importlib.util.spec_from_file_location('journey_migration', path)
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        user = uuid4()
        connection.execute(text('INSERT INTO users (id) VALUES (:id)'), {'id': user})
        connection.execute(text('INSERT INTO reading_journey_preferences (user_id) VALUES (:id)'), {'id': user})
        assert connection.execute(text('SELECT show_next_action FROM reading_journey_preferences')).scalar_one() is True
        assert len(inspect(connection).get_unique_constraints('reading_completions', schema=schema)) == 2
        migration.downgrade()
        assert set(inspect(connection).get_table_names(schema=schema)) == {'users', 'books'}
    finally:
        connection.execute(text("SELECT set_config('search_path', :path, true)"), {'path': previous})
