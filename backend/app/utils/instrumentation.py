"""
Server-side event logging helper.

Logs events to both the database (for querying) and structured logs (for immediate visibility).
"""
import logging
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, ProgrammingError
from app.models import EventLog
from app.database import SessionLocal

logger = logging.getLogger(__name__)


def log_event(
    db: Session,
    event_name: str,
    user_id: Optional[UUID] = None,
    properties: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """
    Log an event to the database and structured logs.
    
    Args:
        db: Database session
        event_name: Name of the event (e.g., "onboarding_completed", "recommendations_impression")
        user_id: Optional user ID (UUID)
        properties: Optional dict of event properties
        request_id: Optional request ID for correlating events
        session_id: Optional session ID
    
    Note: This function does NOT commit the transaction. The caller should commit.
    It does flush() to ensure the event is persisted within the caller's transaction.
    """
    try:
        event = EventLog(
            event_name=event_name,
            user_id=user_id,
            properties=properties,
            request_id=request_id,
            session_id=session_id,
        )
        db.add(event)
        db.flush()  # Flush to persist within transaction, but don't commit
        
        # Also emit structured log
        log_data = {
            "event_name": event_name,
            "user_id": str(user_id) if user_id else None,
            "request_id": request_id,
            "session_id": session_id,
            "properties": properties,
        }
        logger.info("event_logged", extra=log_data)
    except Exception as e:
        # Never break the request path - log warning and continue
        logger.warning(
            "Failed to log event: event_name=%s, user_id=%s, error=%s",
            event_name,
            user_id,
            str(e),
            exc_info=True,
        )


def log_event_best_effort(
    event_name: str,
    user_id: Optional[UUID] = None,
    properties: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """
    Log an event using a separate database session (best-effort, non-blocking).
    
    This function creates its own database session and commits independently,
    so it will never break the main business transaction (e.g., onboarding save).
    
    Args:
        event_name: Name of the event (e.g., "onboarding_completed", "recommendations_impression")
        user_id: Optional user ID (UUID)
        properties: Optional dict of event properties
        request_id: Optional request ID for correlating events
        session_id: Optional session ID
    
    This function never raises exceptions - failures are logged as warnings.
    """
    db = None
    try:
        db = SessionLocal()
        event = EventLog(
            event_name=event_name,
            user_id=user_id,
            properties=properties,
            request_id=request_id,
            session_id=session_id,
        )
        db.add(event)
        db.commit()
        
        # Also emit structured log
        log_data = {
            "event_name": event_name,
            "user_id": str(user_id) if user_id else None,
            "request_id": request_id,
            "session_id": session_id,
            "properties": properties,
        }
        logger.info("event_logged", extra=log_data)
    except (OperationalError, ProgrammingError) as e:
        # Check if it's a missing table error
        error_str = str(e).lower()
        if "does not exist" in error_str or "relation" in error_str or "table" in error_str:
            logger.warning(
                "event_logs table missing — run alembic upgrade head. "
                "Event logging disabled until migration is applied."
            )
        else:
            logger.warning(
                "Failed to log event (database error): event_name=%s, user_id=%s, error=%s",
                event_name,
                user_id,
                str(e),
                exc_info=True,
            )
        if db:
            db.rollback()
    except Exception as e:
        # Never break the request path - log warning and continue
        logger.warning(
            "Failed to log event: event_name=%s, user_id=%s, error=%s",
            event_name,
            user_id,
            str(e),
            exc_info=True,
        )
        if db:
            db.rollback()
    finally:
        if db:
            db.close()

