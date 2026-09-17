"""Add action states and reflection history (RD-57).

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("reading_takeaways", sa.Column("action_completed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("reading_takeaways", sa.Column("next_step", sa.Text(), nullable=False, server_default=""))
    op.add_column("reading_takeaways", sa.Column("action_generation", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("reading_takeaways", sa.Column("reflection_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint("ck_reading_takeaway_next_step", "reading_takeaways", "char_length(next_step) <= 2000")
    op.create_check_constraint("ck_reading_takeaway_reflection_counters", "reading_takeaways", "action_generation >= 1 AND reflection_count >= 0")
    op.create_check_constraint("ck_reading_takeaway_action_state", "reading_takeaways", "action_text <> '' OR (NOT action_completed AND next_step = '')")
    op.create_table(
        "reading_reflections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("takeaway_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reading_takeaways.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("action_generation", sa.Integer(), nullable=False),
        sa.Column("attempted_on", sa.Date(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("next_step", sa.Text(), nullable=False, server_default=""),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("action_snapshot", sa.Text(), nullable=False),
        sa.Column("goal_snapshot", sa.Text(), nullable=False),
        sa.Column("takeaway_snapshot", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("takeaway_id", "client_id", name="uq_reading_reflection_client"),
        sa.UniqueConstraint("takeaway_id", "sequence", name="uq_reading_reflection_sequence"),
        sa.CheckConstraint("sequence >= 1 AND action_generation >= 1", name="ck_reading_reflection_counters"),
        sa.CheckConstraint("outcome IN ('helped', 'mixed', 'did_not_help', 'too_soon')", name="ck_reading_reflection_outcome"),
        sa.CheckConstraint("char_length(trim(result)) BETWEEN 1 AND 4000", name="ck_reading_reflection_result"),
        sa.CheckConstraint("char_length(next_step) <= 2000 AND (completed OR char_length(trim(next_step)) >= 1)", name="ck_reading_reflection_next_step"),
    )


def downgrade():
    op.drop_table("reading_reflections")
    for name in ("ck_reading_takeaway_action_state", "ck_reading_takeaway_reflection_counters", "ck_reading_takeaway_next_step"):
        op.drop_constraint(name, "reading_takeaways", type_="check")
    for name in ("reflection_count", "action_generation", "next_step", "action_completed"):
        op.drop_column("reading_takeaways", name)
