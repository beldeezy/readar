"""add current_gross_revenue to onboarding_profiles

Revision ID: f1a2b3c4d5e6
Revises: 000000000000
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str = "000000000000"  # Depends on baseline that creates onboarding_profiles table
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "onboarding_profiles",
        sa.Column("current_gross_revenue", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("onboarding_profiles", "current_gross_revenue")

