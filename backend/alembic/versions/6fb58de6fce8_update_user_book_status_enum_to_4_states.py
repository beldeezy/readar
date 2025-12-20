"""update_user_book_status_enum_to_4_states

Revision ID: 6fb58de6fce8
Revises: 
Create Date: 2025-12-10 09:47:51.837007

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6fb58de6fce8'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 0: Create the enum type if it doesn't exist (self-sufficient migration)
    # This ensures the migration works even on a fresh database
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userbookstatus') THEN
                CREATE TYPE userbookstatus AS ENUM ('interested', 'read_liked', 'read_disliked', 'not_interested');
            END IF;
        END
        $$;
    """)
    
    # Step 1: Add new enum values to the existing enum type (safe if already exists)
    op.execute("ALTER TYPE userbookstatus ADD VALUE IF NOT EXISTS 'read_liked'")
    op.execute("ALTER TYPE userbookstatus ADD VALUE IF NOT EXISTS 'read_disliked'")
    op.execute("ALTER TYPE userbookstatus ADD VALUE IF NOT EXISTS 'interested'")
    op.execute("ALTER TYPE userbookstatus ADD VALUE IF NOT EXISTS 'not_interested'")
    
    # Step 2: Migrate existing data (only if table exists)
    # Map "read" -> "read_liked" (default assumption for existing read books)
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.user_book_interactions') IS NOT NULL THEN
                UPDATE user_book_interactions 
                SET status = 'read_liked'::userbookstatus 
                WHERE status = 'read'::userbookstatus;
            END IF;
        END
        $$;
    """)
    
    # Map "interesting" -> "interested"
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.user_book_interactions') IS NOT NULL THEN
                UPDATE user_book_interactions 
                SET status = 'interested'::userbookstatus 
                WHERE status = 'interesting'::userbookstatus;
            END IF;
        END
        $$;
    """)
    
    # Step 3: Remove old enum values by recreating the enum type
    # First, create a new enum type with only the new values
    op.execute("CREATE TYPE userbookstatus_new AS ENUM ('read_liked', 'read_disliked', 'interested', 'not_interested')")
    
    # Update the column to use the new enum type (only if table exists)
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.user_book_interactions') IS NOT NULL THEN
                ALTER TABLE user_book_interactions 
                ALTER COLUMN status TYPE userbookstatus_new 
                USING status::text::userbookstatus_new;
            END IF;
        END
        $$;
    """)
    
    # Drop the old enum type and rename the new one
    op.execute("DROP TYPE userbookstatus")
    op.execute("ALTER TYPE userbookstatus_new RENAME TO userbookstatus")


def downgrade() -> None:
    # Step 1: Create old enum type
    op.execute("CREATE TYPE userbookstatus_old AS ENUM ('read', 'interesting', 'not_interested')")
    
    # Step 2: Migrate data back (only if table exists)
    # Map "read_liked" and "read_disliked" -> "read"
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.user_book_interactions') IS NOT NULL THEN
                UPDATE user_book_interactions 
                SET status = 'read'::userbookstatus_old 
                WHERE status::text IN ('read_liked', 'read_disliked');
            END IF;
        END
        $$;
    """)
    
    # Map "interested" -> "interesting"
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.user_book_interactions') IS NOT NULL THEN
                UPDATE user_book_interactions 
                SET status = 'interesting'::userbookstatus_old 
                WHERE status::text = 'interested';
            END IF;
        END
        $$;
    """)
    
    # Step 3: Update the column to use the old enum type (only if table exists)
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.user_book_interactions') IS NOT NULL THEN
                ALTER TABLE user_book_interactions 
                ALTER COLUMN status TYPE userbookstatus_old 
                USING status::text::userbookstatus_old;
            END IF;
        END
        $$;
    """)
    
    # Drop the new enum type and rename the old one
    op.execute("DROP TYPE userbookstatus")
    op.execute("ALTER TYPE userbookstatus_old RENAME TO userbookstatus")

