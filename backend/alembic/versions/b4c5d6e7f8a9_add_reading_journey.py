"""Durable book completion and opt-out/snooze for in-app return prompts.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("reading_journey_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("show_next_action", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("snoozed_until", sa.Date(), nullable=True),
    )
    op.create_table("reading_completions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("completed_on", sa.Date(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("reflection", sa.Text(), nullable=False, server_default=""),
        sa.Column("challenge_before", sa.Text(), nullable=False, server_default=""),
        sa.Column("challenge_after", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "book_id", name="uq_reading_completion_user_book"),
        sa.UniqueConstraint("user_id", "request_id", name="uq_reading_completion_user_request"),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_reading_completion_rating"),
        sa.CheckConstraint("char_length(reflection) <= 2000", name="ck_reading_completion_reflection"),
    )


def downgrade():
    op.drop_table("reading_completions")
    op.drop_table("reading_journey_preferences")
