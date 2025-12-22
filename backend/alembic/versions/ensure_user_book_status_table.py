"""ensure user_book_status table exists

Revision ID: ensure_user_book_status_table
Revises: 80a813719b89
Create Date: 2025-01-XX

This migration safely creates the user_book_status table if it doesn't exist.
This handles the case where the DB is stamped at 80a813719b89 but the table
was never created (e.g., due to migration order issues or partial application).

This is idempotent - safe to run even if the table already exists.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "ensure_user_book_status_table"
down_revision: str = "80a813719b89"  # Linear chain: comes after 80a813719b89
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Get database connection and inspector
    bind = op.get_bind()
    insp = inspect(bind)
    
    # Check if table already exists
    if "user_book_status" not in insp.get_table_names():
        # Create the table with the same schema as add_user_book_status_table
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
    # Get database connection and inspector
    bind = op.get_bind()
    insp = inspect(bind)
    
    # Check if table exists before dropping
    if "user_book_status" in insp.get_table_names():
        op.drop_constraint("uq_user_book_status_user_book", "user_book_status", type_="unique")
        op.drop_index("ix_user_book_status_book_id", table_name="user_book_status")
        op.drop_index("ix_user_book_status_user_id", table_name="user_book_status")
        op.drop_table("user_book_status")

