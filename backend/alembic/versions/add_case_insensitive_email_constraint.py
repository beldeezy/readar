"""add_case_insensitive_email_constraint

Revision ID: add_case_insensitive_email_constraint
Revises: fix_enum_value_casing_and_storage
Create Date: 2025-01-21 13:00:00.000000

Add case-insensitive email uniqueness constraint and normalize existing emails to lowercase.
This prevents duplicate emails like "Test@Example.com" and "test@example.com" from both existing.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_case_insensitive_email_constraint'
down_revision: Union[str, None] = 'fix_enum_value_casing_and_storage'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Normalize all existing emails to lowercase
    op.execute("""
        UPDATE users
        SET email = LOWER(email)
        WHERE email IS NOT NULL AND email != LOWER(email);
    """)
    
    # Step 2: Create functional unique index on lower(email) for case-insensitive uniqueness
    # This ensures that "Test@Example.com" and "test@example.com" cannot both exist
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_lower_unique 
        ON users (LOWER(email))
        WHERE email IS NOT NULL;
    """)


def downgrade() -> None:
    # Drop the functional unique index
    op.execute("DROP INDEX IF EXISTS ix_users_email_lower_unique;")

