"""add topic_fit screening columns to books (RD-23)

Both columns are nullable with no server default: NULL means "not yet
screened", and the recommendation gate fails open on NULL, so applying this
migration alone changes nothing about what gets recommended.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-05

"""
from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: str = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("books", sa.Column("topic_fit", sa.String(), nullable=True))
    op.add_column("books", sa.Column("topic_fit_reason", sa.Text(), nullable=True))
    # The gate filters on this column for every recommendation request.
    op.create_index("ix_books_topic_fit", "books", ["topic_fit"])


def downgrade() -> None:
    op.drop_index("ix_books_topic_fit", table_name="books")
    op.drop_column("books", "topic_fit_reason")
    op.drop_column("books", "topic_fit")
