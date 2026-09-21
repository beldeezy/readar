"""Explicit consent plus idempotent round synchronization, with private results."""
from datetime import timedelta
import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database import get_db
from app.models import FriendlyPair, FriendlyParticipation, ReadingLog, User
from app.routers.friendly_pairing import _lock, _mutate
from app.routers.reading_progress import local_today
from app.schemas.weekly_competition import CompetitionConsent, CompetitionResponse
from app.services import weekly_competition as weekly

router = APIRouter(prefix='/reading/competition/rounds', tags=['weekly-competition'])
logger = logging.getLogger(__name__)


@router.post('/sync', response_model=CompetitionResponse)
def sync_rounds(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store, private'
    try:
        _lock(db)
        weekly.sync_for_reader(db, user.id)
        result = weekly.summary(db, user.id)
        db.commit()
        return result
    except Exception as error:
        db.rollback()
        logger.error('Could not synchronize weekly competition (%s)', type(error).__name__)
        raise HTTPException(status_code=500, detail='We couldn’t update the round. Your saved reading is safe; please try again.')


@router.post('/join', response_model=CompetitionResponse)
def join_rounds(payload: CompetitionConsent, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store, private'
    local_today(payload.timezone)  # Validate IANA timezone before any mutation.

    def change(row):
        if row.status != 'paired':
            raise HTTPException(status_code=409, detail='Pair with a reader before joining weekly rounds.')
        if row.competition_consented_at is not None:
            raise HTTPException(status_code=409, detail='You already joined weekly rounds. Refresh your round before choosing again.')
        pair = db.query(FriendlyPair).filter_by(id=row.pairing_id).one()
        if pair.competition_timezone and pair.competition_timezone != payload.timezone:
            raise HTTPException(status_code=409, detail='Your partner chose the round calendar. Refresh to review it before joining.')
        progress, error = weekly.eligibility(db, row)
        if error:
            raise HTTPException(status_code=409, detail=error)
        if progress.revision != payload.expected_reading_revision:
            raise HTTPException(status_code=409, detail='Your reading settings or progress changed. Refresh to review the current rule before joining.')
        now = weekly.utc_now()
        pair.competition_timezone = payload.timezone
        row.competition_consented_at = now
        row.competition_unit = progress.unit
        row.competition_total = progress.total_units
        row.competition_starting_position = progress.starting_position
        row.competition_goal = 10 if progress.unit == 'pages' else progress.daily_goal
        partner = db.query(FriendlyParticipation).filter(FriendlyParticipation.pairing_id == pair.id,
                                                        FriendlyParticipation.user_id != user.id).one()
        if partner.competition_consented_at:
            pair.competition_starts_on = weekly.round_today(pair, now) + timedelta(days=1)
            partner.revision += 1
            # Exclude positions already reached before both readers opted in,
            # including a log dated tomorrow in an ahead-of-calendar timezone.
            for member in (row, partner):
                positions = [log.position for log in db.query(ReadingLog).filter_by(user_id=member.user_id, book_id=member.book_id).all()]
                member.competition_baseline_position = max([member.competition_starting_position, *positions])
            db.flush()
            weekly.sync_pair(db, pair, now)
    return _mutate(db, user.id, payload, 'join_rounds', change, response_builder=weekly.synchronize_summary)
