"""add_match_confidence_fields_to_book_sources

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-01-09 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add match confidence and audit fields to book_sources
    op.add_column('book_sources', sa.Column('match_strategy', sa.Text(), nullable=True))
    op.add_column('book_sources', sa.Column('match_score', sa.Integer(), nullable=True))
    op.add_column('book_sources', sa.Column('matched_volume_id', sa.Text(), nullable=True))
    op.add_column('book_sources', sa.Column('matched_isbn13', sa.Text(), nullable=True))
    op.add_column('book_sources', sa.Column('rejected_candidates_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('book_sources', 'rejected_candidates_count')
    op.drop_column('book_sources', 'matched_isbn13')
    op.drop_column('book_sources', 'matched_volume_id')
    op.drop_column('book_sources', 'match_score')
    op.drop_column('book_sources', 'match_strategy')
