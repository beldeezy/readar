"""add user_book_status table

Revision ID: add_user_book_status_table
Revises: add_event_logs_table
Create Date: 2025-01-XX

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "add_user_book_status_table"
down_revision: str = "add_event_logs_table"  # Linear chain after add_event_logs_table
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_book_status",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("book_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Create indexes
    op.create_index("ix_user_book_status_user_id", "user_book_status", ["user_id"])
    op.create_index("ix_user_book_status_book_id", "user_book_status", ["book_id"])
    # Create unique constraint
    op.create_unique_constraint(
        "uq_user_book_status_user_book",
        "user_book_status",
        ["user_id", "book_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_user_book_status_user_book", "user_book_status", type_="unique")
    op.drop_index("ix_user_book_status_book_id", table_name="user_book_status")
    op.drop_index("ix_user_book_status_user_id", table_name="user_book_status")
    op.drop_table("user_book_status")

