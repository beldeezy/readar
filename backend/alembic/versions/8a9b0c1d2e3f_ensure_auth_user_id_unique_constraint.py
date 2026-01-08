"""ensure_auth_user_id_unique_constraint

Revision ID: 8a9b0c1d2e3f
Revises: 2b3c4d5e6f7a
Create Date: 2025-01-21 14:00:00.000000

Ensure auth_user_id has unique constraint and index for Supabase Auth source of truth.
This migration is idempotent - it checks if constraints/indexes exist before creating.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a9b0c1d2e3f'
down_revision: Union[str, None] = '2b3c4d5e6f7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure unique index on auth_user_id exists (idempotent)
    # The index was created in add_auth_user_id migration, but we ensure it exists here
    op.execute("""
        DO $$
        BEGIN
            -- Check if unique index exists
            IF NOT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'users'
                  AND indexname = 'ix_users_auth_user_id'
            ) THEN
                CREATE UNIQUE INDEX ix_users_auth_user_id ON users (auth_user_id)
                WHERE auth_user_id IS NOT NULL;
            END IF;
        END$$;
    """)


def downgrade() -> None:
    # Don't drop the index - it may be needed by other migrations
    # The add_auth_user_id migration handles the downgrade
    pass

