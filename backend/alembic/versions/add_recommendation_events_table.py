"""add_recommendation_events_table

Revision ID: d8e9f0a1b2c3
Revises: merge_all_branches_final
Create Date: 2026-01-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, None] = 'merge_all_branches_final'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create recommendation_events table
    op.create_table(
        'recommendation_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('book_id', UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('recommendation_session_id', sa.String(), nullable=True),
        sa.Column('event_metadata', JSONB, nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['book_id'], ['books.id'], ),
    )

    # Create indexes
    op.create_index('ix_recommendation_events_user_id', 'recommendation_events', ['user_id'])
    op.create_index('ix_recommendation_events_book_id', 'recommendation_events', ['book_id'])
    op.create_index('ix_recommendation_events_event_type', 'recommendation_events', ['event_type'])
    op.create_index('ix_recommendation_events_created_at', 'recommendation_events', ['created_at'])
    op.create_index('ix_recommendation_events_recommendation_session_id', 'recommendation_events', ['recommendation_session_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_recommendation_events_recommendation_session_id', table_name='recommendation_events')
    op.drop_index('ix_recommendation_events_created_at', table_name='recommendation_events')
    op.drop_index('ix_recommendation_events_event_type', table_name='recommendation_events')
    op.drop_index('ix_recommendation_events_book_id', table_name='recommendation_events')
    op.drop_index('ix_recommendation_events_user_id', table_name='recommendation_events')

    # Drop table
    op.drop_table('recommendation_events')
