"""Merge heads

Revision ID: 3b9a0a068da5
Revises: ('add_free_to_subscriptionstatus_enum', 'add_user_book_feedback_table')
Create Date: 2025-01-20 13:00:00.000000

Merge migration for add_free_to_subscriptionstatus_enum and add_user_book_feedback_table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b9a0a068da5'
down_revision: Union[str, Sequence[str], None] = ('add_free_to_subscriptionstatus_enum', 'add_user_book_feedback_table')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

