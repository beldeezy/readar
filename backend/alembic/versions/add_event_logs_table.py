"""add event_logs table

Revision ID: add_event_logs_table
Revises: 9b0a1aada2ec
Create Date: 2025-01-XX

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "add_event_logs_table"
down_revision: str = "9b0a1aada2ec"  # Linear chain: comes after 9b0a1aada2ec
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("event_name", sa.String(), nullable=False),
        sa.Column("properties", postgresql.JSONB, nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=True),
    )
    # Create indexes
    op.create_index("ix_event_logs_created_at", "event_logs", ["created_at"])
    op.create_index("ix_event_logs_event_name", "event_logs", ["event_name"])
    op.create_index("ix_event_logs_user_id", "event_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_event_logs_user_id", table_name="event_logs")
    op.drop_index("ix_event_logs_event_name", table_name="event_logs")
    op.drop_index("ix_event_logs_created_at", table_name="event_logs")
    op.drop_table("event_logs")

