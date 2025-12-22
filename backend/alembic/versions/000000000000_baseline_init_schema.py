"""baseline_init_schema

Revision ID: 000000000000
Revises: 
Create Date: 2025-01-20 00:00:00.000000

This is the baseline migration that creates all core tables and types.
All other migrations should depend on this revision.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '000000000000'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types (SQLAlchemy will create them automatically when creating tables, but we create them first to be safe)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscriptionstatus') THEN
                CREATE TYPE subscriptionstatus AS ENUM ('free', 'active', 'canceled');
            END IF;
        END
        $$;
    """)
    
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'businessstage') THEN
                CREATE TYPE businessstage AS ENUM ('idea', 'pre-revenue', 'early-revenue', 'scaling');
            END IF;
        END
        $$;
    """)
    
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'bookdifficulty') THEN
                CREATE TYPE bookdifficulty AS ENUM ('light', 'medium', 'deep');
            END IF;
        END
        $$;
    """)
    
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userbookstatus') THEN
                CREATE TYPE userbookstatus AS ENUM ('read_liked', 'read_disliked', 'interested', 'not_interested');
            END IF;
        END
        $$;
    """)
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        # auth_user_id added in add_auth_user_id migration
        sa.Column('email', sa.String(), nullable=False),  # Made nullable in add_auth_user_id migration
        sa.Column('password_hash', sa.String(), nullable=False),  # Made nullable in add_auth_user_id migration
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('subscription_status', postgresql.ENUM('free', 'active', 'canceled', name='subscriptionstatus', create_type=False), nullable=True),
        sa.Column('stripe_customer_id', sa.String(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    # ix_users_auth_user_id created in add_auth_user_id migration
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    # Create books table
    op.create_table(
        'books',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('external_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('subtitle', sa.String(), nullable=True),
        sa.Column('author_name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('thumbnail_url', sa.String(), nullable=True),
        sa.Column('cover_image_url', sa.String(), nullable=True),
        sa.Column('purchase_url', sa.String(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('published_year', sa.Integer(), nullable=True),
        sa.Column('language', sa.String(), nullable=True),
        sa.Column('isbn_10', sa.String(), nullable=True),
        sa.Column('isbn_13', sa.String(), nullable=True),
        sa.Column('average_rating', sa.Float(), nullable=True),
        sa.Column('ratings_count', sa.Integer(), nullable=True),
        sa.Column('categories', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('business_stage_tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('functional_tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('theme_tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('difficulty', postgresql.ENUM('light', 'medium', 'deep', name='bookdifficulty', create_type=False), nullable=True),
        # promise, best_for, core_frameworks, anti_patterns, outcomes added in cb17facfbf15 migration
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create onboarding_profiles table
    op.create_table(
        'onboarding_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('occupation', sa.String(), nullable=True),
        # entrepreneur_status, economic_sector, current_gross_revenue added in later migrations
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('industry', sa.String(), nullable=True),
        sa.Column('business_model', sa.String(), nullable=False),
        sa.Column('business_experience', sa.String(), nullable=True),
        sa.Column('areas_of_business', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('business_stage', postgresql.ENUM('idea', 'pre-revenue', 'early-revenue', 'scaling', name='businessstage', create_type=False), nullable=False),
        sa.Column('org_size', sa.String(), nullable=True),
        sa.Column('is_student', sa.Boolean(), nullable=True),
        sa.Column('biggest_challenge', sa.Text(), nullable=False),
        sa.Column('vision_6_12_months', sa.Text(), nullable=True),
        sa.Column('blockers', sa.Text(), nullable=True),
        # current_gross_revenue added in f1a2b3c4d5e6 migration
        sa.Column('has_prior_reading_history', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    # Create user_book_interactions table
    op.create_table(
        'user_book_interactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('book_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', postgresql.ENUM('read_liked', 'read_disliked', 'interested', 'not_interested', name='userbookstatus', create_type=False), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['book_id'], ['books.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create recommendation_sessions table
    op.create_table(
        'recommendation_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('request_payload', sa.JSON(), nullable=True),
        sa.Column('results', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('recommendation_sessions')
    op.drop_table('user_book_interactions')
    op.drop_table('onboarding_profiles')
    op.drop_table('books')
    op.drop_table('users')
    
    op.execute('DROP TYPE IF EXISTS userbookstatus')
    op.execute('DROP TYPE IF EXISTS bookdifficulty')
    op.execute('DROP TYPE IF EXISTS businessstage')
    op.execute('DROP TYPE IF EXISTS subscriptionstatus')

