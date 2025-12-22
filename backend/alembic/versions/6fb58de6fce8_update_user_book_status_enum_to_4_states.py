"""update_user_book_status_enum_to_4_states

Revision ID: 6fb58de6fce8
Revises: ee4e43888fe6
Create Date: 2025-12-10 09:47:51.837007

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6fb58de6fce8'
down_revision: Union[str, None] = 'ee4e43888fe6'  # Linear chain: comes after reading_history_entries
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
    # Note: On a fresh DB, the baseline already created the enum with these values,
    # so these will be no-ops. For existing DBs, they add the new values.
    op.execute("""
        DO $$
        BEGIN
            -- Only add values if they don't already exist (for existing DBs)
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'read_liked' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userbookstatus')) THEN
                ALTER TYPE userbookstatus ADD VALUE 'read_liked';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'read_disliked' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userbookstatus')) THEN
                ALTER TYPE userbookstatus ADD VALUE 'read_disliked';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'interested' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userbookstatus')) THEN
                ALTER TYPE userbookstatus ADD VALUE 'interested';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'not_interested' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userbookstatus')) THEN
                ALTER TYPE userbookstatus ADD VALUE 'not_interested';
            END IF;
        END
        $$;
    """)
    
    # Step 2: Migrate existing data (only if table exists)
    # Map "read" -> "read_liked" (default assumption for existing read books)
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.user_book_interactions') IS NOT NULL THEN
                -- On a fresh DB, there are no rows, so this is safe
                -- For existing DBs, we need to handle the old 'read' value
                -- Check if any rows have the old 'read' value (as text, not enum)
                IF EXISTS (
                    SELECT 1 FROM user_book_interactions 
                    WHERE status::text = 'read'
                ) THEN
                    -- Temporarily cast to text to compare, then update
                    UPDATE user_book_interactions 
                    SET status = 'read_liked'::userbookstatus 
                    WHERE status::text = 'read';
                END IF;
            END IF;
        END
        $$;
    """)
    
    # Map "interesting" -> "interested"
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.user_book_interactions') IS NOT NULL THEN
                -- Check if any rows have the old 'interesting' value (as text, not enum)
                IF EXISTS (
                    SELECT 1 FROM user_book_interactions 
                    WHERE status::text = 'interesting'
                ) THEN
                    UPDATE user_book_interactions 
                    SET status = 'interested'::userbookstatus 
                    WHERE status::text = 'interesting';
                END IF;
            END IF;
        END
        $$;
    """)
    
    # Step 3: Remove old enum values by recreating the enum type
    # Only do this if the enum has old values (for existing DBs)
    # On a fresh DB, the enum already has the correct values, so skip this step
    op.execute("""
        DO $$
        DECLARE
            has_old_values BOOLEAN := FALSE;
        BEGIN
            -- Check if enum has old values ('read' or 'interesting')
            SELECT EXISTS (
                SELECT 1 FROM pg_enum 
                WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userbookstatus')
                AND enumlabel IN ('read', 'interesting')
            ) INTO has_old_values;
            
            IF has_old_values THEN
                -- Create a new enum type with only the new values
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userbookstatus_new') THEN
                    CREATE TYPE userbookstatus_new AS ENUM ('read_liked', 'read_disliked', 'interested', 'not_interested');
                END IF;
                
                -- Update the column to use the new enum type (only if table exists)
                IF to_regclass('public.user_book_interactions') IS NOT NULL THEN
                    ALTER TABLE user_book_interactions 
                    ALTER COLUMN status TYPE userbookstatus_new 
                    USING status::text::userbookstatus_new;
                END IF;
                
                -- Drop the old enum type and rename the new one
                DROP TYPE IF EXISTS userbookstatus;
                ALTER TYPE userbookstatus_new RENAME TO userbookstatus;
            END IF;
        END
        $$;
    """)


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

