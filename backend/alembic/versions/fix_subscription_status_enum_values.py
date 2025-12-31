"""fix_subscription_status_enum_values

Revision ID: fix_subscription_status_enum
Revises: 3b9a0a068da5
Create Date: 2025-01-21 00:00:00.000000

Fix subscription_status column to:
1. Store enum VALUES (not names) - configured in SQLAlchemy model
2. Set nullable=False
3. Set server_default='free'
4. Update any existing NULL values to 'free'

This ensures SQLAlchemy stores "free" (enum value) instead of "FREE" (enum name).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'fix_subscription_status_enum'
down_revision: Union[str, None] = '3b9a0a068da5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Update any NULL values to 'free' (the default)
    op.execute("""
        UPDATE users
        SET subscription_status = 'free'
        WHERE subscription_status IS NULL;
    """)
    
    # Step 2: Set server_default to 'free'
    # First, drop the existing default if any (though there may not be one)
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN subscription_status DROP DEFAULT;
    """)
    
    # Then set the new default
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN subscription_status SET DEFAULT 'free';
    """)
    
    # Step 3: Set nullable=False
    op.alter_column(
        'users',
        'subscription_status',
        nullable=False,
        existing_type=postgresql.ENUM('free', 'active', 'canceled', name='subscriptionstatus', create_type=False),
    )


def downgrade() -> None:
    # Revert to nullable=True and remove default
    op.alter_column(
        'users',
        'subscription_status',
        nullable=True,
        existing_type=postgresql.ENUM('free', 'active', 'canceled', name='subscriptionstatus', create_type=False),
    )
    
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN subscription_status DROP DEFAULT;
    """)

