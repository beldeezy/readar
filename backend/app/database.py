from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings
import logging
import time

logger = logging.getLogger(__name__)

# Debug: Print the database URL to verify which database we're connecting to (password masked)
print("READAR DATABASE_URL =", settings.get_masked_database_url())

# Create engine with connection pooling and pre-ping to verify connections
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using them
    echo=False,  # Keep echo off - we'll log slow queries separately
)

# Add slow query logging (DEBUG mode only)
if settings.DEBUG:
    SLOW_QUERY_THRESHOLD_MS = 200.0
    
    @event.listens_for(engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Store query start time before execution."""
        context._query_start_time = time.perf_counter()
    
    @event.listens_for(engine, "after_cursor_execute")
    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Log slow queries after execution."""
        if hasattr(context, "_query_start_time"):
            elapsed_ms = (time.perf_counter() - context._query_start_time) * 1000
            if elapsed_ms >= SLOW_QUERY_THRESHOLD_MS:
                # Get first line of statement for brevity
                statement_first_line = statement.split("\n")[0].strip()[:100]
                logger.warning(
                    f"SLOW_QUERY: {elapsed_ms:.2f}ms - {statement_first_line}"
                )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Dev convenience: ensure all tables (including reading_history_entries) exist.
    In production, prefer running Alembic migrations instead.
    
    WARNING: create_all() will NOT add missing columns to existing tables.
    It only creates tables that don't exist. Use Alembic migrations for schema changes.
    
    This imports all models so that Base.metadata includes all table definitions.
    """
    import os
    alembic_versions_path = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions")
    if os.path.exists(alembic_versions_path) and os.listdir(alembic_versions_path):
        import warnings
        warnings.warn(
            "Alembic migrations detected. Skipping Base.metadata.create_all(). "
            "Use 'alembic upgrade head' for schema changes.",
            UserWarning
        )
        # Skip create_all() when Alembic is present - migrations are the source of truth
        return
    
    # Import all models to ensure they're registered with Base.metadata
    from app import models  # noqa: F401
    
    # Create all tables defined in models (only if Alembic is not present)
    Base.metadata.create_all(bind=engine)

