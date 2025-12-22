"""merge heads for book status + auth fields

Revision ID: merge_heads_book_status_auth
Revises: 80a813719b89
Create Date: 2025-01-XX

Note: This was originally a merge migration, but we've linearized the chain.
This now just follows 80a813719b89.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'merge_heads_book_status_auth'
down_revision: Union[str, Sequence[str], None] = 'ensure_user_book_status_table'  # Linear chain: comes after ensure_user_book_status_table
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This is a merge migration - no schema changes needed
    # Both parent migrations have already been applied
    pass


def downgrade() -> None:
    # This is a merge migration - no schema changes needed
    pass

