"""merge heads for book status + auth fields

Revision ID: merge_heads_book_status_auth
Revises: 9b0a1aada2ec, add_user_book_status_table
Create Date: 2025-01-XX

This merge migration combines two parallel branches:
- 9b0a1aada2ec: merge of auth_user_id and book_insight_fields
- add_user_book_status_table: adds user_book_status table

After this merge, both branches are unified into a single head.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'merge_heads_book_status_auth'
down_revision: Union[str, Sequence[str], None] = ('9b0a1aada2ec', 'add_user_book_status_table')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This is a merge migration - no schema changes needed
    # Both parent migrations have already been applied
    pass


def downgrade() -> None:
    # This is a merge migration - no schema changes needed
    pass

