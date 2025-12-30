"""add_free_to_subscriptionstatus_enum

Revision ID: add_free_to_subscriptionstatus_enum
Revises: 94c3955325f9
Create Date: 2025-01-20 12:00:00.000000

Ensures 'free' (lowercase) enum value exists in subscriptionstatus enum type.
Safe to run multiple times - checks if value exists before adding.
Note: The Python enum SubscriptionStatus.FREE maps to "free" (lowercase).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'add_free_to_subscriptionstatus_enum'
down_revision: Union[str, None] = '94c3955325f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure 'free' (lowercase) exists in subscriptionstatus enum
    # This is safe to run multiple times - checks if value exists before adding
    # The Python enum SubscriptionStatus.FREE maps to "free" (lowercase)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'subscriptionstatus'
                  AND e.enumlabel = 'free'
            ) THEN
                ALTER TYPE subscriptionstatus ADD VALUE 'free';
            END IF;
        END$$;
    """)


def downgrade() -> None:
    # Postgres enums can't easily remove values, so this is a no-op
    pass

