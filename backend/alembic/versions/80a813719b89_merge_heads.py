"""merge heads for book status + auth fields

Revision ID: 80a813719b89
Revises: add_user_book_status_table
Create Date: 2025-01-XX

Note: This was originally a merge migration, but we've linearized the chain.
9b0a1aada2ec -> add_event_logs_table -> add_user_book_status_table, so this now just follows add_user_book_status_table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80a813719b89'
down_revision: Union[str, Sequence[str], None] = 'add_user_book_status_table'  # Linear chain: comes after add_user_book_status_table
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This is a merge migration - no schema changes needed
    # Both parent migrations have already been applied
    pass


def downgrade() -> None:
    # This is a merge migration - no schema changes needed
    pass

