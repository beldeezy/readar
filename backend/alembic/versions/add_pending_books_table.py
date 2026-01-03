"""add pending_books table for goodreads import queue

Revision ID: add_pending_books_table
Revises: 000000000000
Create Date: 2026-01-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "add_pending_books_table"
down_revision: str = "000000000000"  # Depends on baseline that creates books table
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safety guard: ensure books table exists before creating FK to it
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.books') IS NULL THEN
                RAISE EXCEPTION 'books table missing - migration chain is out of order. books table must exist before creating pending_books.';
            END IF;
        END
        $$;
    """)

    op.create_table(
        "pending_books",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("author", sa.String(), nullable=False),
        sa.Column("isbn", sa.String(), nullable=True),
        sa.Column("isbn13", sa.String(), nullable=True),
        sa.Column("goodreads_id", sa.String(), nullable=True),
        sa.Column("goodreads_url", sa.String(), nullable=True),
        sa.Column("year_published", sa.Integer(), nullable=True),
        sa.Column("average_rating", sa.Float(), nullable=True),
        sa.Column("num_pages", sa.Integer(), nullable=True),
        sa.Column(
            "added_to_catalog",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "catalog_book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "added_to_catalog_at",
            sa.DateTime(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("pending_books")
