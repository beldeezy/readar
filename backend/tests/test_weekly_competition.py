"""RD-59: consistency-first rounds, explicit sharing and durable results."""
from datetime import date, datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
from zoneinfo import ZoneInfo

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
from app.models import Book, FriendlyPair, FriendlyParticipation, FriendlyRound, ReadingLog, ReadingProgress, UserBookStatusModel
from app.schemas.weekly_competition import CompetitionConsent
from app.services import weekly_competition as weekly

ROOT = '/api/reading/competition'


def consent_body(state, tz='UTC', **changes):
    return dict(request_id=str(uuid4()), expected_revision=state['revision'],
                expected_reading_revision=state.get('reading_revision') or 0, timezone=tz, share_progress=True) | changes


@pytest.mark.parametrize('changes', [
    {'share_progress': False}, {'share_progress': 'true'}, {'expected_reading_revision': True},
    {'expected_reading_revision': -1}, {'timezone': ''}, {'timezone': 'x' * 65},
    {'expected_revision': True}, {'partner_id': str(uuid4())},
])
def test_round_consent_validation(changes):
    with pytest.raises(ValidationError):
        CompetitionConsent(**consent_body({'revision': 1}, **changes))


def log(day, position):
    return SimpleNamespace(reading_date=date(2026, 9, day), position=position)


def test_score_prioritizes_consistency_over_any_volume_bonus():
    score = lambda logs, total=100: weekly.score_positions(0, total, 10, logs, date(2026, 9, 2), date(2026, 9, 9), date(2026, 9, 8))
    one_day = score([log(2, 100)])
    two_days = score([log(2, 10), log(3, 20)])
    assert one_day == (1, 10000, 1500)
    assert two_days == (2, 2000, 2100)
    assert two_days[2] > one_day[2]
    assert score([log(2, 10)]) == score([log(2, 20)], total=200)


def test_score_excludes_prior_and_future_days_and_handles_chapters_and_baseline():
    logs = [log(1, 50), log(2, 60), log(3, 70), log(9, 80)]
    assert weekly.score_positions(0, 100, 10, logs, date(2026, 9, 2), date(2026, 9, 9), date(2026, 9, 2)) == (1, 1000, 1050)
    assert weekly.score_positions(60, 100, 10, logs, date(2026, 9, 2), date(2026, 9, 9), date(2026, 9, 8)) == (1, 1000, 1050)
    assert weekly.score_positions(0, 20, 1, [log(2, 1)], date(2026, 9, 2), date(2026, 9, 9), date(2026, 9, 2)) == (1, 500, 1025)


def test_integer_scores_round_down_deterministically_and_cap_bonus():
    assert weekly.score_positions(0, 300, 10, [log(2, 10)], date(2026, 9, 2), date(2026, 9, 9), date(2026, 9, 2)) == (1, 333, 1016)
    logs = [log(day, (day-1)*10) for day in range(2, 9)]
    assert weekly.score_positions(0, 70, 10, logs, date(2026, 9, 2), date(2026, 9, 9), date(2026, 9, 8)) == (7, 10000, 7500)


@pytest.fixture
def competition(db, monkeypatch):
    clock = [datetime(2026, 9, 1, 12, tzinfo=timezone.utc)]
    monkeypatch.setattr(weekly, 'utc_now', lambda: clock[0])
    monkeypatch.setattr('app.routers.reading_progress.local_today', lambda tz, now=None: (now or clock[0]).astimezone(ZoneInfo(tz)).date())
    users = [get_or_create_user_by_auth_id(db, str(uuid4()), f'{uuid4()}@example.com') for _ in range(3)]
    books = [Book(id=uuid4(), title=f'Competition book {i}', author_name='Writer', description='Test', page_count=100*(i+1)) for i in range(3)]
    db.add_all(books); db.flush()
    db.add_all([UserBookStatusModel(user_id=user.id, book_id=str(book.id), status='currently_reading') for user, book in zip(users, books)])
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: users[0]
    client = TestClient(app)
    for i in (0, 1):
        as_user(users[i])
        settings = client.put(f'/api/reading/books/{books[i].id}/settings', json=dict(unit='pages', starting_position=0, total_units=100*(i+1), daily_goal=10, expected_revision=0))
        assert settings.status_code == 200, settings.text
        joined = client.post(ROOT + '/join', json=dict(request_id=str(uuid4()), expected_revision=0, reading_name=f'Reader {i}', book_id=str(books[i].id), share_with_partner=True))
        assert joined.status_code == 200, joined.text
    yield client, users, books, clock
    app.dependency_overrides.clear()


def as_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


def summary(client, user):
    as_user(user)
    response = client.post(ROOT + '/rounds/sync')
    assert response.status_code == 200, response.text
    return response.json()


def consent(client, user, tz='UTC'):
    state = summary(client, user)
    response = client.post(ROOT + '/rounds/join', json=consent_body(state, tz))
    assert response.status_code == 200, response.text
    return response.json()


def start(client, users):
    consent(client, users[0])
    return consent(client, users[1])


def save_log(client, user, book, day, position):
    as_user(user)
    current = client.get(f'/api/reading/books/{book.id}/progress').json()
    response = client.put(f'/api/reading/books/{book.id}/logs/{day}', json=dict(position=position, expected_revision=current['revision']))
    assert response.status_code == 200, response.text
    return response.json()


def test_existing_pairing_does_not_share_progress_until_both_consent(db, competition):
    client, users, books, clock = competition
    state = summary(client, users[0])
    assert state['state'] == 'not_joined' and state['current'] is None
    assert client.get(ROOT).json()['progress_sharing'] is False
    first = consent(client, users[0])
    assert first['state'] == 'waiting' and first['current'] is None
    other = summary(client, users[1])
    assert other['state'] == 'not_joined' and other['partner_consented'] is True
    assert other['current'] is None and other['history'] == []
    assert db.query(FriendlyRound).count() == 0
    both = consent(client, users[1])
    assert both['state'] == 'scheduled'
    assert both['current']['starts_on'] == '2026-09-02'
    assert both['current']['ends_on'] == '2026-09-08'
    assert db.query(FriendlyRound).count() == 1


def test_live_score_uses_relative_progress_and_repeated_logs_add_no_credit(db, competition):
    client, users, books, clock = competition
    start(client, users)
    clock[0] = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    saved = save_log(client, users[0], books[0], '2026-09-02', 10)
    # Retry a committed response with the original stale reading revision.
    retried = client.put(f'/api/reading/books/{books[0].id}/logs/2026-09-02', json=dict(position=10, expected_revision=saved['revision'] - 1))
    assert retried.status_code == 200
    save_log(client, users[1], books[1], '2026-09-02', 20)
    state = summary(client, users[0])
    assert state['current']['you'] == state['current']['partner'] == dict(days=1, progress_percent=10.0, points=10.5)
    assert state['current']['result'] == 'even'
    assert state['all_time_points'] == 10.5
    assert db.query(FriendlyRound).one().first_score == 1050
    assert db.query(ReadingLog).count() == 2


def test_completion_is_not_a_substitute_for_consistent_days(db, competition):
    client, users, books, clock = competition
    start(client, users)
    clock[0] = datetime(2026, 9, 3, 12, tzinfo=timezone.utc)
    save_log(client, users[0], books[0], '2026-09-02', 100)
    save_log(client, users[1], books[1], '2026-09-02', 10)
    save_log(client, users[1], books[1], '2026-09-03', 20)
    state = summary(client, users[1])
    assert state['current']['you']['points'] == 20.5
    assert state['current']['partner']['points'] == 15
    assert state['current']['result'] == 'ahead'


def test_round_rollover_records_win_and_keeps_total_on_new_week(db, competition):
    client, users, books, clock = competition
    start(client, users)
    clock[0] = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    save_log(client, users[0], books[0], '2026-09-02', 10)
    clock[0] = datetime(2026, 9, 9, 0, tzinfo=timezone.utc)
    state = summary(client, users[0])
    assert state['history'][0]['result'] == 'win'
    assert state['history'][0]['you']['points'] == 10.5
    assert state['history'][0]['partner'] is None
    assert state['current']['starts_on'] == '2026-09-09'
    assert state['current']['you']['points'] == 0
    assert state['all_time_points'] == 10.5 and state['wins'] == 1
    assert summary(client, users[0]) == state
    assert db.query(FriendlyRound).count() == 2


@pytest.mark.parametrize('reading', [False, True])
def test_ties_have_shared_recognition_only_when_reading_happened(db, competition, reading):
    client, users, books, clock = competition
    start(client, users)
    clock[0] = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    if reading:
        save_log(client, users[0], books[0], '2026-09-02', 10)
        save_log(client, users[1], books[1], '2026-09-02', 20)
    clock[0] = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    state = summary(client, users[0])
    assert state['history'][0]['result'] == ('shared_win' if reading else 'quiet')
    assert state['shared_wins'] == int(reading) and state['wins'] == 0


def test_first_shared_calendar_is_explicit_and_stale_calendar_choice_conflicts(db, competition):
    client, users, books, clock = competition
    old = summary(client, users[1])
    consent(client, users[0], 'America/New_York')
    as_user(users[1])
    assert client.post(ROOT + '/rounds/join', json=consent_body(old, 'UTC')).status_code == 409
    current = summary(client, users[1])
    assert current['timezone'] == 'America/New_York'
    assert client.post(ROOT + '/rounds/join', json=consent_body(current, 'Not/AZone')).status_code == 422
    saved = consent(client, users[1], 'America/New_York')
    clock[0] = datetime(2026, 9, 2, 3, 59, tzinfo=timezone.utc)
    assert summary(client, users[0])['state'] == 'scheduled'
    clock[0] = datetime(2026, 9, 2, 4, 0, tzinfo=timezone.utc)
    assert summary(client, users[0])['state'] == 'active'
    assert saved['current']['starts_on'] == '2026-09-02'


def test_pre_pairing_positions_and_reading_before_round_start_are_excluded(db, competition):
    client, users, books, clock = competition
    save_log(client, users[0], books[0], '2026-09-01', 50)
    start(client, users)
    save_log(client, users[0], books[0], '2026-09-01', 60)
    clock[0] = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    save_log(client, users[0], books[0], '2026-09-02', 70)
    assert summary(client, users[0])['current']['you'] == dict(days=1, progress_percent=10, points=10.5)


def test_positions_already_logged_in_ahead_timezone_are_not_free_credit(db, competition):
    client, users, books, clock = competition
    as_user(users[0])
    clock[0] = datetime(2026, 9, 1, 13, tzinfo=timezone.utc)
    progress = client.get(f'/api/reading/books/{books[0].id}/progress').json()
    ahead = client.put(f'/api/reading/books/{books[0].id}/logs/2026-09-02', params={'tz': 'Pacific/Kiritimati'}, json=dict(position=50, expected_revision=progress['revision']))
    assert ahead.status_code == 200, ahead.text
    start(client, users)
    clock[0] = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    assert summary(client, users[0])['current']['you']['points'] == 0
    save_log(client, users[0], books[0], '2026-09-02', 60)
    assert summary(client, users[0])['current']['you']['points'] == 10.5


def test_chapter_target_and_edition_are_frozen_but_personal_goal_can_change(db, competition):
    client, users, books, clock = competition
    as_user(users[0])
    progress = client.get(f'/api/reading/books/{books[0].id}/progress').json()
    settings = dict(unit='chapters', starting_position=0, total_units=20, daily_goal=1, expected_revision=progress['revision'])
    response = client.put(f'/api/reading/books/{books[0].id}/settings', json=settings)
    assert response.status_code == 200
    start(client, users)
    as_user(users[0])
    current = client.get(f'/api/reading/books/{books[0].id}/progress').json()
    personal = client.put(f'/api/reading/books/{books[0].id}/settings', json=settings | {'daily_goal': 2, 'expected_revision': current['revision']})
    assert personal.status_code == 200
    blocked = client.put(f'/api/reading/books/{books[0].id}/settings', json=settings | {'total_units': 10, 'expected_revision': personal.json()['revision']})
    assert blocked.status_code == 409
    clock[0] = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    save_log(client, users[0], books[0], '2026-09-02', 1)
    state = summary(client, users[0])
    assert state['rule']['daily_target'] == 1
    assert state['current']['you']['points'] == 10.25


def test_unknown_length_and_changed_reading_settings_require_review(db, competition):
    client, users, books, clock = competition
    old = summary(client, users[0])
    as_user(users[0])
    saved = client.put(f'/api/reading/books/{books[0].id}/settings', json=dict(unit='pages', starting_position=0, total_units=101, daily_goal=10, expected_revision=old['reading_revision']))
    assert saved.status_code == 200
    assert client.post(ROOT + '/rounds/join', json=consent_body(old)).status_code == 409
    db.query(ReadingProgress).filter_by(user_id=users[0].id, book_id=books[0].id).one().total_units = None
    db.commit()
    state = summary(client, users[0])
    assert state['eligibility_error'] and state['rule'] is None
    assert client.post(ROOT + '/rounds/join', json=consent_body(state)).status_code == 409


def test_late_corrections_update_personal_logs_without_rewriting_closed_results(db, competition):
    client, users, books, clock = competition
    start(client, users)
    clock[0] = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    save_log(client, users[0], books[0], '2026-09-02', 10)
    clock[0] = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    # No prior sync: the progress write itself must close the old round first.
    save_log(client, users[0], books[0], '2026-09-02', 20)
    state = summary(client, users[0])
    assert state['history'][0]['you']['points'] == 10.5
    assert state['all_time_points'] == 10.5
    assert client.get(f'/api/reading/books/{books[0].id}/progress').json()['current_position'] == 20
    save_log(client, users[0], books[0], '2026-09-09', 30)
    assert summary(client, users[0])['current']['you']['points'] == 10.5


def test_deleting_current_log_updates_score_but_closed_round_stays_fixed(db, competition):
    client, users, books, clock = competition
    start(client, users)
    clock[0] = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    saved = save_log(client, users[0], books[0], '2026-09-02', 10)
    response = client.delete(f'/api/reading/books/{books[0].id}/logs/2026-09-02', params={'expected_revision': saved['revision']})
    assert response.status_code == 200
    assert summary(client, users[0])['current']['you']['points'] == 0


def test_departure_ends_round_without_winner_retains_own_points_and_revokes_sharing(db, competition):
    client, users, books, clock = competition
    start(client, users)
    clock[0] = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    save_log(client, users[0], books[0], '2026-09-02', 10)
    before = summary(client, users[0])
    left = client.post(ROOT + '/leave', json=dict(request_id=str(uuid4()), expected_revision=before['revision']))
    assert left.status_code == 200, left.text
    assert left.json()['progress_sharing'] is False
    state = summary(client, users[0])
    assert state['state'] == 'unavailable' and state['current'] is None
    assert state['history'][0]['result'] == 'ended'
    assert state['history'][0]['partner'] is None
    assert state['all_time_points'] == 10.5 and state['wins'] == 0
    assert summary(client, users[1])['history'][0]['partner'] is None
    outsider = summary(client, users[2])
    assert outsider['history'] == [] and outsider['all_time_points'] == 0
    assert client.post(ROOT + '/rounds/sync').headers['cache-control'] == 'no-store, private'


def test_consent_retries_and_new_pairings_cannot_inherit_progress_sharing(db, competition):
    client, users, books, clock = competition
    initial = summary(client, users[0])
    body = consent_body(initial)
    first = client.post(ROOT + '/rounds/join', json=body)
    assert first.status_code == 200
    assert client.post(ROOT + '/rounds/join', json=body).json() == first.json()
    consent(client, users[1])
    latest = summary(client, users[0])
    client.post(ROOT + '/leave', json=dict(request_id=str(uuid4()), expected_revision=latest['revision']))
    assert client.post(ROOT + '/rounds/join', json=body).status_code == 409
    old = client.get(ROOT).json()
    new_search = client.post(ROOT + '/join', json=dict(request_id=str(uuid4()), expected_revision=old['revision'], reading_name='Again', book_id=str(books[0].id), share_with_partner=True))
    assert new_search.status_code == 200
    assert new_search.json()['progress_sharing'] is False
    assert db.query(FriendlyParticipation).filter_by(user_id=users[0].id).one().competition_consented_at is None


def test_failed_reading_save_rolls_back_score_and_log_together(db, competition, monkeypatch):
    client, users, books, clock = competition
    start(client, users)
    clock[0] = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    as_user(users[0])
    progress = client.get(f'/api/reading/books/{books[0].id}/progress').json()
    with monkeypatch.context() as patch:
        patch.setattr(db, 'commit', Mock(side_effect=RuntimeError('test failure')))
        response = client.put(f'/api/reading/books/{books[0].id}/logs/2026-09-02', json=dict(position=10, expected_revision=progress['revision']))
        assert response.status_code == 500
    assert db.query(ReadingLog).count() == 0
    assert summary(client, users[0])['current']['you']['points'] == 0


def test_failed_consent_rolls_back_round_and_both_readers(db, competition, monkeypatch):
    client, users, books, clock = competition
    consent(client, users[0])
    state = summary(client, users[1])
    with monkeypatch.context() as patch:
        patch.setattr(db, 'commit', Mock(side_effect=RuntimeError('test failure')))
        assert client.post(ROOT + '/rounds/join', json=consent_body(state)).status_code == 500
    assert summary(client, users[1])['consented'] is False
    assert summary(client, users[0])['state'] == 'waiting'
    assert db.query(FriendlyRound).count() == 0


def test_catchup_is_idempotent_and_does_not_award_reading_points(db, competition):
    client, users, books, clock = competition
    start(client, users)
    clock[0] = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
    state = summary(client, users[0])
    assert len(state['history']) == 5
    assert all(row['result'] == 'quiet' for row in state['history'])
    assert summary(client, users[0]) == state
    assert db.query(FriendlyRound).count() == 6
    assert client.get('/api/reading/rewards').json()['total_points'] == 0


def test_weekly_routes_require_auth():
    client = TestClient(app)
    for response in (client.post(ROOT + '/rounds/sync'), client.post(ROOT + '/rounds/join', json=consent_body({'revision': 0}))):
        assert response.status_code in (401, 403)


def test_weekly_migration_defaults_to_no_consent_and_downgrade_preserves_pairing(db, monkeypatch):
    connection = db.connection()
    schema = 'rd59_' + uuid4().hex
    previous = connection.execute(text("SELECT current_setting('search_path')")).scalar_one()
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connection.execute(text("SELECT set_config('search_path', :path, true)"), {'path': schema})
    try:
        connection.execute(text('CREATE TABLE users (id UUID PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE books (id UUID PRIMARY KEY)'))
        migrations = []
        for name in ('f2a3b4c5d6e7_add_friendly_pairing.py', 'a3b4c5d6e7f8_add_weekly_competition.py'):
            path = Path(__file__).parents[1] / 'alembic/versions' / name
            spec = importlib.util.spec_from_file_location(name[:-3], path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
            migrations.append(migration)
        migrations[0].upgrade()
        user = uuid4()
        connection.execute(text('INSERT INTO users (id) VALUES (:id)'), {'id': user})
        connection.execute(text('INSERT INTO friendly_participations (user_id) VALUES (:id)'), {'id': user})
        migrations[1].upgrade()
        row = connection.execute(text('SELECT competition_consented_at, competition_total, competition_baseline_position FROM friendly_participations')).one()
        assert tuple(row) == (None, None, None)
        assert connection.execute(text('SELECT count(*) FROM friendly_rounds')).scalar_one() == 0
        assert len(inspect(connection).get_check_constraints('friendly_rounds', schema=schema)) == 4
        migrations[1].downgrade()
        assert connection.execute(text('SELECT status FROM friendly_participations')).scalar_one() == 'inactive'
        assert set(inspect(connection).get_table_names(schema=schema)) == {'users', 'books', 'friendly_pairs', 'friendly_participations'}
    finally:
        connection.execute(text("SELECT set_config('search_path', :path, true)"), {'path': previous})
