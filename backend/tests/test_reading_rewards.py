"""RD-55: goal snapshots, reader-wide daily credit, streak recovery and migration."""
from datetime import date, datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import inspect, text

from app.core.auth import get_current_user
from app.core.user_helpers import get_or_create_user_by_auth_id
from app.database import get_db
from app.main import app
from app.models import Book, ReadingLog, ReadingProgress, UserBookStatusModel
from app.routers.reading_progress import local_today
from app.services.reading_rewards import summarize_rewards

TODAY = date(2026, 9, 17)


@pytest.mark.parametrize("offsets,current,best,points,state", [
    ([], 0, 0, 0, "new"),
    ([0], 1, 1, 10, "active"),
    ([-1], 1, 1, 10, "continue"),
    ([-2], 0, 1, 10, "restart"),
    ([-2, -1, 0], 3, 3, 30, "active"),
    ([-3, -2, -1], 3, 3, 30, "continue"),
    ([-5, -4, -3, 0], 1, 3, 40, "active"),
    ([-5, -4, -3, -1], 1, 3, 40, "continue"),
    ([-3, -2], 0, 2, 20, "restart"),
    ([1], 0, 0, 0, "new"),
])
def test_streak_boundaries(offsets, current, best, points, state):
    result = summarize_rewards({TODAY + timedelta(days=n) for n in offsets}, TODAY, "UTC")
    assert (result.current_streak, result.best_streak, result.total_points, result.state) == (current, best, points, state)
    assert result.today_qualified == (state == "active")
    assert len(result.recent_days) == 7
    assert result.recent_days[0].reading_date == TODAY - timedelta(days=6)
    assert result.recent_days[-1].reading_date == TODAY


def test_calendar_days_not_hours_across_dst_and_year_boundary():
    before = datetime(2026, 11, 1, 5, 30, tzinfo=timezone.utc)
    after = datetime(2026, 11, 1, 6, 30, tzinfo=timezone.utc)
    assert local_today("America/New_York", before) == local_today("America/New_York", after)
    days = {date(2025, 12, 31), date(2026, 1, 1)}
    assert summarize_rewards(days, date(2026, 1, 1), "UTC").current_streak == 2


@pytest.fixture
def rewards(db, monkeypatch):
    user = get_or_create_user_by_auth_id(db, str(uuid4()), f"{uuid4()}@example.com")
    other = get_or_create_user_by_auth_id(db, str(uuid4()), f"{uuid4()}@example.com")
    books = [Book(id=uuid4(), title=f"Rewards {i}", author_name="Test", description="Test", page_count=200) for i in range(2)]
    db.add_all(books)
    db.flush()
    for book in books:
        db.add(UserBookStatusModel(user_id=user.id, book_id=str(book.id), status="currently_reading"))
    db.commit()
    clock = {"today": TODAY}
    monkeypatch.setattr("app.routers.reading_progress.local_today", lambda tz: clock["today"])
    monkeypatch.setattr("app.routers.reading_rewards.local_today", lambda tz: clock["today"])
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app), user, other, books, clock
    app.dependency_overrides.clear()


def summary(client, tz="UTC"):
    response = client.get("/api/reading/rewards", params={"tz": tz})
    assert response.status_code == 200, response.text
    return response.json()


def log(client, book, position, revision, day=TODAY):
    return client.put(f"/api/reading/books/{book.id}/logs/{day}", json={"position": position, "expected_revision": revision})


def settings(client, book, revision=0, **changes):
    data = dict(unit="pages", starting_position=0, total_units=200, daily_goal=10, expected_revision=revision)
    response = client.put(f"/api/reading/books/{book.id}/settings", json={**data, **changes})
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_summary_does_not_write_and_one_day_counts_once(db, rewards):
    client, _, _, (book, second), _ = rewards
    assert summary(client)["state"] == "new"
    assert db.query(ReadingProgress).count() == db.query(ReadingLog).count() == 0
    assert log(client, book, 5, 0).status_code == 200
    assert summary(client)["total_points"] == 0
    assert log(client, book, 10, 1).status_code == 200
    assert log(client, book, 10, 1).status_code == 200  # lost-response retry
    assert log(client, book, 100, 2).status_code == 200  # more pages, same date
    assert log(client, second, 20, 0).status_code == 200
    result = summary(client)
    assert (result["total_points"], result["current_streak"], result["qualifying_days"]) == (10, 1, 1)
    assert summary(client) == result  # reload does not award again


def test_corrections_and_deletes_recalculate_later_credit(db, rewards):
    client, _, _, (book, _), _ = rewards
    yesterday = TODAY - timedelta(days=1)
    assert log(client, book, 10, 0, yesterday).status_code == 200
    assert log(client, book, 20, 1).status_code == 200
    assert summary(client)["total_points"] == 20
    assert log(client, book, 15, 2, yesterday).status_code == 200
    result = summary(client)
    assert (result["total_points"], result["current_streak"], result["today_qualified"]) == (10, 1, False)
    assert log(client, book, 10, 3, yesterday).status_code == 200
    assert summary(client)["current_streak"] == 2
    path = f"/api/reading/books/{book.id}/logs/{yesterday}"
    assert client.delete(path, params={"expected_revision": 4}).status_code == 200
    assert client.delete(path, params={"expected_revision": 4}).status_code == 200
    result = summary(client)
    assert (result["total_points"], result["best_streak"], result["today_qualified"]) == (10, 1, True)


def test_goal_changes_do_not_rewrite_existing_dates(db, rewards):
    client, _, _, (book, _), clock = rewards
    first = log(client, book, 5, 0).json()
    assert first["logs"][0]["goal_target"] == 10
    changed = settings(client, book, revision=1, daily_goal=3)
    assert (changed["daily_goal"], changed["today_goal"], changed["goal_met"]) == (3, 10, False)
    assert summary(client)["total_points"] == 0
    updated = log(client, book, 10, 2).json()
    assert updated["logs"][0]["goal_target"] == 10
    assert summary(client)["total_points"] == 10
    clock["today"] += timedelta(days=1)
    next_day = log(client, book, 13, 3, clock["today"]).json()
    assert (next_day["today_goal"], next_day["today_units"], next_day["goal_met"]) == (3, 3, True)
    assert summary(client)["total_points"] == 20
    settings(client, book, revision=4, daily_goal=100)
    assert summary(client)["total_points"] == 20


def test_starting_position_corrections_recalculate_without_crediting_prior_reading(db, rewards):
    client, _, _, (book, _), _ = rewards
    settings(client, book, starting_position=100)
    assert log(client, book, 100, 1).status_code == 200
    assert summary(client)["total_points"] == 0
    assert log(client, book, 110, 2).status_code == 200
    assert summary(client)["total_points"] == 10
    settings(client, book, revision=3, starting_position=105)
    assert summary(client)["total_points"] == 0


def test_chapters_qualify_without_combining_units_or_books(db, rewards):
    client, _, _, (pages, chapters), _ = rewards
    settings(client, chapters, unit="chapters", daily_goal=2, total_units=None)
    assert log(client, pages, 9, 0).status_code == 200
    assert log(client, chapters, 1, 1).status_code == 200
    assert summary(client)["total_points"] == 0
    assert log(client, chapters, 2, 2).status_code == 200
    assert summary(client)["total_points"] == 10
    assert log(client, pages, 10, 1).status_code == 200
    assert summary(client)["total_points"] == 10


def test_missed_day_retains_points_best_and_can_be_repaired(db, rewards):
    client, _, _, (book, _), clock = rewards
    assert log(client, book, 10, 0).status_code == 200
    clock["today"] += timedelta(days=1)
    assert summary(client)["state"] == "continue"
    clock["today"] += timedelta(days=1)
    missed = summary(client)
    assert (missed["state"], missed["current_streak"], missed["total_points"], missed["best_streak"]) == ("restart", 0, 10, 1)
    assert log(client, book, 30, 1, clock["today"]).status_code == 200
    assert summary(client)["current_streak"] == 1
    assert log(client, book, 20, 2, TODAY + timedelta(days=1)).status_code == 200
    repaired = summary(client)
    assert (repaired["current_streak"], repaired["total_points"]) == (3, 30)


def test_streak_continues_across_different_books_and_shelf_removal(db, rewards):
    client, user, _, (first, second), _ = rewards
    assert log(client, first, 10, 0, TODAY - timedelta(days=1)).status_code == 200
    assert log(client, second, 10, 0).status_code == 200
    db.query(UserBookStatusModel).filter_by(user_id=user.id).delete()
    db.commit()
    result = summary(client)
    assert (result["current_streak"], result["total_points"]) == (2, 20)


def test_unauthorized_or_rejected_writes_cannot_change_rewards(db, rewards, monkeypatch):
    client, user, other, (book, _), _ = rewards
    assert log(client, book, 10, 0).status_code == 200
    original = summary(client)
    assert log(client, book, 20, 0).status_code == 409
    assert log(client, book, 201, 1).status_code == 422
    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", Mock(side_effect=RuntimeError("test failure")))
        assert log(client, book, 5, 1).status_code == 500
    assert summary(client) == original
    app.dependency_overrides[get_current_user] = lambda: other
    assert summary(client)["total_points"] == 0
    assert log(client, book, 10, 0).status_code == 409
    app.dependency_overrides[get_current_user] = lambda: user
    assert summary(client) == original


def test_timezone_controls_today_without_rewriting_saved_dates(db, rewards, monkeypatch):
    client, _, _, (book, _), clock = rewards
    assert log(client, book, 10, 0).status_code == 200
    clock["today"] += timedelta(days=1)
    assert log(client, book, 20, 1, clock["today"]).status_code == 200
    moment = datetime(2026, 9, 18, 2, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("app.routers.reading_rewards.local_today", lambda tz: local_today(tz, moment))
    west = summary(client, "America/New_York")
    east = summary(client, "Asia/Tokyo")
    assert (west["today"], west["total_points"], west["timezone"]) == ("2026-09-17", 10, "America/New_York")
    assert (east["today"], east["total_points"]) == ("2026-09-18", 20)
    assert db.query(ReadingLog).count() == 2
    assert client.get("/api/reading/rewards?tz=invalid/zone").status_code == 422


def test_rewards_require_auth():
    assert TestClient(app).get("/api/reading/rewards").status_code in (401, 403)


def test_goal_snapshot_migration_backfills_and_downgrades(db, monkeypatch):
    """Upgrade actual RD-54 tables with representative page/chapter logs."""
    connection = db.connection()
    schema = "rd55_" + uuid4().hex
    previous = connection.execute(text("SELECT current_setting('search_path')")).scalar_one()
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connection.execute(text("SELECT set_config('search_path', :path, true)"), {"path": schema})
    try:
        connection.execute(text("CREATE TABLE users (id UUID PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE books (id UUID PRIMARY KEY)"))
        migrations = []
        for name in ("b8c9d0e1f2a3_add_reading_progress", "c9d0e1f2a3b4_snapshot_reading_goals"):
            path = Path(__file__).parents[1] / f"alembic/versions/{name}.py"
            spec = importlib.util.spec_from_file_location(name, path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migrations.append(migration)
        migrations[0].upgrade()
        user = uuid4()
        connection.execute(text("INSERT INTO users (id) VALUES (:id)"), {"id": user})
        for unit, goal in (("pages", 25), ("chapters", 2)):
            book = uuid4()
            connection.execute(text("INSERT INTO books (id) VALUES (:id)"), {"id": book})
            connection.execute(text("INSERT INTO reading_progress (id,user_id,book_id,unit,daily_goal) VALUES (:id,:user,:book,:unit,:goal)"), dict(id=uuid4(), user=user, book=book, unit=unit, goal=goal))
            connection.execute(text("INSERT INTO reading_logs (id,user_id,book_id,reading_date,position) VALUES (:id,:user,:book,:day,30)"), dict(id=uuid4(), user=user, book=book, day=TODAY))
        migrations[1].upgrade()
        assert sorted(connection.execute(text("SELECT goal_target FROM reading_logs")).scalars()) == [2, 25]
        goal_column = next(c for c in inspect(connection).get_columns("reading_logs", schema=schema) if c["name"] == "goal_target")
        assert goal_column["nullable"] is False
        assert any(c["name"] == "ck_reading_log_goal_target" for c in inspect(connection).get_check_constraints("reading_logs", schema=schema))
        migrations[1].downgrade()
        assert "goal_target" not in {c["name"] for c in inspect(connection).get_columns("reading_logs", schema=schema)}
        assert connection.execute(text("SELECT count(*) FROM reading_logs")).scalar_one() == 2
    finally:
        connection.execute(text("SELECT set_config('search_path', :path, true)"), {"path": previous})
