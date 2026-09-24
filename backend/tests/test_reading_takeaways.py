"""RD-56: durable reader-owned takeaways, retries, editing and context snapshots."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from sqlalchemy import inspect, text

from app.core.auth import get_current_user
from app.core.user_helpers import get_or_create_user_by_auth_id
from app.database import get_db
from app.main import app
from app.models import Book, BusinessStage, OnboardingProfile, ReadingHistoryEntry, ReadingLog, ReadingProgress, ReadingTakeaway, UserBookStatusModel
from app.routers.reading_takeaways import _suggested_goal
from app.schemas.reading_takeaways import TakeawayCreate, TakeawayUpdate

ROOT = "/api/reading/takeaways"


def body(book_id=None, **changes):
    return dict(book_id=str(book_id or uuid4()), client_id=str(uuid4()), takeaway="Explain the problem in the customer's words.",
                action_text="Ask two customers where they got stuck.", goal_context="Find a clearer message.") | changes


@pytest.mark.parametrize("field,value", [
    ("takeaway", " \n\t "), ("takeaway", "a" * 4001), ("takeaway", None), ("takeaway", 3),
    ("goal_context", " \n "), ("goal_context", "a" * 2001), ("goal_context", None),
    ("action_text", "a" * 2001), ("action_text", None), ("user_id", str(uuid4())),
])
def test_invalid_takeaway_input_is_rejected(field, value):
    with pytest.raises(ValidationError):
        TakeawayCreate(**body(**{field: value}))


def test_text_is_normalized_but_reader_formatting_survives():
    result = TakeawayCreate(**body(takeaway="  First line\nSecond line  ", action_text=" \t ", goal_context="  Grow carefully  "))
    assert (result.takeaway, result.action_text, result.goal_context) == ("First line\nSecond line", "", "Grow carefully")
    with pytest.raises(ValidationError):
        TakeawayUpdate(takeaway="Idea", goal_context="Goal", expected_revision=True)


def test_onboarding_suggestion_fallback_and_no_truncation():
    assert _suggested_goal(None) == ""
    profile = SimpleNamespace(future_vision=" \n ", vision_6_12_months="x" * 2001, primary_problems="  Finding clients  ", biggest_challenge="Focus")
    assert _suggested_goal(profile) == "Finding clients"
    profile.future_vision = "Build a stable business"
    assert _suggested_goal(profile) == "Build a stable business"


@pytest.fixture
def notes(db):
    user = get_or_create_user_by_auth_id(db, str(uuid4()), f"{uuid4()}@example.com")
    other = get_or_create_user_by_auth_id(db, str(uuid4()), f"{uuid4()}@example.com")
    book = Book(id=uuid4(), title="Original book", author_name="Original author", description="Test book")
    db.add(book)
    db.flush()
    db.add(UserBookStatusModel(user_id=user.id, book_id=str(book.id), status="currently_reading"))
    profile = OnboardingProfile(user_id=user.id, business_model="service", business_stage=BusinessStage.IDEA,
                                biggest_challenge="Finding clients", future_vision="Book five discovery calls")
    db.add(profile)
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app), user, other, book, profile
    app.dependency_overrides.clear()


def create(client, book, **changes):
    response = client.post(ROOT, json=body(book.id, **changes))
    assert response.status_code == 200, response.text
    return response.json()


def update(client, entry, revision=None, **changes):
    fields = {field: entry[field] for field in ("takeaway", "action_text", "goal_context")}
    return client.put(f"{ROOT}/{entry['id']}", json=fields | {"expected_revision": revision or entry["revision"]} | changes)


def test_empty_collection_is_read_only_and_suggests_own_goal(db, notes):
    client, _, other, _, _ = notes
    result = client.get(ROOT).json()
    assert result == {"items": [], "suggested_goal": "Book five discovery calls", "next_cursor": None}
    assert db.query(ReadingTakeaway).count() == 0
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.get(ROOT).json()["suggested_goal"] == ""


def test_create_retry_and_reload_do_not_duplicate(db, notes):
    client, _, _, book, _ = notes
    payload = body(book.id)
    first = client.post(ROOT, json=payload)
    assert first.status_code == 200, first.text
    retry = client.post(ROOT, json=payload)
    assert retry.json() == first.json()
    assert db.query(ReadingTakeaway).count() == 1
    db.expire_all()
    assert client.get(f"{ROOT}/{first.json()['id']}").json() == first.json()
    assert client.get(ROOT).json()["items"] == [first.json()]


def test_same_draft_with_changed_text_reports_saved_entry(db, notes):
    client, _, _, book, _ = notes
    payload = body(book.id)
    first = client.post(ROOT, json=payload).json()
    conflict = client.post(ROOT, json=payload | {"takeaway": "Changed after an uncertain save"})
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["existing_id"] == first["id"]
    assert client.get(f"{ROOT}/{first['id']}").json()["takeaway"] == payload["takeaway"]
    assert db.query(ReadingTakeaway).count() == 1


def test_idea_only_then_add_edit_and_clear_action(db, notes):
    client, _, _, book, _ = notes
    entry = create(client, book, action_text="")
    assert entry["action_text"] == ""
    response = update(client, entry, action_text="Try one call tomorrow", goal_context="Practice listening")
    assert response.status_code == 200, response.text
    saved = response.json()
    assert (saved["action_text"], saved["goal_context"], saved["revision"]) == ("Try one call tomorrow", "Practice listening", 2)
    cleared = update(client, saved, takeaway="Updated insight", action_text="").json()
    assert (cleared["takeaway"], cleared["action_text"], cleared["revision"]) == ("Updated insight", "", 3)


def test_edit_retries_are_safe_and_stale_edits_are_rejected(db, notes):
    client, _, _, book, _ = notes
    entry = create(client, book)
    first = update(client, entry, takeaway="Revised takeaway")
    assert first.status_code == 200
    assert update(client, entry, takeaway="Revised takeaway").json() == first.json()
    assert update(client, entry, action_text="Stale change").status_code == 409
    assert client.get(f"{ROOT}/{entry['id']}").json() == first.json()


def test_book_and_goal_context_survive_profile_catalog_and_shelf_changes(db, notes):
    client, user, _, book, profile = notes
    goal = client.get(ROOT).json()["suggested_goal"]
    entry = create(client, book, goal_context=goal)
    profile.future_vision = "A different goal now"
    book.title = "New catalog title"
    book.author_name = "New catalog author"
    db.query(UserBookStatusModel).filter_by(user_id=user.id).delete()
    db.commit()
    result = client.get(ROOT).json()
    assert result["suggested_goal"] == "A different goal now"
    saved = result["items"][0]
    assert (saved["book_title"], saved["book_author"], saved["goal_context"]) == ("Original book", "Original author", goal)
    assert update(client, entry, action_text="Still useful after pausing the book").status_code == 200
    assert profile.future_vision == "A different goal now"


def test_account_isolation_includes_read_write_and_cursor(db, notes):
    client, user, other, book, _ = notes
    payload = body(book.id)
    entry = client.post(ROOT, json=payload).json()
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.get(ROOT).json()["items"] == []
    assert client.get(f"{ROOT}/{entry['id']}").status_code == 404
    assert update(client, entry, takeaway="Overwrite someone else").status_code == 404
    assert client.get(ROOT, params={"before": entry["id"]}).status_code == 404
    # A client id is private to its reader, so it is not an existence oracle.
    own = client.post(ROOT, json=payload)
    assert own.status_code == 200 and own.json()["id"] != entry["id"]
    app.dependency_overrides[get_current_user] = lambda: user
    assert client.get(ROOT).json()["items"] == [entry]


def test_collection_paginates_without_dropping_entries(db, notes):
    client, _, _, book, _ = notes
    expected = {create(client, book, takeaway=f"Idea {n}")["id"] for n in range(5)}
    found = []
    cursor = None
    while True:
        params = {"limit": 2} | ({"before": cursor} if cursor else {})
        result = client.get(ROOT, params=params).json()
        found.extend(entry["id"] for entry in result["items"])
        cursor = result["next_cursor"]
        if cursor is None:
            break
    assert len(found) == 5 and set(found) == expected
    assert client.get(ROOT, params={"limit": 101}).status_code == 422
    assert client.get(ROOT, params={"before": str(uuid4())}).status_code == 404


def test_invalid_book_or_reassignment_does_not_change_data(db, notes):
    client, _, _, book, _ = notes
    assert client.post(ROOT, json=body()).status_code == 404
    assert db.query(ReadingTakeaway).count() == 0
    entry = create(client, book)
    assert update(client, entry, book_id=str(uuid4())).status_code == 422
    assert update(client, entry, goal_context=" \n ").status_code == 422
    assert client.get(f"{ROOT}/{entry['id']}").json() == entry


def test_failed_create_and_update_commit_preserve_saved_state(db, notes, monkeypatch):
    client, _, _, book, _ = notes
    payload = body(book.id)
    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", Mock(side_effect=RuntimeError("test failure")))
        assert client.post(ROOT, json=payload).status_code == 500
    assert db.query(ReadingTakeaway).count() == 0
    entry = client.post(ROOT, json=payload).json()
    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", Mock(side_effect=RuntimeError("test failure")))
        assert update(client, entry, takeaway="Should not persist").status_code == 500
    assert client.get(f"{ROOT}/{entry['id']}").json() == entry


def test_takeaways_do_not_create_reading_credit_or_complete_book(db, notes):
    client, user, _, book, _ = notes
    create(client, book)
    assert db.query(ReadingLog).count() == db.query(ReadingProgress).count() == 0
    assert db.query(ReadingHistoryEntry).count() == 0
    assert db.query(UserBookStatusModel).filter_by(user_id=user.id).one().status == "currently_reading"
    assert client.get("/api/reading/rewards").json()["total_points"] == 0


def test_takeaway_routes_require_auth():
    client = TestClient(app)
    for response in (client.get(ROOT), client.get(f"{ROOT}/{uuid4()}"), client.post(ROOT, json=body()),
                     client.put(f"{ROOT}/{uuid4()}", json={"takeaway": "Idea", "goal_context": "Goal", "expected_revision": 1})):
        assert response.status_code in (401, 403)


def test_takeaway_migration_upgrade_and_downgrade(db, monkeypatch):
    connection = db.connection()
    schema = "rd56_" + uuid4().hex
    previous = connection.execute(text("SELECT current_setting('search_path')")).scalar_one()
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connection.execute(text("SELECT set_config('search_path', :path, true)"), {"path": schema})
    try:
        connection.execute(text("CREATE TABLE users (id UUID PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE books (id UUID PRIMARY KEY)"))
        path = Path(__file__).parents[1] / "alembic/versions/d0e1f2a3b4c5_add_reading_takeaways.py"
        spec = importlib.util.spec_from_file_location("rd56_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        inspector = inspect(connection)
        assert len(inspector.get_check_constraints("reading_takeaways", schema=schema)) == 4
        assert any(c["column_names"] == ["user_id", "client_id"] for c in inspector.get_unique_constraints("reading_takeaways", schema=schema))
        assert any(c["name"] == "ix_reading_takeaway_user_created" for c in inspector.get_indexes("reading_takeaways", schema=schema))
        user, book = uuid4(), uuid4()
        connection.execute(text("INSERT INTO users (id) VALUES (:id)"), {"id": user})
        connection.execute(text("INSERT INTO books (id) VALUES (:id)"), {"id": book})
        connection.execute(text("INSERT INTO reading_takeaways (id,user_id,book_id,client_id,book_title,book_author,takeaway,goal_context) VALUES (:id,:user,:book,:client,'Book','Author','Idea','Goal')"), dict(id=uuid4(), user=user, book=book, client=uuid4()))
        row = connection.execute(text("SELECT action_text, revision FROM reading_takeaways")).one()
        assert tuple(row) == ("", 1)
        migration.downgrade()
        assert set(inspect(connection).get_table_names(schema=schema)) == {"users", "books"}
        assert connection.execute(text("SELECT count(*) FROM books")).scalar_one() == 1
    finally:
        connection.execute(text("SELECT set_config('search_path', :path, true)"), {"path": previous})
