"""fix_enum_value_casing_and_storage

Revision ID: fix_enum_value_casing_and_storage
Revises: add_free_to_subscriptionstatus_enum
Create Date: 2025-01-21 12:00:00.000000

Fix enum casing and storage issues:
1. Ensure canonical lowercase values exist in enum types (subscriptionstatus, businessstage)
2. Repair any rows with uppercase enum values (e.g., "FREE" -> "free")
3. This migration is safe to run multiple times.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'fix_enum_value_casing_and_storage'
down_revision: Union[str, None] = 'add_free_to_subscriptionstatus_enum'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Part A: Ensure canonical values exist in enum types
    
    # subscriptionstatus: ensure 'free', 'active', 'canceled' exist
    op.execute("""
        DO $$
        BEGIN
            -- Add 'free' if missing
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'subscriptionstatus' AND e.enumlabel = 'free'
            ) THEN
                ALTER TYPE subscriptionstatus ADD VALUE 'free';
            END IF;
            
            -- Add 'active' if missing
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'subscriptionstatus' AND e.enumlabel = 'active'
            ) THEN
                ALTER TYPE subscriptionstatus ADD VALUE 'active';
            END IF;
            
            -- Add 'canceled' if missing
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'subscriptionstatus' AND e.enumlabel = 'canceled'
            ) THEN
                ALTER TYPE subscriptionstatus ADD VALUE 'canceled';
            END IF;
        END$$;
    """)
    
    # businessstage: ensure 'idea', 'pre-revenue', 'early-revenue', 'scaling' exist
    op.execute("""
        DO $$
        BEGIN
            -- Add 'idea' if missing
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'businessstage' AND e.enumlabel = 'idea'
            ) THEN
                ALTER TYPE businessstage ADD VALUE 'idea';
            END IF;
            
            -- Add 'pre-revenue' if missing
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'businessstage' AND e.enumlabel = 'pre-revenue'
            ) THEN
                ALTER TYPE businessstage ADD VALUE 'pre-revenue';
            END IF;
            
            -- Add 'early-revenue' if missing
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'businessstage' AND e.enumlabel = 'early-revenue'
            ) THEN
                ALTER TYPE businessstage ADD VALUE 'early-revenue';
            END IF;
            
            -- Add 'scaling' if missing
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'businessstage' AND e.enumlabel = 'scaling'
            ) THEN
                ALTER TYPE businessstage ADD VALUE 'scaling';
            END IF;
        END$$;
    """)
    
    # Part B: Repair polluted rows (uppercase -> lowercase)
    # Note: This is safe even if no rows need updating
    
    # Fix subscriptionstatus: "FREE" -> "free", "ACTIVE" -> "active", "CANCELED" -> "canceled"
    op.execute("""
        UPDATE users
        SET subscription_status = 'free'
        WHERE subscription_status::text = 'FREE';
    """)
    
    op.execute("""
        UPDATE users
        SET subscription_status = 'active'
        WHERE subscription_status::text = 'ACTIVE';
    """)
    
    op.execute("""
        UPDATE users
        SET subscription_status = 'canceled'
        WHERE subscription_status::text = 'CANCELED';
    """)
    
    # Fix businessstage: uppercase enum names -> lowercase values
    # "IDEA" -> "idea", "PRE_REVENUE" -> "pre-revenue", etc.
    op.execute("""
        UPDATE onboarding_profiles
        SET business_stage = 'idea'
        WHERE business_stage::text = 'IDEA';
    """)
    
    op.execute("""
        UPDATE onboarding_profiles
        SET business_stage = 'pre-revenue'
        WHERE business_stage::text = 'PRE_REVENUE';
    """)
    
    op.execute("""
        UPDATE onboarding_profiles
        SET business_stage = 'early-revenue'
        WHERE business_stage::text = 'EARLY_REVENUE';
    """)
    
    op.execute("""
        UPDATE onboarding_profiles
        SET business_stage = 'scaling'
        WHERE business_stage::text = 'SCALING';
    """)


def downgrade() -> None:
    # Postgres enums can't easily remove values, and we don't want to revert
    # the data fixes (uppercase -> lowercase), so this is a no-op
    pass

