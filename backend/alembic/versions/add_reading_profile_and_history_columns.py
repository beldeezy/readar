"""Add user_reading_profiles table and new columns to reading_history_entries

Revision ID: 7a8b9c0d1e2f
Revises: 54f53f2927c2
Create Date: 2026-03-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from typing import Union

revision: str = "7a8b9c0d1e2f"
down_revision: Union[str, None] = "54f53f2927c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. New columns on reading_history_entries
    # ------------------------------------------------------------------
    # isbn / isbn13 — to preserve CSV data for better catalog matching
    op.add_column(
        "reading_history_entries",
        sa.Column("isbn", sa.String(), nullable=True),
    )
    op.add_column(
        "reading_history_entries",
        sa.Column("isbn13", sa.String(), nullable=True),
    )
    # FK to Books catalog — set when entry is matched/upserted during import
    op.add_column(
        "reading_history_entries",
        sa.Column(
            "catalog_book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id"),
            nullable=True,
        ),
    )
    # updated_at for merge tracking
    op.add_column(
        "reading_history_entries",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ------------------------------------------------------------------
    # 2. New table: user_reading_profiles
    # ------------------------------------------------------------------
    op.create_table(
        "user_reading_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("total_books_read", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_rating", sa.Float(), nullable=True),
        sa.Column("structured_tags", postgresql.JSONB(), nullable=True),
        sa.Column("profile_summary", sa.Text(), nullable=True),
        sa.Column("reading_confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_user_reading_profiles_user_id",
        "user_reading_profiles",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_user_reading_profiles_user_id", table_name="user_reading_profiles")
    op.drop_table("user_reading_profiles")

    op.drop_column("reading_history_entries", "updated_at")
    op.drop_column("reading_history_entries", "catalog_book_id")
    op.drop_column("reading_history_entries", "isbn13")
    op.drop_column("reading_history_entries", "isbn")
