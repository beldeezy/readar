"""make onboarding_profiles.full_name nullable

Revision ID: make_onboarding_full_name_nullable
Revises: f1a2b3c4d5e6
Create Date: 2025-01-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "make_onboarding_full_name_nullable"
down_revision: str = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Make full_name column nullable to allow extraction from Supabase metadata."""
    op.alter_column(
        "onboarding_profiles",
        "full_name",
        existing_type=sa.String(),
        nullable=True
    )


def downgrade() -> None:
    """Revert full_name to NOT NULL."""
    # First, update any NULL values to a default before applying NOT NULL constraint
    op.execute(
        "UPDATE onboarding_profiles SET full_name = 'User' WHERE full_name IS NULL"
    )
    op.alter_column(
        "onboarding_profiles",
        "full_name",
        existing_type=sa.String(),
        nullable=False
    )
