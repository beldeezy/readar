from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

# Debug: Print the database URL to verify which database we're connecting to (password masked)
print("READAR DATABASE_URL =", settings.get_masked_database_url())

# Create engine with connection pooling and pre-ping to verify connections
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using them
    echo=settings.DEBUG,  # Log SQL queries in debug mode
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

