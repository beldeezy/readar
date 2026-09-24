"""Weekly scores are derived from daily positions, then frozen at round close."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import or_

from app.models import FriendlyPair, FriendlyParticipation, FriendlyRound, ReadingLog, ReadingProgress
from app.schemas.weekly_competition import CompetitionResponse, CompetitionRule, CompetitionRoundView, CompetitionScore


def utc_now():
    return datetime.now(timezone.utc)


def round_today(pair, now):
    return now.astimezone(ZoneInfo(pair.competition_timezone)).date()


def score_positions(starting_position, total_units, daily_target, logs, starts_on, ends_before, today):
    previous, days, units = starting_position, 0, 0
    for log in sorted(logs, key=lambda item: item.reading_date):
        delta = max(0, log.position - previous)
        previous = max(previous, log.position)
        if starts_on <= log.reading_date < ends_before and log.reading_date <= today:
            days += int(delta >= daily_target)
            units += delta
    progress_bps = min(10000, units * 10000 // total_units)
    return days, progress_bps, days * 1000 + progress_bps // 20


def _refresh_round(round_, participants, logs, today):
    for prefix, row in zip(('first', 'second'), participants):
        days, progress, score = score_positions(max(row.competition_starting_position, row.competition_baseline_position or 0), row.competition_total,
            row.competition_goal, logs[row.user_id], round_.starts_on, round_.ends_before, today)
        setattr(round_, prefix + '_days', days)
        setattr(round_, prefix + '_progress_bps', progress)
        setattr(round_, prefix + '_score', score)


def sync_pair(db, pair, now=None):
    """Caller holds the exclusive pairing lock. Never reopen a closed round."""
    if pair.ended_at is not None or pair.competition_starts_on is None:
        return None
    now = now or utc_now()
    today = round_today(pair, now)
    by_user = {row.user_id: row for row in db.query(FriendlyParticipation).filter_by(pairing_id=pair.id).all()}
    participants = [by_user[pair.first_user_id], by_user[pair.second_user_id]]
    if any(row.status != 'paired' or row.competition_consented_at is None for row in participants):
        raise RuntimeError('Missing active progress-sharing consent')
    logs = {row.user_id: db.query(ReadingLog).filter_by(user_id=row.user_id, book_id=row.book_id).order_by(ReadingLog.reading_date).all() for row in participants}
    current = db.query(FriendlyRound).filter_by(pairing_id=pair.id).order_by(FriendlyRound.starts_on.desc()).first()
    if current is None:
        current = FriendlyRound(pairing_id=pair.id, starts_on=pair.competition_starts_on,
                                ends_before=pair.competition_starts_on + timedelta(days=7), status='active')
        db.add(current)
    while today >= current.ends_before:
        if current.status == 'active':
            _refresh_round(current, participants, logs, current.ends_before - timedelta(days=1))
            current.status, current.closed_at = 'finished', now
        next_start = current.ends_before
        current = FriendlyRound(pairing_id=pair.id, starts_on=next_start,
                                ends_before=next_start + timedelta(days=7), status='active')
        db.add(current)
    _refresh_round(current, participants, logs, today)
    db.flush()
    return current


def sync_for_reader(db, user_id, now=None):
    row = db.query(FriendlyParticipation).filter_by(user_id=user_id, status='paired').first()
    if row is None:
        return None
    pair = db.query(FriendlyPair).filter_by(id=row.pairing_id).first()
    return sync_pair(db, pair, now) if pair else None


def end_rounds(db, pair):
    now = utc_now()
    current = sync_pair(db, pair, now)
    if current:
        current.status, current.closed_at = 'ended', now
        db.flush()


def guard_settings(db, user_id, book_id, values):
    row = db.query(FriendlyParticipation).filter_by(user_id=user_id, book_id=book_id, status='paired').first()
    if row is None or row.competition_consented_at is None:
        return
    frozen = {'unit': row.competition_unit, 'starting_position': row.competition_starting_position, 'total_units': row.competition_total}
    if any(values[key] != value for key, value in frozen.items()):
        raise HTTPException(status_code=409, detail='Your book unit, starting position and length are fixed for this competition. Leave the pairing before changing them. Your personal daily goal can still change.')


def eligibility(db, row):
    progress = db.query(ReadingProgress).filter_by(user_id=row.user_id, book_id=row.book_id).first()
    if progress is None or not progress.total_units:
        return None, 'Save Book settings with your edition’s length before joining weekly rounds.'
    return progress, None


def _score(round_, first):
    prefix = 'first' if first else 'second'
    return CompetitionScore(days=getattr(round_, prefix + '_days'),
        progress_percent=getattr(round_, prefix + '_progress_bps') / 100,
        points=getattr(round_, prefix + '_score') / 100)


def _result(round_, first):
    yours, theirs = (round_.first_score, round_.second_score) if first else (round_.second_score, round_.first_score)
    if round_.status == 'ended':
        return 'ended'
    if round_.status == 'active':
        return 'ahead' if yours > theirs else 'behind' if yours < theirs else 'even'
    if yours == theirs:
        return 'shared_win' if yours else 'quiet'
    return 'win' if yours > theirs else 'loss'


def _view(round_, pair, user_id, partner=False, today=None):
    first = pair.first_user_id == user_id
    scheduled = round_.status == 'active' and today is not None and today < round_.starts_on
    return CompetitionRoundView(starts_on=round_.starts_on, ends_on=round_.ends_before - timedelta(days=1),
        status='scheduled' if scheduled else round_.status, you=_score(round_, first),
        partner=_score(round_, not first) if partner else None,
        result='pending' if scheduled else _result(round_, first))


def summary(db, user_id):
    row = db.query(FriendlyParticipation).filter_by(user_id=user_id).populate_existing().first()
    result = CompetitionResponse(state='unavailable', revision=row.revision if row else 0)
    # Private lifetime history includes the reader's earned scores after leaving.
    history = db.query(FriendlyRound, FriendlyPair).join(FriendlyPair, FriendlyRound.pairing_id == FriendlyPair.id).filter(
        or_(FriendlyPair.first_user_id == user_id, FriendlyPair.second_user_id == user_id)).order_by(FriendlyRound.starts_on.desc(), FriendlyRound.id.desc()).all()
    total = 0
    for round_, pair in history:
        first = pair.first_user_id == user_id
        total += round_.first_score if first else round_.second_score
        outcome = _result(round_, first)
        result.wins += int(outcome == 'win')
        result.shared_wins += int(outcome == 'shared_win')
        if round_.status != 'active' and len(result.history) < 12:
            # Retain only one's own result after a partnership; no former-partner
            # identity, book, score or progress is included in history responses.
            result.history.append(_view(round_, pair, user_id))
    result.all_time_points = total / 100
    if row is None or row.status != 'paired':
        return result
    pair = db.query(FriendlyPair).filter_by(id=row.pairing_id).one()
    partner = db.query(FriendlyParticipation).filter(FriendlyParticipation.pairing_id == pair.id,
                                                    FriendlyParticipation.user_id != user_id).one()
    result.timezone = pair.competition_timezone
    result.consented = row.competition_consented_at is not None
    result.partner_consented = partner.competition_consented_at is not None
    progress, result.eligibility_error = eligibility(db, row)
    result.reading_revision = progress.revision if progress else None
    if result.consented:
        result.rule = CompetitionRule(unit=row.competition_unit, daily_target=row.competition_goal, total_units=row.competition_total)
        result.eligibility_error = None
    elif progress:
        result.rule = CompetitionRule(unit=progress.unit, daily_target=10 if progress.unit == 'pages' else progress.daily_goal, total_units=progress.total_units)
    if not result.consented:
        result.state = 'not_joined'
    elif not result.partner_consented:
        result.state = 'waiting'
    else:
        current = next(((round_, owner) for round_, owner in history if owner.id == pair.id and round_.status == 'active'), None)
        if current:
            result.current = _view(*current, user_id, partner=True, today=round_today(pair, utc_now()))
            result.state = result.current.status
        else:
            raise RuntimeError('Missing current competition round')
    return result


def synchronize_summary(db, user_id):
    sync_for_reader(db, user_id)
    return summary(db, user_id)
