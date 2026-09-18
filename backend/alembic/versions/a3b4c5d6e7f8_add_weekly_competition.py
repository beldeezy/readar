"""Weekly Friendly Competition with explicit progress-sharing consent (RD-59).

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a3b4c5d6e7f8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('friendly_pairs', sa.Column('competition_timezone', sa.String(64), nullable=True))
    op.add_column('friendly_pairs', sa.Column('competition_starts_on', sa.Date(), nullable=True))
    op.add_column('friendly_participations', sa.Column('competition_consented_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('friendly_participations', sa.Column('competition_unit', sa.String(), nullable=True))
    for name in ('competition_total', 'competition_starting_position', 'competition_goal', 'competition_baseline_position'):
        op.add_column('friendly_participations', sa.Column(name, sa.Integer(), nullable=True))
    op.create_table('friendly_rounds',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pairing_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('friendly_pairs.id'), nullable=False),
        sa.Column('starts_on', sa.Date(), nullable=False),
        sa.Column('ends_before', sa.Date(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        *[sa.Column(name, sa.Integer(), nullable=False, server_default='0') for name in
          ('first_days', 'second_days', 'first_progress_bps', 'second_progress_bps', 'first_score', 'second_score')],
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('pairing_id', 'starts_on', name='uq_friendly_round_pair_start'),
        sa.CheckConstraint('ends_before = starts_on + 7', name='ck_friendly_round_week'),
        sa.CheckConstraint("status IN ('active', 'finished', 'ended') AND ((status = 'active' AND closed_at IS NULL) OR (status <> 'active' AND closed_at IS NOT NULL))", name='ck_friendly_round_status'),
        sa.CheckConstraint('first_days BETWEEN 0 AND 7 AND second_days BETWEEN 0 AND 7 AND first_progress_bps BETWEEN 0 AND 10000 AND second_progress_bps BETWEEN 0 AND 10000', name='ck_friendly_round_progress'),
        sa.CheckConstraint('first_score = first_days * 1000 + first_progress_bps / 20 AND second_score = second_days * 1000 + second_progress_bps / 20', name='ck_friendly_round_score'),
    )


def downgrade():
    op.drop_table('friendly_rounds')
    for name in ('competition_baseline_position', 'competition_goal', 'competition_starting_position', 'competition_total', 'competition_unit', 'competition_consented_at'):
        op.drop_column('friendly_participations', name)
    op.drop_column('friendly_pairs', 'competition_starts_on')
    op.drop_column('friendly_pairs', 'competition_timezone')
