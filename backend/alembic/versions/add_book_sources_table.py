"""add_book_sources_table

Revision ID: a1b2c3d4e5f6
Revises: 000000000000
Create Date: 2026-01-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '000000000000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create book_sources table
    op.create_table(
        'book_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('book_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_name', sa.Text(), nullable=False),
        sa.Column('source_year', sa.Integer(), nullable=False),
        sa.Column('source_rank', sa.Integer(), nullable=False),
        sa.Column('source_category', sa.Text(), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['book_id'], ['books.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('book_id', 'source_name', 'source_year', 'source_category', name='uq_book_source_unique')
    )

    # Create indexes
    op.create_index('idx_book_sources_book_id', 'book_sources', ['book_id'])
    op.create_index('idx_book_sources_source', 'book_sources', ['source_name', 'source_year', 'source_category'])


def downgrade() -> None:
    op.drop_index('idx_book_sources_source', table_name='book_sources')
    op.drop_index('idx_book_sources_book_id', table_name='book_sources')
    op.drop_table('book_sources')
