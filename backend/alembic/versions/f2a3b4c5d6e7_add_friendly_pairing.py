"""Optional Friendly Competition pairing (RD-58).

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('friendly_pairs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('first_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('second_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.CheckConstraint('first_user_id <> second_user_id', name='ck_friendly_pair_distinct'),
        sa.CheckConstraint('(ended_at IS NULL AND ended_by IS NULL) OR (ended_at IS NOT NULL AND ended_by IS NOT NULL AND ended_by IN (first_user_id, second_user_id))', name='ck_friendly_pair_ended'),
    )
    op.create_table('friendly_participations',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('status', sa.String(), nullable=False, server_default='inactive'),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reading_name', sa.String(32), nullable=False, server_default=''),
        sa.Column('book_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('books.id'), nullable=True),
        sa.Column('book_title', sa.Text(), nullable=False, server_default=''),
        sa.Column('book_author', sa.Text(), nullable=False, server_default=''),
        sa.Column('queued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pairing_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('friendly_pairs.id'), nullable=True),
        sa.Column('consented_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_request_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('last_request_hash', sa.String(64), nullable=True),
        sa.CheckConstraint("status IN ('inactive', 'waiting', 'paired', 'ended')", name='ck_friendly_participation_status'),
        sa.CheckConstraint('revision >= 0', name='ck_friendly_participation_revision'),
        sa.CheckConstraint("status NOT IN ('waiting', 'paired') OR (char_length(trim(reading_name)) BETWEEN 1 AND 32 AND book_id IS NOT NULL AND consented_at IS NOT NULL)", name='ck_friendly_participation_consent'),
        sa.CheckConstraint("(status = 'waiting' AND queued_at IS NOT NULL AND pairing_id IS NULL) OR (status IN ('paired', 'ended') AND queued_at IS NULL AND pairing_id IS NOT NULL) OR (status = 'inactive' AND queued_at IS NULL AND pairing_id IS NULL)", name='ck_friendly_participation_state'),
    )
    op.create_index('ix_friendly_waiting', 'friendly_participations', ['queued_at', 'user_id'], postgresql_where=sa.text("status = 'waiting'"))


def downgrade():
    op.drop_index('ix_friendly_waiting', table_name='friendly_participations')
    op.drop_table('friendly_participations')
    op.drop_table('friendly_pairs')
