"""Preserve the goal used to qualify a reading date (RD-55).

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""
from alembic import op
import sqlalchemy as sa

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("reading_logs", sa.Column("goal_target", sa.Integer(), nullable=True))
    # RD-54 has no goal history. Backfill from its saved book settings once.
    op.execute("""
        UPDATE reading_logs AS log SET goal_target = progress.daily_goal
        FROM reading_progress AS progress
        WHERE log.user_id = progress.user_id AND log.book_id = progress.book_id
    """)
    # Defensive fallback for orphan logs created outside the normal API.
    op.execute("UPDATE reading_logs SET goal_target = 10 WHERE goal_target IS NULL")
    op.alter_column("reading_logs", "goal_target", nullable=False)
    op.create_check_constraint("ck_reading_log_goal_target", "reading_logs", "goal_target >= 1 AND goal_target <= 1000")


def downgrade():
    op.drop_constraint("ck_reading_log_goal_target", "reading_logs", type_="check")
    op.drop_column("reading_logs", "goal_target")
