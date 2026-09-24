"""RD-57: a reader's action/result loop, private history and safe concurrent edits."""
import importlib.util
from datetime import date
from pathlib import Path
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
from app.models import Book, ReadingReflection, ReadingTakeaway, ReadingLog, ReadingHistoryEntry, UserBookStatusModel
from app.schemas.reading_reflections import ReflectionCreate

ROOT = '/api/reading/takeaways'


def payload(revision=1, **changes):
    return dict(client_id=str(uuid4()), expected_revision=revision, attempted_on='2026-01-01',
                outcome='mixed', result='One customer answered. The example was useful.',
                next_step='Ask one more customer.', completed=False) | changes


@pytest.mark.parametrize('changes', [
    {'result': ' \n '}, {'result': 'x' * 4001}, {'result': None}, {'result': 5},
    {'outcome': 'unknown'}, {'completed': 'true'}, {'expected_revision': True},
    {'expected_revision': 0}, {'next_step': ''}, {'next_step': ' \t '},
    {'next_step': 'x' * 2001}, {'attempted_on': 'bad-date'}, {'action_snapshot': 'forged'},
])
def test_invalid_reflection_is_rejected(changes):
    with pytest.raises(ValidationError):
        ReflectionCreate(**payload(**changes))


def test_completed_reflection_can_omit_next_step_and_preserves_reader_formatting():
    saved = ReflectionCreate(**payload(completed=True, next_step='', result='  First line\nSecond line  '))
    assert saved.result == 'First line\nSecond line'
    assert saved.next_step == ''


@pytest.fixture
def actions(db):
    user = get_or_create_user_by_auth_id(db, str(uuid4()), f'{uuid4()}@example.com')
    other = get_or_create_user_by_auth_id(db, str(uuid4()), f'{uuid4()}@example.com')
    book = Book(id=uuid4(), title='Learning by doing', author_name='A Writer', description='Test book')
    db.add(book)
    db.flush()
    db.add(UserBookStatusModel(user_id=user.id, book_id=str(book.id), status='currently_reading'))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app), user, other, book
    app.dependency_overrides.clear()


def create(client, book, **changes):
    response = client.post(ROOT, json=dict(book_id=str(book.id), client_id=str(uuid4()), takeaway='Use concrete examples.',
                                          action_text='Ask two customers.', goal_context='Explain our value clearly.') | changes)
    assert response.status_code == 200, response.text
    return response.json()


def attempt(client, entry, **changes):
    response = client.post(f"{ROOT}/{entry['id']}/reflections", json=payload(entry['revision'], **changes))
    assert response.status_code == 200, response.text
    return response.json()


def correct(client, saved, **changes):
    row, entry = saved['reflection'], saved['takeaway']
    fields = {key: row[key] for key in ('attempted_on', 'outcome', 'result', 'next_step', 'completed')}
    return client.put(f"{ROOT}/{entry['id']}/reflections/{row['id']}", json=fields | {'expected_revision': entry['revision']} | changes)


def note_edit(client, entry, **changes):
    fields = {key: entry[key] for key in ('takeaway', 'action_text', 'goal_context')}
    return client.put(f"{ROOT}/{entry['id']}", json=fields | {'expected_revision': entry['revision']} | changes)


def test_attempts_keep_context_and_advance_the_plan(db, actions):
    client, _, _, book = actions
    entry = create(client, book)
    assert (entry['action_status'], entry['reflection_count'], entry['next_step']) == ('pending', 0, '')
    first = attempt(client, entry)
    row = first['reflection']
    assert (row['action_snapshot'], row['goal_snapshot'], row['takeaway_snapshot']) == (entry['action_text'], entry['goal_context'], entry['takeaway'])
    assert (first['takeaway']['revision'], first['takeaway']['reflection_count']) == (2, 1)
    second = attempt(client, first['takeaway'], completed=True, next_step='', outcome='helped')
    assert second['reflection']['action_snapshot'] == first['reflection']['next_step']
    assert second['takeaway']['action_status'] == 'completed'
    db.expire_all()
    history = client.get(f"{ROOT}/{entry['id']}/reflections").json()
    assert [row['sequence'] for row in history['items']] == [2, 1]
    assert history['items'][1] == first['reflection']
    bundle = client.get(f"{ROOT}/{entry['id']}/reflections/{row['id']}").json()
    assert bundle == {'takeaway': second['takeaway'], 'reflection': first['reflection']}


def test_retry_and_changed_retry_never_duplicate_attempt(db, actions):
    client, _, _, book = actions
    entry = create(client, book)
    body = payload()
    url = f"{ROOT}/{entry['id']}/reflections"
    first = client.post(url, json=body).json()
    assert client.post(url, json=body).json() == first
    conflict = client.post(url, json=body | {'result': 'Changed after a lost response'})
    assert conflict.status_code == 409
    assert conflict.json()['detail']['existing_id'] == first['reflection']['id']
    assert db.query(ReadingReflection).count() == 1
    assert db.query(ReadingTakeaway).one().reflection_count == 1


def test_latest_correction_updates_plan_and_identical_retry_is_safe(db, actions):
    client, _, _, book = actions
    saved = attempt(client, create(client, book))
    changes = {'result': 'Actually, both replied.', 'completed': True, 'next_step': ''}
    corrected = correct(client, saved, **changes)
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()['takeaway']['action_status'] == 'completed'
    assert correct(client, saved, **changes).json() == corrected.json()
    assert db.query(ReadingReflection).count() == 1
    assert db.query(ReadingTakeaway).one().revision == 3


def test_historical_correction_does_not_replace_newer_plan(db, actions):
    client, _, _, book = actions
    first = attempt(client, create(client, book))
    second = attempt(client, first['takeaway'], next_step='Try a clearer example.')
    correction = correct(client, {'takeaway': second['takeaway'], 'reflection': first['reflection']}, completed=True, next_step='')
    assert correction.status_code == 200
    assert correction.json()['takeaway']['next_step'] == 'Try a clearer example.'
    assert correction.json()['takeaway']['action_status'] == 'pending'
    assert correction.json()['takeaway']['reflection_count'] == 2


def test_reopen_is_retry_safe_and_old_completion_correction_cannot_recomplete(db, actions):
    client, _, _, book = actions
    saved = attempt(client, create(client, book), completed=True, next_step='')
    entry = saved['takeaway']
    url = f"{ROOT}/{entry['id']}/reopen"
    body = {'expected_revision': entry['revision']}
    reopened = client.put(url, json=body)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()['action_status'] == 'pending'
    assert client.put(url, json=body).json() == reopened.json()
    correction = correct(client, saved | {'takeaway': reopened.json()}, result='Corrected result')
    assert correction.json()['takeaway']['action_status'] == 'pending'
    assert correction.json()['takeaway']['reflection_count'] == 1
    new = attempt(client, correction.json()['takeaway'])
    assert new['takeaway']['reflection_count'] == 2


@pytest.mark.parametrize('changes', [{'action_text': 'Try a workshop.'}, {'action_text': ''}, {'goal_context': 'Build confidence.'}, {'takeaway': 'A refined idea.'}])
def test_revised_context_survives_corrections_to_past_results(db, actions, changes):
    client, _, _, book = actions
    saved = attempt(client, create(client, book))
    revised = note_edit(client, saved['takeaway'], **changes).json()
    corrected = correct(client, saved | {'takeaway': revised}, completed=True, next_step='')
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()['takeaway']['action_status'] == revised['action_status']
    assert corrected.json()['takeaway']['next_step'] == revised['next_step']
    assert corrected.json()['reflection']['action_snapshot'] == saved['reflection']['action_snapshot']
    assert corrected.json()['reflection']['goal_snapshot'] == saved['reflection']['goal_snapshot']


def test_stale_writes_cannot_replace_newer_note_or_reflection(db, actions):
    client, _, _, book = actions
    entry = create(client, book)
    first = attempt(client, entry)
    assert client.post(f"{ROOT}/{entry['id']}/reflections", json=payload()).status_code == 409
    assert note_edit(client, entry, takeaway='Stale edit').status_code == 409
    second = attempt(client, first['takeaway'], completed=True, next_step='')
    assert correct(client, first, result='Stale correction').status_code == 409
    assert client.put(f"{ROOT}/{entry['id']}/reopen", json={'expected_revision': 1}).status_code == 409
    assert client.get(f"{ROOT}/{entry['id']}").json() == second['takeaway']


def test_idea_and_completed_actions_require_an_open_action(db, actions):
    client, _, _, book = actions
    idea = create(client, book, action_text='')
    assert idea['action_status'] == 'idea'
    assert client.post(f"{ROOT}/{idea['id']}/reflections", json=payload()).status_code == 409
    assert client.put(f"{ROOT}/{idea['id']}/reopen", json={'expected_revision': 1}).status_code == 409
    saved = attempt(client, create(client, book), completed=True, next_step='')
    entry = saved['takeaway']
    assert client.post(f"{ROOT}/{entry['id']}/reflections", json=payload(entry['revision'])).status_code == 409
    assert db.query(ReadingReflection).count() == 1


def test_filters_apply_before_pagination_and_history_pages_are_stable(db, actions):
    client, _, _, book = actions
    pending = [create(client, book) for _ in range(3)]
    ideas = [create(client, book, action_text='') for _ in range(2)]
    completed = attempt(client, create(client, book), completed=True, next_step='')['takeaway']
    for state, expected in [('pending', pending), ('idea', ideas), ('completed', [completed])]:
        found, cursor = [], None
        while True:
            response = client.get(ROOT, params={'state': state, 'limit': 1} | ({'before': cursor} if cursor else {})).json()
            found.extend(row['id'] for row in response['items'])
            cursor = response['next_cursor']
            if cursor is None:
                break
        assert len(found) == len(expected) and set(found) == {row['id'] for row in expected}
    assert client.get(ROOT, params={'state': 'bad'}).status_code == 422
    entry = pending[0]
    for _ in range(3):
        entry = attempt(client, entry)['takeaway']
    url = f"{ROOT}/{entry['id']}/reflections"
    first = client.get(url, params={'limit': 2}).json()
    second = client.get(url, params={'limit': 2, 'before': first['next_before']}).json()
    assert [row['sequence'] for row in first['items'] + second['items']] == [3, 2, 1]
    assert second['next_before'] is None
    assert client.get(url, params={'before': 0}).status_code == 422


def test_ownership_includes_history_corrections_reopen_and_cross_parent_ids(db, actions):
    client, user, other, book = actions
    first = attempt(client, create(client, book))
    entry, row = first['takeaway'], first['reflection']
    second = create(client, book)
    cross = client.get(f"{ROOT}/{second['id']}/reflections/{row['id']}")
    assert cross.status_code == 404
    assert correct(client, first | {'takeaway': second}, result='Wrong parent').status_code == 404
    app.dependency_overrides[get_current_user] = lambda: other
    base = f"{ROOT}/{entry['id']}"
    for response in [client.get(base + '/reflections'), client.get(base + '/reflections/' + row['id']),
                     client.post(base + '/reflections', json=payload()), correct(client, first, result='Not mine'),
                     client.put(base + '/reopen', json={'expected_revision': entry['revision']})]:
        assert response.status_code == 404, response.text
    for state in ['pending', 'completed', 'idea']:
        assert client.get(ROOT, params={'state': state}).json()['items'] == []
    app.dependency_overrides[get_current_user] = lambda: user
    assert client.get(base).json() == entry


def test_future_attempt_and_timezone_are_checked_on_create_and_correction(db, actions, monkeypatch):
    client, _, _, book = actions
    entry = create(client, book)
    url = f"{ROOT}/{entry['id']}/reflections"
    assert client.post(url, params={'tz': 'Not/AZone'}, json=payload()).status_code == 422
    # The route must use the requested local calendar, not the server's UTC date.
    def local_day(tz):
        return date(2026, 1, 2) if tz == 'Pacific/Kiritimati' else date(2026, 1, 1)
    monkeypatch.setattr('app.routers.reading_reflections.local_today', local_day)
    assert client.post(url, json=payload(attempted_on='2026-01-02')).status_code == 422
    saved = client.post(url, params={'tz': 'Pacific/Kiritimati'}, json=payload(attempted_on='2026-01-02')).json()
    assert saved['reflection']['attempted_on'] == '2026-01-02'
    assert correct(client, saved, attempted_on='2026-01-03').status_code == 422
    assert db.query(ReadingReflection).count() == 1


def test_commit_failure_rolls_back_history_and_action_together(db, actions, monkeypatch):
    client, _, _, book = actions
    entry = create(client, book)
    with monkeypatch.context() as patch:
        patch.setattr(db, 'commit', Mock(side_effect=RuntimeError('test failure')))
        response = client.post(f"{ROOT}/{entry['id']}/reflections", json=payload(completed=True, next_step=''))
        assert response.status_code == 500
    assert client.get(f"{ROOT}/{entry['id']}").json() == entry
    assert db.query(ReadingReflection).count() == 0
    saved = attempt(client, entry, completed=True, next_step='')
    with monkeypatch.context() as patch:
        patch.setattr(db, 'commit', Mock(side_effect=RuntimeError('test failure')))
        assert correct(client, saved, result='Must not persist').status_code == 500
    assert client.get(f"{ROOT}/{entry['id']}/reflections").json()['items'] == [saved['reflection']]
    with monkeypatch.context() as patch:
        patch.setattr(db, 'commit', Mock(side_effect=RuntimeError('test failure')))
        assert client.put(f"{ROOT}/{entry['id']}/reopen", json={'expected_revision': saved['takeaway']['revision']}).status_code == 500
    assert client.get(f"{ROOT}/{entry['id']}").json() == saved['takeaway']


def test_reflections_do_not_award_reading_points_or_complete_the_book(db, actions):
    client, user, _, book = actions
    attempt(client, create(client, book), completed=True, next_step='')
    assert db.query(ReadingLog).count() == db.query(ReadingHistoryEntry).count() == 0
    assert db.query(UserBookStatusModel).filter_by(user_id=user.id).one().status == 'currently_reading'
    assert client.get('/api/reading/rewards').json()['total_points'] == 0


def test_reflection_routes_require_auth():
    client = TestClient(app)
    url = f'{ROOT}/{uuid4()}'
    fields = payload()
    fields.pop('client_id')
    for response in [client.get(url + '/reflections'), client.get(url + '/reflections/' + str(uuid4())),
                     client.post(url + '/reflections', json=payload()), client.put(url + '/reflections/' + str(uuid4()), json=fields),
                     client.put(url + '/reopen', json={'expected_revision': 1})]:
        assert response.status_code in (401, 403)


def test_migration_preserves_existing_notes_and_downgrade_retains_them(db, monkeypatch):
    connection = db.connection()
    schema = 'rd57_' + uuid4().hex
    previous = connection.execute(text("SELECT current_setting('search_path')")).scalar_one()
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connection.execute(text("SELECT set_config('search_path', :path, true)"), {'path': schema})
    try:
        connection.execute(text('CREATE TABLE users (id UUID PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE books (id UUID PRIMARY KEY)'))
        migrations = []
        for filename in ['d0e1f2a3b4c5_add_reading_takeaways.py', 'e1f2a3b4c5d6_add_action_reflections.py']:
            path = Path(__file__).parents[1] / 'alembic/versions' / filename
            spec = importlib.util.spec_from_file_location(filename[:-3], path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
            migrations.append(migration)
        migrations[0].upgrade()
        user, book = uuid4(), uuid4()
        connection.execute(text('INSERT INTO users (id) VALUES (:id)'), {'id': user})
        connection.execute(text('INSERT INTO books (id) VALUES (:id)'), {'id': book})
        for action in ['', 'Try this']:
            connection.execute(text("INSERT INTO reading_takeaways (id,user_id,book_id,client_id,book_title,book_author,takeaway,goal_context,action_text) VALUES (:id,:user,:book,:client,'Book','Author','Idea','Goal',:action)"), dict(id=uuid4(), user=user, book=book, client=uuid4(), action=action))
        migrations[1].upgrade()
        rows = connection.execute(text('SELECT action_text,action_completed,next_step,action_generation,reflection_count FROM reading_takeaways ORDER BY action_text')).all()
        assert [tuple(row) for row in rows] == [('', False, '', 1, 0), ('Try this', False, '', 1, 0)]
        inspector = inspect(connection)
        assert len(inspector.get_check_constraints('reading_reflections', schema=schema)) == 4
        assert len(inspector.get_unique_constraints('reading_reflections', schema=schema)) == 2
        assert connection.execute(text('SELECT count(*) FROM reading_reflections')).scalar_one() == 0
        migrations[1].downgrade()
        assert 'reading_reflections' not in inspect(connection).get_table_names(schema=schema)
        assert connection.execute(text('SELECT takeaway,goal_context FROM reading_takeaways')).all() == [('Idea', 'Goal'), ('Idea', 'Goal')]
        assert 'action_completed' not in {col['name'] for col in inspect(connection).get_columns('reading_takeaways', schema=schema)}
    finally:
        connection.execute(text("SELECT set_config('search_path', :path, true)"), {'path': previous})
