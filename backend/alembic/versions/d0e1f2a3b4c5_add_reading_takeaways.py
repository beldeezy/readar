"""Add reader-authored takeaways and actions (RD-56).

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reading_takeaways",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("book_title", sa.Text(), nullable=False),
        sa.Column("book_author", sa.Text(), nullable=False),
        sa.Column("takeaway", sa.Text(), nullable=False),
        sa.Column("action_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("goal_context", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "client_id", name="uq_reading_takeaway_user_client"),
        sa.CheckConstraint("char_length(trim(takeaway)) BETWEEN 1 AND 4000", name="ck_reading_takeaway_text"),
        sa.CheckConstraint("char_length(trim(goal_context)) BETWEEN 1 AND 2000", name="ck_reading_takeaway_goal"),
        sa.CheckConstraint("char_length(action_text) <= 2000", name="ck_reading_takeaway_action"),
        sa.CheckConstraint("revision >= 1", name="ck_reading_takeaway_revision"),
    )
    op.create_index("ix_reading_takeaway_user_created", "reading_takeaways", ["user_id", "created_at", "id"])


def downgrade():
    op.drop_index("ix_reading_takeaway_user_created", table_name="reading_takeaways")
    op.drop_table("reading_takeaways")
