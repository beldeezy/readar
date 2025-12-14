"""create reading_history_entries table

Revision ID: ee4e43888fe6
Revises: 6fb58de6fce8
Create Date: 2025-12-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "ee4e43888fe6"  # Keep existing revision ID to maintain migration chain
down_revision: str = "6fb58de6fce8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reading_history_entries",
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
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("my_rating", sa.Float(), nullable=True),
        sa.Column("date_read", sa.String(), nullable=True),
        sa.Column("shelf", sa.String(), nullable=True),
        sa.Column(
            "source",
            sa.String(),
            nullable=False,
            server_default="goodreads",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("reading_history_entries")

