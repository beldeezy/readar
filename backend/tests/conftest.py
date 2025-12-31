"""Pytest configuration for backend tests."""
import sys
import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text as sa_text
from sqlalchemy.orm import sessionmaker, Session
import sqlalchemy as sa

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Import database components
from app.database import Base

# Import the entire models module to ensure all models are registered with Base.metadata
# This must happen before create_all() so that all table definitions are available
import app.models  # noqa: F401


# Determine test database URL
# TEST_DATABASE_URL is REQUIRED - never use production DATABASE_URL
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL environment variable is required for running tests. "
        "Set it to a test Postgres database URL, e.g.:\n"
        "  export TEST_DATABASE_URL='postgresql://user:password@localhost:5432/test_readar'\n"
        "This prevents accidentally running tests against production database."
    )


@pytest.fixture(scope="session")
def engine():
    """
    Create a test database engine.
    
    Requires TEST_DATABASE_URL environment variable to be set.
    For local testing, set TEST_DATABASE_URL to a test Postgres database.
    
    Note: Models use Postgres-specific features (PostgresEnum, UUID, JSONB, ARRAY),
    so SQLite is not supported. Use a test Postgres database.
    """
    if TEST_DATABASE_URL.startswith("sqlite"):
        raise RuntimeError(
            "SQLite not supported - models use Postgres-specific features. "
            "Set TEST_DATABASE_URL to a Postgres test database URL."
        )
    
    # Create engine for test database
    test_engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
        echo=False,
    )
    
    # Debug assertion: verify tables are registered
    if not Base.metadata.tables:
        raise RuntimeError(
            "No tables registered in Base.metadata. "
            "Did you import app.models? All model classes must be imported before create_all()."
        )
    
    # Create Postgres enum types before creating tables
    # These are required for PostgresEnum columns
    with test_engine.connect() as conn:
        # Create enum types if they don't exist (idempotent)
        conn.execute(sa_text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscriptionstatus') THEN
                    CREATE TYPE subscriptionstatus AS ENUM ('free', 'active', 'canceled');
                END IF;
            END
            $$;
        """))
        
        conn.execute(sa_text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'businessstage') THEN
                    CREATE TYPE businessstage AS ENUM ('idea', 'pre-revenue', 'early-revenue', 'scaling');
                END IF;
            END
            $$;
        """))
        
        conn.execute(sa_text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'bookdifficulty') THEN
                    CREATE TYPE bookdifficulty AS ENUM ('light', 'medium', 'deep');
                END IF;
            END
            $$;
        """))
        
        conn.execute(sa_text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userbookstatus') THEN
                    CREATE TYPE userbookstatus AS ENUM ('read_liked', 'read_disliked', 'interested', 'not_interested');
                END IF;
            END
            $$;
        """))
        
        conn.execute(sa_text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feedbacksentiment') THEN
                    CREATE TYPE feedbacksentiment AS ENUM ('positive', 'negative');
                END IF;
            END
            $$;
        """))
        
        conn.execute(sa_text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feedbackstate') THEN
                    CREATE TYPE feedbackstate AS ENUM ('interested', 'read_completed', 'dismissed');
                END IF;
            END
            $$;
        """))
        
        conn.commit()
    
    # Create all tables
    # Note: This will fail if tables already exist, but that's okay for test isolation
    try:
        Base.metadata.create_all(bind=test_engine)
        print(f"Created {len(Base.metadata.tables)} tables in test database")
    except Exception as e:
        # If tables exist, that's fine - we'll clean up in teardown
        print(f"Note: Some tables may already exist: {e}")
    
    yield test_engine
    
    # Cleanup: drop all tables (optional - comment out if you want to keep test data)
    try:
        Base.metadata.drop_all(bind=test_engine)
    except Exception:
        pass  # Ignore errors during cleanup
    test_engine.dispose()


@pytest.fixture(scope="function")
def db(engine) -> Session:
    """
    Create a database session for each test.
    
    Uses a transaction that is rolled back after each test for isolation.
    This ensures tests don't affect each other.
    """
    connection = engine.connect()
    
    # Start a transaction
    transaction = connection.begin()
    
    # Create session bound to this connection
    # Use autocommit=False, autoflush=False to match production
    SessionLocal = sessionmaker(
        bind=connection,
        autocommit=False,
        autoflush=False,
    )
    session = SessionLocal()
    
    yield session
    
    # Cleanup: rollback transaction and close
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def db_with_commit(db: Session) -> Session:
    """
    Database session that allows commits (for testing commit behavior).
    
    Uses a savepoint (nested transaction) that is rolled back at the end for test isolation.
    """
    # Use a nested transaction (savepoint) that we can rollback
    transaction = db.begin_nested()
    
    yield db
    
    # Rollback the nested transaction
    transaction.rollback()
