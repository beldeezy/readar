"""Explicit, private two-reader pairing; no points, emails or implicit re-enrolment."""
from datetime import datetime, timezone
import hashlib
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database import get_db
from app.models import Book, FriendlyPair, FriendlyParticipation, User, UserBookStatusModel
from app.schemas.friendly_pairing import JoinPairing, PairingCommand, PairingResponse, SharedReader

router = APIRouter(prefix='/reading/competition', tags=['friendly-competition'])
logger = logging.getLogger(__name__)
PAIRING_LOCK = 580058


def _lock(db, shared=False):
    # Small launch queue: serialize the whole match/leave transaction across API
    # processes. A shared lock makes GET coherent without enrolling anyone.
    function = 'pg_advisory_xact_lock_shared' if shared else 'pg_advisory_xact_lock'
    db.execute(text(f'SELECT {function}(:key)'), {'key': PAIRING_LOCK})


def _participation(db, user_id):
    return db.query(FriendlyParticipation).filter_by(user_id=user_id).populate_existing().first()


def _shared(row):
    # Explicit allowlist: never serialize User, profile, notes or reading logs.
    return SharedReader(reading_name=row.reading_name, book_title=row.book_title, book_author=row.book_author)


def _response(db, user_id):
    row = _participation(db, user_id)
    if row is None:
        return PairingResponse(status='inactive', revision=0)
    result = PairingResponse(status=row.status, revision=row.revision,
        you=_shared(row) if row.reading_name else None, selected_book_id=row.book_id, queued_at=row.queued_at)
    if row.status in ('paired', 'ended'):
        pair = db.query(FriendlyPair).filter_by(id=row.pairing_id).populate_existing().one()
        if user_id not in (pair.first_user_id, pair.second_user_id):
            raise RuntimeError('Invalid pairing membership')
        result.pairing_id = pair.id
        result.started_at = pair.started_at
        result.ended_at = pair.ended_at
        if row.status == 'paired':
            partner_id = pair.second_user_id if pair.first_user_id == user_id else pair.first_user_id
            partner = _participation(db, partner_id)
            if pair.ended_at is not None or not partner or partner.status != 'paired' or partner.pairing_id != pair.id:
                raise RuntimeError('Invalid active pairing')
            result.partner = _shared(partner)
        else:
            result.ended_by_you = pair.ended_by == user_id
    return result


def _fingerprint(action, payload):
    return hashlib.sha256(json.dumps({'action': action, **payload.model_dump(mode='json')}, sort_keys=True).encode()).hexdigest()


def _mutate(db, user_id, payload, action, change):
    try:
        _lock(db)
        row = _participation(db, user_id)
        fingerprint = _fingerprint(action, payload)
        if row and row.last_request_id == payload.request_id:
            if row.last_request_hash != fingerprint:
                raise HTTPException(status_code=409, detail='This request was already saved with different choices. Check status before trying again.')
            # Return current state: a lost-response retry after departure must not
            # resurrect consent, expose a former partner, or create another pair.
            result = _response(db, user_id)
            db.commit()
            return result
        if (row.revision if row else 0) != payload.expected_revision:
            raise HTTPException(status_code=409, detail='Your pairing changed in another session. Check status before choosing again.')
        if row is None:
            row = FriendlyParticipation(user_id=user_id, status='inactive', revision=0)
            db.add(row)
        change(row)
        row.last_request_id = payload.request_id
        row.last_request_hash = fingerprint
        row.revision += 1
        db.flush()
        result = _response(db, user_id)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception as error:
        db.rollback()
        logger.error('Could not save friendly pairing (%s)', type(error).__name__)
        raise HTTPException(status_code=500, detail='We couldn’t save your pairing choice. Please try again; your reading progress is safe.')


@router.get('', response_model=PairingResponse)
def get_pairing(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store, private'
    _lock(db, shared=True)
    return _response(db, user.id)


@router.post('/join', response_model=PairingResponse)
def join_pairing(payload: JoinPairing, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store, private'

    def change(row):
        if row.status not in ('inactive', 'ended'):
            raise HTTPException(status_code=409, detail='You already have an active search or pairing. Check status before choosing again.')
        book = db.get(Book, payload.book_id)
        if book is None:
            raise HTTPException(status_code=404, detail='Book not found.')
        ids = [str(book.id)] + ([book.external_id] if book.external_id else [])
        started = db.query(UserBookStatusModel).filter(UserBookStatusModel.user_id == user.id,
            UserBookStatusModel.book_id.in_(ids), UserBookStatusModel.status == 'currently_reading').first()
        if not started:
            raise HTTPException(status_code=409, detail='Start this book in Reading before choosing it for Friendly Competition.')
        now = datetime.now(timezone.utc)
        row.status = 'waiting'
        row.reading_name = payload.reading_name
        row.book_id, row.book_title, row.book_author = book.id, book.title, book.author_name or ''
        row.consented_at, row.queued_at, row.pairing_id = now, now, None
        # All writers hold PAIRING_LOCK, so two newcomers cannot claim the same
        # waiting reader, even on different workers. FIFO has a stable tie break.
        partner = db.query(FriendlyParticipation).filter(FriendlyParticipation.status == 'waiting',
            FriendlyParticipation.user_id != user.id).order_by(FriendlyParticipation.queued_at, FriendlyParticipation.user_id).first()
        if partner:
            pair = FriendlyPair(id=uuid4(), first_user_id=partner.user_id, second_user_id=user.id, started_at=now)
            db.add(pair)
            db.flush()  # Insert the FK target before assigning either membership.
            row.status = partner.status = 'paired'
            row.pairing_id = partner.pairing_id = pair.id
            row.queued_at = partner.queued_at = None
            partner.revision += 1
    return _mutate(db, user.id, payload, 'join', change)


@router.post('/leave', response_model=PairingResponse)
def leave_pairing(payload: PairingCommand, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store, private'

    def change(row):
        if row.status == 'waiting':
            row.status, row.queued_at, row.pairing_id = 'inactive', None, None
        elif row.status == 'paired':
            pair = db.query(FriendlyPair).filter_by(id=row.pairing_id).one()
            partner_id = pair.second_user_id if pair.first_user_id == user.id else pair.first_user_id
            partner = _participation(db, partner_id)
            if not partner or partner.pairing_id != pair.id or partner.status != 'paired' or pair.ended_at is not None:
                raise RuntimeError('Invalid active pairing')
            pair.ended_at, pair.ended_by = datetime.now(timezone.utc), user.id
            row.status = partner.status = 'ended'
            partner.revision += 1
        else:
            raise HTTPException(status_code=409, detail='There is no active search or pairing to leave. Check status for your latest state.')
    return _mutate(db, user.id, payload, 'leave', change)
