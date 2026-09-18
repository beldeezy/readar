"""RD-58: consent, private pairing, durable exits and concurrent queue safety."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import Response
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.user_helpers import get_or_create_user_by_auth_id
from app.database import get_db
from app.main import app
from app.models import Book, FriendlyPair, FriendlyParticipation, ReadingLog, ReadingTakeaway, User, UserBookStatusModel
from app.routers.friendly_pairing import join_pairing
from app.schemas.friendly_pairing import JoinPairing

ROOT = '/api/reading/competition'


def join_body(book_id=None, revision=0, **changes):
    return dict(request_id=str(uuid4()), expected_revision=revision, reading_name='Page Turner',
                book_id=str(book_id or uuid4()), share_with_partner=True) | changes


def leave_body(state, **changes):
    return dict(request_id=str(uuid4()), expected_revision=state['revision']) | changes


@pytest.mark.parametrize('changes', [
    {'reading_name': ''}, {'reading_name': ' \n '}, {'reading_name': 'x' * 33},
    {'reading_name': 'email@example.com'}, {'reading_name': 'Name\nName'}, {'reading_name': 'Name\u202ename'},
    {'reading_name': 5}, {'share_with_partner': False}, {'share_with_partner': 'true'},
    {'expected_revision': True}, {'expected_revision': -1}, {'user_id': str(uuid4())},
    {'partner_id': str(uuid4())}, {'book_id': 'bad'},
])
def test_invalid_pairing_input_is_rejected(changes):
    with pytest.raises(ValidationError):
        JoinPairing(**join_body(**changes))


def test_consent_is_required_and_name_is_normalized():
    body = join_body(reading_name='  María Reader  ')
    assert JoinPairing(**body).reading_name == 'María Reader'
    body.pop('share_with_partner')
    with pytest.raises(ValidationError):
        JoinPairing(**body)


@pytest.fixture
def readers(db):
    users = [get_or_create_user_by_auth_id(db, str(uuid4()), f'{uuid4()}@example.com') for _ in range(3)]
    books = [Book(id=uuid4(), title=f'Book {i}', author_name=f'Author {i}', description='Test book', external_id=f'legacy-{uuid4()}') for i in range(3)]
    db.add_all(books)
    db.flush()
    db.add_all([UserBookStatusModel(user_id=user.id, book_id=str(book.id), status='currently_reading') for user, book in zip(users, books)])
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: users[0]
    yield TestClient(app), users, books
    app.dependency_overrides.clear()


def as_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


def join(client, user, book, revision=0, **changes):
    as_user(user)
    response = client.post(ROOT + '/join', json=join_body(book.id, revision, **changes))
    assert response.status_code == 200, response.text
    return response.json()


def status(client, user):
    as_user(user)
    response = client.get(ROOT)
    assert response.status_code == 200, response.text
    return response.json()


def test_get_is_read_only_and_never_enrols_a_reader(db, readers):
    client, users, _ = readers
    for user in users:
        data = status(client, user)
        assert data['status'] == 'inactive' and data['revision'] == 0
        assert data['you'] is data['partner'] is data['pairing_id'] is None
    assert db.query(FriendlyParticipation).count() == db.query(FriendlyPair).count() == 0
    assert client.get(ROOT).headers['cache-control'] == 'no-store, private'


def test_join_waits_then_pairs_different_books_and_reload_is_durable(db, readers):
    client, users, books = readers
    waiting = join(client, users[0], books[0], reading_name='First Reader')
    assert waiting['status'] == 'waiting' and waiting['queued_at']
    assert waiting['partner'] is None and waiting['revision'] == 1
    paired = join(client, users[1], books[1], reading_name='Second Reader')
    assert paired['status'] == 'paired' and paired['queued_at'] is None
    assert paired['partner'] == dict(reading_name='First Reader', book_title=books[0].title, book_author=books[0].author_name)
    db.expire_all()
    first = status(client, users[0])
    assert first['status'] == 'paired' and first['revision'] == 2
    assert first['pairing_id'] == paired['pairing_id']
    assert first['partner'] == paired['you']
    assert status(client, users[1]) == paired
    assert db.query(FriendlyPair).count() == 1


def test_pairing_payload_is_an_allowlist_not_account_or_private_reading_data(db, readers):
    client, users, books = readers
    db.add(ReadingTakeaway(user_id=users[0].id, book_id=books[0].id, client_id=uuid4(), book_title=books[0].title,
                           book_author=books[0].author_name, takeaway='PRIVATE TAKEAWAY', goal_context='PRIVATE GOAL', action_text='PRIVATE ACTION'))
    db.commit()
    join(client, users[0], books[0], reading_name='Alias')
    paired = join(client, users[1], books[1])
    assert set(paired['partner']) == {'reading_name', 'book_title', 'book_author'}
    encoded = str(paired)
    for private in [users[0].email, str(users[0].id), users[0].auth_user_id, 'PRIVATE TAKEAWAY', 'PRIVATE GOAL', 'PRIVATE ACTION']:
        assert private not in encoded
    outsider = status(client, users[2])
    assert outsider['partner'] is None and outsider['pairing_id'] is None
    assert client.get(ROOT + '/' + paired['pairing_id']).status_code == 404
    assert client.post(ROOT + '/leave', json=leave_body(outsider) | {'user_id': str(users[0].id)}).status_code == 422
    assert status(client, users[0])['status'] == 'paired'


def test_only_own_started_book_is_eligible_including_legacy_ids(db, readers):
    client, users, books = readers
    assert client.post(ROOT + '/join', json=join_body()).status_code == 404
    assert client.post(ROOT + '/join', json=join_body(books[1].id)).status_code == 409
    own_shelf = db.query(UserBookStatusModel).filter_by(user_id=users[0].id).one()
    own_shelf.status = 'reading_next'
    db.commit()
    assert client.post(ROOT + '/join', json=join_body(books[0].id)).status_code == 409
    assert db.query(FriendlyParticipation).count() == 0
    own_shelf.status, own_shelf.book_id = 'currently_reading', books[0].external_id
    db.commit()
    assert join(client, users[0], books[0])['status'] == 'waiting'


def test_same_request_retry_and_changed_retry_cannot_duplicate_or_change_consent(db, readers):
    client, users, books = readers
    body = join_body(books[0].id)
    first = client.post(ROOT + '/join', json=body).json()
    assert client.post(ROOT + '/join', json=body).json() == first
    assert client.post(ROOT + '/join', json=body | {'reading_name': 'Changed'}).status_code == 409
    assert client.post(ROOT + '/join', json=join_body(books[0].id)).status_code == 409
    assert db.query(FriendlyParticipation).count() == 1
    join(client, users[1], books[1])
    as_user(users[0])
    retry = client.post(ROOT + '/join', json=body).json()
    assert retry['status'] == 'paired'
    assert db.query(FriendlyPair).count() == 1


def test_cancel_waiting_is_idempotent_and_old_join_cannot_restart_search(db, readers):
    client, users, books = readers
    body = join_body(books[0].id)
    waiting = client.post(ROOT + '/join', json=body).json()
    leave = leave_body(waiting)
    stopped = client.post(ROOT + '/leave', json=leave)
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()['status'] == 'inactive'
    assert stopped.json()['queued_at'] is stopped.json()['partner'] is None
    assert client.post(ROOT + '/leave', json=leave).json() == stopped.json()
    assert client.post(ROOT + '/join', json=body).status_code == 409
    assert join(client, users[1], books[1])['status'] == 'waiting'
    assert db.query(FriendlyPair).count() == 0


def test_either_partner_can_leave_sharing_stops_and_neither_is_requeued(db, readers):
    client, users, books = readers
    original = join_body(books[0].id)
    client.post(ROOT + '/join', json=original)
    second = join(client, users[1], books[1])
    leave = leave_body(second)
    ended = client.post(ROOT + '/leave', json=leave).json()
    assert ended['status'] == 'ended' and ended['ended_by_you'] is True
    assert ended['partner'] is None
    assert client.post(ROOT + '/leave', json=leave).json() == ended
    first = status(client, users[0])
    assert first['status'] == 'ended' and first['ended_by_you'] is False
    assert first['partner'] is None
    # This original join was the remaining reader's last command. Retry returns
    # the ended state, never recreates consent or reveals the former partner.
    assert client.post(ROOT + '/join', json=original).json() == first
    assert join(client, users[2], books[2])['status'] == 'waiting'
    assert db.query(FriendlyParticipation).filter_by(status='waiting').count() == 1
    assert db.query(FriendlyPair).one().ended_at is not None


def test_fresh_opt_in_after_departure_pairs_again_but_old_leave_cannot_end_new_pair(db, readers):
    client, users, books = readers
    join(client, users[0], books[0])
    second = join(client, users[1], books[1])
    old_leave = leave_body(second)
    ended = client.post(ROOT + '/leave', json=old_leave).json()
    waiting = join(client, users[2], books[2])
    new = join(client, users[1], books[1], ended['revision'], reading_name='New name')
    assert new['pairing_id'] != second['pairing_id']
    assert new['partner'] == waiting['you']
    assert client.post(ROOT + '/leave', json=old_leave).status_code == 409
    assert status(client, users[1]) == new
    assert status(client, users[0])['partner'] is None
    assert db.query(FriendlyPair).count() == 2


def test_stale_cancel_after_match_requires_fresh_choice(db, readers):
    client, users, books = readers
    waiting = join(client, users[0], books[0])
    join(client, users[1], books[1])
    as_user(users[0])
    assert client.post(ROOT + '/leave', json=leave_body(waiting)).status_code == 409
    latest = status(client, users[0])
    assert latest['status'] == 'paired'
    assert client.post(ROOT + '/leave', json=leave_body(latest)).json()['status'] == 'ended'


def test_waiting_candidate_is_oldest_and_only_active_opt_ins_are_matched(db, readers):
    client, users, books = readers
    now = datetime.now(timezone.utc)
    # Seed a valid queue backlog to verify ordering; normal join pairs immediately.
    for i in (0, 1):
        db.add(FriendlyParticipation(user_id=users[i].id, status='waiting', revision=1, reading_name=f'Reader {i}',
                                    book_id=books[i].id, book_title=books[i].title, book_author=books[i].author_name,
                                    consented_at=now, queued_at=now - timedelta(days=2-i)))
    db.commit()
    paired = join(client, users[2], books[2])
    assert paired['partner']['reading_name'] == 'Reader 0'
    assert status(client, users[1])['status'] == 'waiting'
    assert status(client, users[0])['status'] == 'paired'


def test_shared_details_are_snapshots_until_reader_leaves_and_opts_in_again(db, readers):
    client, users, books = readers
    first = join(client, users[0], books[0], reading_name='Chosen nickname')
    original_title = books[0].title
    books[0].title = 'Changed catalog title'
    db.query(UserBookStatusModel).filter_by(user_id=users[0].id).one().status = 'reading_next'
    db.commit()
    second = join(client, users[1], books[1])
    assert second['partner']['book_title'] == original_title
    assert second['partner']['reading_name'] == first['you']['reading_name']


def test_failed_match_rolls_back_both_readers_and_pair_creation(db, readers, monkeypatch):
    client, users, books = readers
    waiting = join(client, users[0], books[0])
    as_user(users[1])
    with monkeypatch.context() as patch:
        patch.setattr(db, 'commit', Mock(side_effect=RuntimeError('test failure')))
        assert client.post(ROOT + '/join', json=join_body(books[1].id)).status_code == 500
    assert status(client, users[0]) == waiting
    assert status(client, users[1])['status'] == 'inactive'
    assert db.query(FriendlyPair).count() == 0


def test_failed_leave_rolls_back_both_readers_and_pair_end(db, readers, monkeypatch):
    client, users, books = readers
    join(client, users[0], books[0])
    paired = join(client, users[1], books[1])
    with monkeypatch.context() as patch:
        patch.setattr(db, 'commit', Mock(side_effect=RuntimeError('test failure')))
        assert client.post(ROOT + '/leave', json=leave_body(paired)).status_code == 500
    assert status(client, users[1]) == paired
    assert status(client, users[0])['status'] == 'paired'
    assert db.query(FriendlyPair).one().ended_at is None


def test_pairing_does_not_change_progress_rewards_or_book_status(db, readers):
    client, users, books = readers
    join(client, users[0], books[0])
    paired = join(client, users[1], books[1])
    client.post(ROOT + '/leave', json=leave_body(paired))
    assert db.query(ReadingLog).count() == 0
    assert client.get('/api/reading/rewards').json()['total_points'] == 0
    assert {row.status for row in db.query(UserBookStatusModel).all()} == {'currently_reading'}


def test_pairing_routes_require_auth():
    client = TestClient(app)
    for response in (client.get(ROOT), client.post(ROOT + '/join', json=join_body()),
                     client.post(ROOT + '/leave', json={'request_id': str(uuid4()), 'expected_revision': 0})):
        assert response.status_code in (401, 403)


@pytest.mark.parametrize('same_reader', [False, True])
def test_concurrent_join_requests_cannot_claim_a_reader_twice(engine, same_reader):
    """Real independent transactions, not a shared test-session mock."""
    user_ids, book_ids = [uuid4() for _ in range(3)], [uuid4() for _ in range(3)]
    bodies = [JoinPairing(**join_body(book_id)) for book_id in book_ids]
    try:
        with Session(engine) as db:
            db.add_all([User(id=user_id, auth_user_id=str(uuid4()), email=f'{uuid4()}@example.com') for user_id in user_ids])
            db.add_all([Book(id=book_id, title='Concurrent book', author_name='Writer', description='Test') for book_id in book_ids])
            db.flush()
            db.add_all([UserBookStatusModel(user_id=user_id, book_id=str(book_id), status='currently_reading') for user_id, book_id in zip(user_ids, book_ids)])
            db.commit()
        barrier = Barrier(3)
        def submit(index):
            barrier.wait(timeout=10)
            with Session(engine, autoflush=False) as db:
                return join_pairing(bodies[index], Response(), SimpleNamespace(id=user_ids[index]), db)
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(submit, 0 if same_reader else index) for index in range(3)]
            results = [future.result(timeout=15) for future in futures]
        with Session(engine) as db:
            rows = db.query(FriendlyParticipation).filter(FriendlyParticipation.user_id.in_(user_ids)).all()
            pairs = db.query(FriendlyPair).filter(FriendlyPair.first_user_id.in_(user_ids)).all()
            if same_reader:
                assert len(rows) == 1 and rows[0].status == 'waiting' and len(pairs) == 0
                assert len({result.revision for result in results}) == 1
            else:
                assert len(pairs) == 1
                assert sorted(row.status for row in rows) == ['paired', 'paired', 'waiting']
                assert len({row.user_id for row in rows}) == 3
                paired_ids = {row.user_id for row in rows if row.status == 'paired'}
                assert paired_ids == {pairs[0].first_user_id, pairs[0].second_user_id}
    finally:
        with Session(engine) as db:
            db.query(FriendlyParticipation).filter(FriendlyParticipation.user_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(FriendlyPair).filter(FriendlyPair.first_user_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(UserBookStatusModel).filter(UserBookStatusModel.user_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(Book).filter(Book.id.in_(book_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
            db.commit()


def test_pairing_migration_upgrade_constraints_and_downgrade(db, monkeypatch):
    connection = db.connection()
    schema = 'rd58_' + uuid4().hex
    previous = connection.execute(text("SELECT current_setting('search_path')")).scalar_one()
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connection.execute(text("SELECT set_config('search_path', :path, true)"), {'path': schema})
    try:
        connection.execute(text('CREATE TABLE users (id UUID PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE books (id UUID PRIMARY KEY)'))
        path = Path(__file__).parents[1] / 'alembic/versions/f2a3b4c5d6e7_add_friendly_pairing.py'
        spec = importlib.util.spec_from_file_location('rd58_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        inspector = inspect(connection)
        assert len(inspector.get_check_constraints('friendly_pairs', schema=schema)) == 2
        assert len(inspector.get_check_constraints('friendly_participations', schema=schema)) == 4
        assert inspector.get_pk_constraint('friendly_participations', schema=schema)['constrained_columns'] == ['user_id']
        assert any(row['name'] == 'ix_friendly_waiting' for row in inspector.get_indexes('friendly_participations', schema=schema))
        user = uuid4()
        connection.execute(text('INSERT INTO users (id) VALUES (:id)'), {'id': user})
        connection.execute(text('INSERT INTO friendly_participations (user_id) VALUES (:id)'), {'id': user})
        assert tuple(connection.execute(text('SELECT status, revision, consented_at FROM friendly_participations')).one()) == ('inactive', 0, None)
        assert connection.execute(text('SELECT count(*) FROM friendly_pairs')).scalar_one() == 0
        migration.downgrade()
        assert set(inspect(connection).get_table_names(schema=schema)) == {'users', 'books'}
        assert connection.execute(text('SELECT count(*) FROM users')).scalar_one() == 1
    finally:
        connection.execute(text("SELECT set_config('search_path', :path, true)"), {'path': previous})
