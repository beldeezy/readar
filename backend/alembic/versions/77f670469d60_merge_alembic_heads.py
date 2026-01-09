"""Merge alembic heads

Revision ID: 77f670469d60
Revises: a1b2c3d4e5f6, add_pending_books_table
Create Date: 2026-01-09 12:18:04.273683

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77f670469d60'
down_revision: Union[str, None] = ('a1b2c3d4e5f6', 'add_pending_books_table')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

