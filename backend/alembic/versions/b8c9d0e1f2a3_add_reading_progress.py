"""Add reading settings and daily position logs (RD-54).

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reading_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit", sa.String(), nullable=False, server_default="pages"),
        sa.Column("starting_position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_units", sa.Integer(), nullable=True),
        sa.Column("daily_goal", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", "book_id", name="uq_reading_progress_user_book"),
        sa.CheckConstraint("unit IN ('pages', 'chapters')", name="ck_reading_progress_unit"),
        sa.CheckConstraint("starting_position >= 0 AND starting_position <= 100000", name="ck_reading_progress_start"),
        sa.CheckConstraint("daily_goal >= 1 AND daily_goal <= 1000", name="ck_reading_progress_goal"),
        sa.CheckConstraint("total_units IS NULL OR (total_units >= 1 AND total_units <= 100000 AND total_units >= starting_position)", name="ck_reading_progress_total"),
    )
    op.create_table(
        "reading_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reading_date", sa.Date(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "book_id", "reading_date", name="uq_reading_log_user_book_date"),
        sa.CheckConstraint("position >= 0 AND position <= 100000", name="ck_reading_log_position"),
    )


def downgrade():
    op.drop_table("reading_logs")
    op.drop_table("reading_progress")
