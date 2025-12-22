"""add user_book_feedback table

Revision ID: add_user_book_feedback_table
Revises: 94c3955325f9
Create Date: 2025-01-XX

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "add_user_book_feedback_table"
down_revision: Union[str, None] = "94c3955325f9"  # Linear chain: comes after 94c3955325f9
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types for feedback
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feedbacksentiment') THEN
                CREATE TYPE feedbacksentiment AS ENUM ('positive', 'negative');
            END IF;
        END
        $$;
    """)
    
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feedbackstate') THEN
                CREATE TYPE feedbackstate AS ENUM ('interested', 'read_completed', 'dismissed');
            END IF;
        END
        $$;
    """)
    
    # Create user_book_feedback table
    op.create_table(
        "user_book_feedback",
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
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "sentiment",
            postgresql.ENUM('positive', 'negative', name='feedbacksentiment', create_type=False),
            nullable=False,
        ),
        sa.Column(
            "state",
            postgresql.ENUM('interested', 'read_completed', 'dismissed', name='feedbackstate', create_type=False),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(),
            nullable=False,
            server_default="recommendations_v1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    
    # Create indexes
    op.create_index("ix_user_book_feedback_user_id", "user_book_feedback", ["user_id"])
    op.create_index("ix_user_book_feedback_book_id", "user_book_feedback", ["book_id"])
    op.create_index("idx_user_book_feedback_user_book", "user_book_feedback", ["user_id", "book_id"])


def downgrade() -> None:
    op.drop_index("idx_user_book_feedback_user_book", table_name="user_book_feedback")
    op.drop_index("ix_user_book_feedback_book_id", table_name="user_book_feedback")
    op.drop_index("ix_user_book_feedback_user_id", table_name="user_book_feedback")
    op.drop_table("user_book_feedback")
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS feedbackstate")
    op.execute("DROP TYPE IF EXISTS feedbacksentiment")

