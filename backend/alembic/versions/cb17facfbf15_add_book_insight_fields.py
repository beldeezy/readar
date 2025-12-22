"""add book insight fields

Revision ID: cb17facfbf15
Revises: add_auth_user_id
Create Date: 2025-12-15 12:16:05.499701

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'cb17facfbf15'
down_revision: Union[str, None] = 'add_auth_user_id'  # Linear chain: comes after add_auth_user_id
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add insight fields to books table
    op.add_column('books', sa.Column('promise', sa.Text(), nullable=True))
    op.add_column('books', sa.Column('best_for', sa.Text(), nullable=True))
    op.add_column('books', sa.Column('core_frameworks', postgresql.JSONB(), nullable=True))
    op.add_column('books', sa.Column('anti_patterns', postgresql.JSONB(), nullable=True))
    op.add_column('books', sa.Column('outcomes', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    # Remove insight fields from books table
    op.drop_column('books', 'outcomes')
    op.drop_column('books', 'anti_patterns')
    op.drop_column('books', 'core_frameworks')
    op.drop_column('books', 'best_for')
    op.drop_column('books', 'promise')

