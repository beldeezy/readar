"""RD-54: authenticated logs, corrections, retries and migration against Postgres."""
from datetime import date, datetime, timezone
import importlib.util
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import inspect, text

from app.core.auth import get_current_user
from app.core.user_helpers import get_or_create_user_by_auth_id
from app.database import get_db
from app.main import app
from app.models import Book, ReadingHistoryEntry, ReadingLog, ReadingProgress, UserBookStatusModel
from app.routers.reading_progress import local_today

TODAY = "2026-09-17"
YESTERDAY = "2026-09-16"


@pytest.fixture
def reading(db, monkeypatch):
    user = get_or_create_user_by_auth_id(db, str(uuid4()), f"{uuid4()}@example.com")
    other = get_or_create_user_by_auth_id(db, str(uuid4()), f"{uuid4()}@example.com")
    book = Book(id=uuid4(), title="Reading fixture", author_name="Test Author", description="Test book", page_count=100)
    db.add(book)
    db.flush()
    shelf = UserBookStatusModel(user_id=user.id, book_id=str(book.id), status="currently_reading")
    db.add(shelf)
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr("app.routers.reading_progress.local_today", lambda tz: date.fromisoformat(TODAY))
    yield TestClient(app), user, other, book, shelf
    app.dependency_overrides.clear()


def url(book, path="progress"):
    return f"/api/reading/books/{book.id}/{path}"


def get(client, book):
    response = client.get(url(book), params={"tz": "America/New_York"})
    assert response.status_code == 200, response.text
    return response.json()


def log(client, book, position, revision, day=TODAY):
    return client.put(url(book, f"logs/{day}"), json={"position": position, "expected_revision": revision})


def settings(client, book, revision=0, **changes):
    data = dict(unit="pages", starting_position=0, total_units=100, daily_goal=10, expected_revision=revision)
    return client.put(url(book, "settings"), json={**data, **changes})


def test_default_progress_is_read_only_and_missing_total_stays_unknown(db, reading):
    client, _, _, book, _ = reading
    state = get(client, book)
    assert (state["current_position"], state["daily_goal"], state["today_units"], state["revision"]) == (0, 10, 0, 0)
    assert state["logs"] == []
    assert db.query(ReadingProgress).count() == 0
    book.page_count = None
    db.commit()
    assert get(client, book)["percent_complete"] is None
    assert log(client, book, 12, 0).status_code == 200
    assert get(client, book)["total_units"] is None


def test_log_reload_update_and_retry_do_not_duplicate_credit(db, reading):
    client, user, _, book, _ = reading
    first = log(client, book, 10, 0)
    assert first.status_code == 200, first.text
    assert log(client, book, 10, 0).status_code == 200  # lost response retry
    state = get(client, book)
    assert (state["current_position"], state["today_units"], state["revision"]) == (10, 10, 1)
    assert state["goal_met"] is True
    assert len(state["logs"]) == 1
    assert log(client, book, 16, 1).status_code == 200
    state = get(client, book)
    assert state["today_units"] == 16
    assert state["percent_complete"] == 16
    assert db.query(ReadingLog).filter_by(user_id=user.id).count() == 1


def test_correction_recalculates_later_amounts_and_delete_restores_position(db, reading):
    client, _, _, book, _ = reading
    assert log(client, book, 10, 0, YESTERDAY).status_code == 200
    assert log(client, book, 25, 1).status_code == 200
    assert get(client, book)["today_units"] == 15
    assert log(client, book, 12, 2, YESTERDAY).status_code == 200
    state = get(client, book)
    assert state["today_units"] == 13
    assert client.delete(url(book, f"logs/{TODAY}"), params={"expected_revision": 3}).status_code == 200
    state = get(client, book)
    assert (state["current_position"], state["today_units"]) == (12, 0)
    assert client.delete(url(book, f"logs/{TODAY}"), params={"expected_revision": 3}).status_code == 200
    assert get(client, book)["revision"] == 4


def test_starting_position_is_not_new_reading_credit(db, reading):
    client, _, _, book, _ = reading
    assert settings(client, book, starting_position=30, daily_goal=5).status_code == 200
    assert get(client, book)["today_units"] == 0
    assert log(client, book, 34, 1).status_code == 200
    state = get(client, book)
    assert state["today_units"] == 4
    assert state["goal_met"] is False
    assert settings(client, book, revision=2, starting_position=31, daily_goal=3).status_code == 200
    assert get(client, book)["today_units"] == 3


def test_chapters_and_unknown_length_round_trip_without_mixing_units(db, reading):
    client, _, _, book, _ = reading
    assert settings(client, book, unit="chapters", daily_goal=1, total_units=None).status_code == 200
    assert log(client, book, 2, 1).status_code == 200
    state = get(client, book)
    assert state["unit"] == "chapters"
    assert state["total_units"] is None
    assert state["percent_complete"] is None
    assert settings(client, book, revision=2).status_code == 422
    assert get(client, book)["unit"] == "chapters"


def test_stale_device_cannot_overwrite_a_newer_log_or_settings(db, reading):
    client, _, _, book, _ = reading
    assert log(client, book, 20, 0).status_code == 200
    assert log(client, book, 15, 0).status_code == 409
    assert settings(client, book, daily_goal=5).status_code == 409
    state = get(client, book)
    assert (state["current_position"], state["daily_goal"], state["revision"]) == (20, 10, 1)


@pytest.mark.parametrize("value", [-1, 100001, 1.5, True, "10"])
def test_invalid_position_is_rejected(db, reading, value):
    client, _, _, book, _ = reading
    assert log(client, book, value, 0).status_code == 422
    assert get(client, book)["logs"] == []


def test_future_backwards_and_beyond_edition_entries_are_rejected(db, reading):
    client, _, _, book, _ = reading
    assert log(client, book, 10, 0, "2026-09-18").status_code == 422
    assert log(client, book, 101, 0).status_code == 422
    assert log(client, book, 20, 0).status_code == 200
    assert log(client, book, 21, 1, YESTERDAY).status_code == 422
    assert settings(client, book, revision=1, total_units=19).status_code == 422
    assert settings(client, book, revision=1, starting_position=21).status_code == 422
    assert get(client, book)["current_position"] == 20


def test_waiting_books_cannot_accidentally_log_reading(db, reading):
    client, _, _, book, shelf = reading
    shelf.status = "waiting_for_book"
    db.commit()
    assert log(client, book, 10, 0).status_code == 409
    assert db.query(ReadingProgress).count() == 0


def test_history_survives_a_pause_and_reselection(db, reading):
    client, _, _, book, shelf = reading
    assert log(client, book, 10, 0).status_code == 200
    shelf.status = "reading_next"
    db.commit()
    assert get(client, book)["current_position"] == 10
    shelf.status = "currently_reading"
    db.commit()
    assert log(client, book, 15, 1).status_code == 200


def test_account_isolation_and_completion_is_not_automatic(db, reading):
    client, user, other, book, _ = reading
    assert log(client, book, 100, 0).status_code == 200
    assert db.query(ReadingHistoryEntry).filter_by(user_id=user.id).count() == 0
    assert db.query(UserBookStatusModel).filter_by(user_id=user.id).one().status == "currently_reading"
    app.dependency_overrides[get_current_user] = lambda: other
    assert get(client, book)["logs"] == []
    assert client.delete(url(book, f"logs/{TODAY}"), params={"expected_revision": 1}).status_code == 409
    app.dependency_overrides[get_current_user] = lambda: user
    assert get(client, book)["current_position"] == 100


def test_commit_failure_preserves_log_and_revision(db, reading, monkeypatch):
    client, _, _, book, _ = reading
    assert log(client, book, 10, 0).status_code == 200
    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", Mock(side_effect=RuntimeError("test failure")))
        assert log(client, book, 20, 1).status_code == 500
    state = get(client, book)
    assert (state["current_position"], state["revision"]) == (10, 1)


def test_local_day_uses_timezone_and_handles_invalid_zone():
    moment = datetime(2026, 9, 18, 2, 0, tzinfo=timezone.utc)
    assert local_today("America/New_York", moment) == date(2026, 9, 17)
    assert local_today("Asia/Tokyo", moment) == date(2026, 9, 18)
    with pytest.raises(HTTPException) as error:
        local_today("invalid/timezone", moment)
    assert error.value.status_code == 422


def test_progress_requires_auth():
    client = TestClient(app)
    assert client.get(f"/api/reading/books/{uuid4()}/progress").status_code in (401, 403)


def test_progress_migration_upgrade_and_downgrade(db, monkeypatch):
    """Exercise actual migration DDL in a disposable schema, never public data."""
    migration_path = Path(__file__).parents[1] / "alembic/versions/b8c9d0e1f2a3_add_reading_progress.py"
    spec = importlib.util.spec_from_file_location("rd54_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = db.connection()
    schema = "rd54_" + uuid4().hex
    previous = connection.execute(text("SELECT current_setting('search_path')")).scalar_one()
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connection.execute(text("SELECT set_config('search_path', :path, true)"), {"path": schema})
    try:
        connection.execute(text("CREATE TABLE users (id UUID PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE books (id UUID PRIMARY KEY)"))
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        tables = inspect(connection).get_table_names(schema=schema)
        assert "reading_progress" in tables and "reading_logs" in tables
        constraints = inspect(connection).get_unique_constraints("reading_logs", schema=schema)
        assert any(c["column_names"] == ["user_id", "book_id", "reading_date"] for c in constraints)
        checks = inspect(connection).get_check_constraints("reading_progress", schema=schema)
        assert len(checks) == 4
        migration.downgrade()
        assert set(inspect(connection).get_table_names(schema=schema)) == {"users", "books"}
    finally:
        connection.execute(text("SELECT set_config('search_path', :path, true)"), {"path": previous})
